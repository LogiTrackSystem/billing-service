"""Devoluciones y cancelaciones: solicitud de reembolso (automática) y reembolso simulado (administrador).

Reglas:
- Solo se puede reembolsar un pedido que se canceló o se devolvió por completo.
- El pago debe estar 'confirmado'; al reembolsar pasa a 'reembolsado' y su factura a 'anulada'.
- Un pedido dividido se reembolsa completo (el pago es del pedido, no de las partes). Si solo se devolvió
  una parte y otras se entregaron, no hay reembolso automático (queda para revisión manual).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import FacturaPedido, Pago, SolicitudReembolso
from .pedidos import PayloadInvalido


class ReembolsoError(Exception):
    def __init__(self, status: int, codigo: str, mensaje: str):
        super().__init__(mensaje)
        self.status, self.codigo, self.mensaje = status, codigo, mensaje


def _uuid(valor, campo: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(valor))
    except (ValueError, TypeError):
        raise PayloadInvalido(f"{campo} no es un UUID válido")


def _monto(valor) -> Optional[Decimal]:
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except InvalidOperation:
        raise PayloadInvalido("monto no válido")


def solicitud_desde_evento(clave: str, payload: dict) -> Optional[dict]:
    """Interpreta shipment.cancelled / shipment.returned. Devuelve los datos de la solicitud o None si el
    evento no corresponde a un pedido cobrado (una parte suelta, un envío sin monto, una devolución parcial)."""
    if clave == "shipment.cancelled":
        if payload.get("monto_cop") is None:
            return None  # parte de un pedido dividido o envío anterior al cobro: no tiene pago propio
        return {
            "envio_id": _uuid(payload.get("envio_id"), "envio_id"), "motivo": "cancelado",
            "codigo_envio": payload.get("codigo_envio"),
            "cliente_id": _uuid(payload["cliente_id"], "cliente_id") if payload.get("cliente_id") else None,
            "monto_cop": _monto(payload.get("monto_cop")), "detalle": payload.get("motivo"),
        }
    if clave == "shipment.returned":
        if not payload.get("pedido_devuelto") or payload.get("pedido_monto_cop") is None:
            return None  # devolución parcial, o pedido sin cobro
        return {
            "envio_id": _uuid(payload.get("pedido_id") or payload.get("envio_id"), "pedido_id"), "motivo": "devuelto",
            "codigo_envio": payload.get("pedido_codigo") or payload.get("codigo_envio"),
            "cliente_id": _uuid(payload["cliente_id"], "cliente_id") if payload.get("cliente_id") else None,
            "monto_cop": _monto(payload.get("pedido_monto_cop")), "detalle": payload.get("notas"),
        }
    return None


def registrar_solicitud(db: Session, clave: str, payload: dict) -> Optional[SolicitudReembolso]:
    """Idempotente: una sola solicitud por pedido. Lanza PayloadInvalido si el evento está mal formado."""
    datos = solicitud_desde_evento(clave, payload)
    if datos is None:
        return None
    existente = db.query(SolicitudReembolso).filter(SolicitudReembolso.envio_id == datos["envio_id"]).first()
    if existente is not None:
        return existente
    if datos["detalle"]:
        datos["detalle"] = str(datos["detalle"])[:255]
    solicitud = SolicitudReembolso(**datos)
    db.add(solicitud)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(SolicitudReembolso).filter(SolicitudReembolso.envio_id == datos["envio_id"]).first()
    db.refresh(solicitud)
    return solicitud


def ejecutar_reembolso(db: Session, pago_id: uuid.UUID, ejecutado_por: Optional[uuid.UUID], nota: Optional[str]) -> Pago:
    pago = db.query(Pago).filter(Pago.id == pago_id).with_for_update().first()
    if pago is None:
        raise ReembolsoError(404, "PAGO_NO_ENCONTRADO", "Pago no encontrado")
    if pago.estado == "reembolsado":
        raise ReembolsoError(409, "PAGO_YA_REEMBOLSADO", "Este pago ya fue reembolsado.")
    if pago.estado != "confirmado":
        raise ReembolsoError(409, "PAGO_NO_REEMBOLSABLE", f"El pago está '{pago.estado}'; solo se reembolsa un pago confirmado.")
    solicitud = db.query(SolicitudReembolso).filter(SolicitudReembolso.envio_id == pago.envio_id).first()
    if solicitud is None:
        raise ReembolsoError(
            409, "PEDIDO_SIN_DEVOLUCION",
            "El pedido no fue cancelado ni devuelto por completo; solo esos pedidos se reembolsan.",
        )

    ahora = datetime.now(timezone.utc)
    pago.estado = "reembolsado"
    pago.reembolsado_en = ahora
    factura = db.query(FacturaPedido).filter(FacturaPedido.pago_id == pago.id).first()
    if factura is not None:
        factura.estado = "anulada"
        factura.anulada_en = ahora
    solicitud.ejecutada_en = ahora
    solicitud.ejecutada_por = ejecutado_por
    solicitud.nota = (nota or "")[:255] or None
    db.commit()
    db.refresh(pago)
    return pago
