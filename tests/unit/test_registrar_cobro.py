"""Unitaria 2: pedidos.registrar_cobro crea pago y factura, y es idempotente por envío."""
import uuid

from app.models import FacturaPedido, Pago
from app.pedidos import registrar_cobro


def test_registrar_cobro_crea_pago_y_factura_una_sola_vez(db):
    payload = {"envio_id": str(uuid.uuid4()), "cliente_id": str(uuid.uuid4()), "monto_cop": "86528"}
    registrar_cobro(db, payload)
    registrar_cobro(db, payload)  # mismo evento repetido
    assert db.query(Pago).count() == 1 and db.query(FacturaPedido).count() == 1
    assert db.query(Pago).one().estado == "confirmado"
