"""Integración: evento shipment.created -> cobro registrado -> pago y factura visibles por API."""
import uuid

from app.pedidos import registrar_cobro


def test_cobro_registrado_se_consulta_como_pago_y_factura(api, db):
    # Arrange / Act: llega el evento de un envío con monto
    envio_id = str(uuid.uuid4())
    registrar_cobro(db, {"envio_id": envio_id, "cliente_id": str(uuid.uuid4()), "monto_cop": "86528", "codigo_envio": "ENV-1"})
    pago = api.get(f"/pagos/envio/{envio_id}")
    factura = api.get(f"/facturas-pedido/envio/{envio_id}")
    # Assert
    assert pago.status_code == 200 and pago.json()["estado"] == "confirmado"
    assert factura.status_code == 200 and factura.json()["codigo_envio"] == "ENV-1"
    assert api.get(f"/pagos/envio/{uuid.uuid4()}").status_code == 404
