import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import aio_pika
import httpx
from .interno import cabeceras_internas
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import CostoRuta, Factura, TarifaCliente
from .pedidos import PayloadInvalido, registrar_cobro
from .reembolsos import registrar_solicitud

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
SHIPMENT_SERVICE_URL = os.getenv("SHIPMENT_SERVICE_URL")
ROUTING_SERVICE_URL = os.getenv("ROUTING_SERVICE_URL")
EXCHANGE_NAME = "logitrack_events"

COSTO_COMBUSTIBLE_POR_KM = Decimal("1500")
COSTO_PEAJE_POR_KM = Decimal("200")
VELOCIDAD_PROMEDIO_KMH = Decimal("60")

TARIFA_POR_ENVIO_DEFECTO = Decimal("50000")


async def _obtener_envio(envio_id: str):
    if not SHIPMENT_SERVICE_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=cabeceras_internas()) as client:
            resp = await client.get(f"{SHIPMENT_SERVICE_URL}/envios/{envio_id}")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


async def _obtener_ruta_por_envio(envio_id: str):
    if not ROUTING_SERVICE_URL:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=cabeceras_internas()) as client:
            resp = await client.get(f"{ROUTING_SERVICE_URL}/rutas/", params={"envio_id": envio_id})
            resp.raise_for_status()
            rutas = resp.json()
            return rutas[0] if rutas else None
    except Exception:
        return None


def _obtener_o_crear_tarifa(db: Session, cliente_id) -> TarifaCliente:
    tarifa = db.query(TarifaCliente).filter(TarifaCliente.cliente_id == cliente_id).first()
    if tarifa is None:
        tarifa = TarifaCliente(cliente_id=cliente_id, modelo="por_envio", valor=TARIFA_POR_ENVIO_DEFECTO)
        db.add(tarifa)
        db.commit()
        db.refresh(tarifa)
    return tarifa


def _periodo_actual() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _obtener_o_crear_factura_abierta(db: Session, cliente_id, periodo: str) -> Factura:
    factura = (
        db.query(Factura)
        .filter(Factura.cliente_id == cliente_id, Factura.periodo == periodo)
        .first()
    )
    if factura is None:
        factura = Factura(cliente_id=cliente_id, periodo=periodo, monto_total=Decimal("0"), estado="abierta")
        db.add(factura)
        db.commit()
        db.refresh(factura)
    return factura


async def _procesar_shipment_delivered(payload: dict):
    envio_id = uuid.UUID(payload["envio_id"])

    db: Session = SessionLocal()
    try:
        envio = await _obtener_envio(str(envio_id))
        if not envio:
            return  # sin datos del envío no se puede facturar

        cliente_id = uuid.UUID(envio["cliente_id"])

        ruta = await _obtener_ruta_por_envio(str(envio_id))
        distancia_km = Decimal(str(ruta["distancia_km"])) if ruta and ruta.get("distancia_km") is not None else Decimal("0")
        ruta_id = uuid.UUID(ruta["id"]) if ruta else None

        costo_combustible = (distancia_km * COSTO_COMBUSTIBLE_POR_KM).quantize(Decimal("0.01"))
        costo_peajes = (distancia_km * COSTO_PEAJE_POR_KM).quantize(Decimal("0.01"))
        horas_conductor = (distancia_km / VELOCIDAD_PROMEDIO_KMH).quantize(Decimal("0.01")) if distancia_km else Decimal("0")
        costo_total = costo_combustible + costo_peajes

        if ruta_id is not None:
            costo_ruta = CostoRuta(
                ruta_id=ruta_id,
                envio_id=envio_id,
                distancia_km=distancia_km,
                costo_combustible=costo_combustible,
                costo_peajes=costo_peajes,
                horas_conductor=horas_conductor,
                costo_total=costo_total,
            )
            db.add(costo_ruta)
            db.commit()

        tarifa = _obtener_o_crear_tarifa(db, cliente_id)
        periodo = _periodo_actual()
        factura = _obtener_o_crear_factura_abierta(db, cliente_id, periodo)

        if tarifa.modelo == "por_km":
            monto_envio = (tarifa.valor * distancia_km).quantize(Decimal("0.01"))
        elif tarifa.modelo == "tarifa_plana":
            monto_envio = Decimal("0")  # se factura al cerrar el periodo, no por envío individual
        else:  # "por_envio" (defecto)
            monto_envio = tarifa.valor

        if monto_envio > 0:
            factura.monto_total = (factura.monto_total or Decimal("0")) + monto_envio
            db.commit()
    finally:
        db.close()


async def _on_message(message: aio_pika.IncomingMessage):
    async with message.process():
        payload = json.loads(message.body.decode())
        await _procesar_shipment_delivered(payload)


async def _on_shipment_created(message: aio_pika.IncomingMessage):
    """Registra el pago simulado y la factura del pedido. Un evento mal formado se descarta (se registra
    en consola); si falla la base de datos el mensaje vuelve a la cola para reintentarse."""
    async with message.process(requeue=True):
        payload = json.loads(message.body.decode())
        db: Session = SessionLocal()
        try:
            registrar_cobro(db, payload)
        except PayloadInvalido as exc:
            print(f"[billing] shipment.created descartado: {exc}")
        finally:
            db.close()


async def _on_cierre_de_pedido(message: aio_pika.IncomingMessage):
    """shipment.cancelled / shipment.returned: deja registrada la solicitud de reembolso del pedido cobrado.
    El reembolso lo ejecuta un administrador. Evento mal formado: se descarta; error de base de datos: se reintenta."""
    async with message.process(requeue=True):
        payload = json.loads(message.body.decode())
        db: Session = SessionLocal()
        try:
            registrar_solicitud(db, message.routing_key, payload)
        except PayloadInvalido as exc:
            print(f"[billing] {message.routing_key} descartado: {exc}")
        finally:
            db.close()


async def iniciar_consumidor():
    connection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await connection.channel()
    exchange = await channel.declare_exchange(
        EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
    )
    queue = await channel.declare_queue("billing_service.shipment_delivered", durable=True)
    await queue.bind(exchange, routing_key="shipment.delivered")
    await queue.consume(_on_message)

    cola_pedidos = await channel.declare_queue("billing_service.shipment_created", durable=True)
    # created: pedido inmediato o programado que ya llegó a su hora; scheduled: pedido programado aceptado
    # (el pago se registra al aceptar el precio). El registro es idempotente por envío.
    await cola_pedidos.bind(exchange, routing_key="shipment.created")
    await cola_pedidos.bind(exchange, routing_key="shipment.scheduled")
    # split: pedido dividido en partes; el pago es del pedido (las partes no llevan monto)
    await cola_pedidos.bind(exchange, routing_key="shipment.split")
    await cola_pedidos.consume(_on_shipment_created)

    # cancelado o devuelto: el pedido cobrado queda pendiente de reembolso (lo ejecuta el administrador)
    cola_cierres = await channel.declare_queue("billing_service.pedido_cerrado", durable=True)
    await cola_cierres.bind(exchange, routing_key="shipment.cancelled")
    await cola_cierres.bind(exchange, routing_key="shipment.returned")
    await cola_cierres.consume(_on_cierre_de_pedido)
    return connection
