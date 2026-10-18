"""Registro del cobro de un pedido (pago simulado + factura del pedido)."""
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import FacturaPedido, Pago


class PayloadInvalido(Exception):
    pass


def registrar_cobro(db: Session, payload: dict) -> Optional[Pago]:
    """Crea, de forma idempotente (un solo pago por envío), el pago simulado confirmado y la factura del
    pedido a partir del evento shipment.created. Si el evento no trae monto no hay nada que cobrar.
    Lanza PayloadInvalido si el evento está mal formado (no tiene sentido reintentarlo)."""
    if payload.get("monto_cop") is None:
        return None
    try:
        envio_id = uuid.UUID(str(payload["envio_id"]))
        cliente_id = uuid.UUID(str(payload["cliente_id"]))
        monto = Decimal(str(payload["monto_cop"]))
    except (KeyError, ValueError, InvalidOperation):
        raise PayloadInvalido("shipment.created sin envio_id, cliente_id o monto_cop válidos")
    if monto <= 0:
        raise PayloadInvalido("monto_cop debe ser mayor que cero")

    existente = db.query(Pago).filter(Pago.envio_id == envio_id).first()
    if existente is not None:
        return existente

    codigo = payload.get("codigo_envio")
    ahora = datetime.now(timezone.utc)
    pago = Pago(
        envio_id=envio_id, codigo_envio=codigo, cliente_id=cliente_id, monto_cop=monto,
        moneda=payload.get("moneda") or "COP", estado="confirmado", metodo="simulado",
        referencia="SIM-" + secrets.token_hex(4).upper(), confirmado_en=ahora,
    )
    db.add(pago)
    try:
        db.flush()
        db.add(FacturaPedido(
            pago_id=pago.id, envio_id=envio_id, codigo_envio=codigo, cliente_id=cliente_id,
            concepto=f"Transporte de carga {codigo or envio_id}" + (
                f" (pedido dividido en {len(payload['partes'])} envíos)" if payload.get("partes") else ""
            ),
            monto_cop=monto, moneda=pago.moneda,
        ))
        db.commit()
    except IntegrityError:
        db.rollback()  # otro consumidor ya lo registró
        return db.query(Pago).filter(Pago.envio_id == envio_id).first()
    db.refresh(pago)
    return pago
