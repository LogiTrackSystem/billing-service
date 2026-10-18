"""Devoluciones y cancelaciones: solicitud automática y reembolso simulado ejecutado por el administrador."""
import uuid
from decimal import Decimal as D

import pytest

from app.models import FacturaPedido, Pago, SolicitudReembolso
from app.pedidos import PayloadInvalido, registrar_cobro
from app.reembolsos import registrar_solicitud, solicitud_desde_evento

CLIENTE = uuid.uuid4()
ADMIN = {"x-user-id": str(uuid.uuid4()), "x-user-rol": "administrador"}


def cobrar(db, monto=86528.0, **extra):
    envio_id = str(uuid.uuid4())
    pago = registrar_cobro(db, {"envio_id": envio_id, "codigo_envio": "ENV-00000032", "cliente_id": str(CLIENTE),
                                "monto_cop": monto, **extra})
    return envio_id, pago


def cancelado(envio_id, monto=86528.0, **extra):
    return {"envio_id": envio_id, "codigo_envio": "ENV-00000032", "cliente_id": str(CLIENTE),
            "estado_anterior": "pendiente", "motivo": "cliente desistió", "monto_cop": monto, **extra}


def devuelto(envio_id, **extra):
    base = {"envio_id": envio_id, "codigo_envio": "ENV-00000032", "cliente_id": str(CLIENTE), "notas": "dirección cerrada",
            "envio_padre_id": None, "pedido_id": envio_id, "pedido_codigo": "ENV-00000032",
            "pedido_devuelto": True, "pedido_monto_cop": 86528.0}
    return {**base, **extra}


# ---------- interpretación de los eventos ----------

def test_cancelado_con_monto_genera_solicitud(db):
    envio_id, _ = cobrar(db)
    s = registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    assert s.motivo == "cancelado" and str(s.envio_id) == envio_id and s.monto_cop == D("86528") and s.detalle == "cliente desistió"


def test_una_parte_cancelada_sin_monto_no_genera_solicitud(db):
    assert registrar_solicitud(db, "shipment.cancelled", cancelado(str(uuid.uuid4()), monto=None)) is None
    assert db.query(SolicitudReembolso).count() == 0


def test_devuelto_completo_genera_solicitud_del_pedido_no_de_la_parte(db):
    padre, parte = str(uuid.uuid4()), str(uuid.uuid4())
    s = registrar_solicitud(db, "shipment.returned", devuelto(parte, envio_padre_id=padre, pedido_id=padre))
    assert s.motivo == "devuelto" and str(s.envio_id) == padre


@pytest.mark.parametrize("extra", [{"pedido_devuelto": False}, {"pedido_monto_cop": None}])
def test_devolucion_parcial_o_sin_cobro_no_genera_solicitud(db, extra):
    assert registrar_solicitud(db, "shipment.returned", devuelto(str(uuid.uuid4()), **extra)) is None


def test_evento_antiguo_sin_campos_de_pedido_se_ignora(db):
    """Un shipment.returned del formato anterior (solo envio_id y notas) no rompe nada."""
    assert registrar_solicitud(db, "shipment.returned", {"envio_id": str(uuid.uuid4()), "notas": "x"}) is None


def test_es_idempotente(db):
    envio_id, _ = cobrar(db)
    a = registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    b = registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    assert a.id == b.id and db.query(SolicitudReembolso).count() == 1


@pytest.mark.parametrize("malo", [cancelado("no-es-uuid"), cancelado(str(uuid.uuid4()), cliente_id="x"),
                                   cancelado(str(uuid.uuid4()), monto="abc")])
def test_evento_mal_formado_se_rechaza_sin_crear_nada(db, malo):
    with pytest.raises(PayloadInvalido):
        registrar_solicitud(db, "shipment.cancelled", malo)
    assert db.query(SolicitudReembolso).count() == 0


def test_evento_de_otro_tipo_se_ignora(db):
    assert solicitud_desde_evento("shipment.delivered", {"envio_id": str(uuid.uuid4())}) is None


# ---------- reembolso (administrador) ----------

def test_reembolso_de_pedido_cancelado_anula_la_factura(api, db):
    envio_id, pago = cobrar(db)
    registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    r = api.post(f"/pagos/{pago.id}/reembolsar", json={"nota": "autorizado por finanzas"}, headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "reembolsado" and r.json()["reembolsado_en"] is not None
    db.expire_all()
    f = db.query(FacturaPedido).one()
    assert f.estado == "anulada" and f.anulada_en is not None
    s = db.query(SolicitudReembolso).one()
    assert s.ejecutada_en is not None and str(s.ejecutada_por) == ADMIN["x-user-id"] and s.nota == "autorizado por finanzas"


def test_reembolso_sin_cuerpo_tambien_funciona(api, db):
    envio_id, pago = cobrar(db)
    registrar_solicitud(db, "shipment.returned", devuelto(envio_id))
    assert api.post(f"/pagos/{pago.id}/reembolsar").status_code == 200


def test_no_se_reembolsa_un_pedido_que_no_fue_cancelado_ni_devuelto(api, db):
    _, pago = cobrar(db)
    r = api.post(f"/pagos/{pago.id}/reembolsar", headers=ADMIN)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "PEDIDO_SIN_DEVOLUCION"
    db.expire_all()
    assert db.query(Pago).one().estado == "confirmado" and db.query(FacturaPedido).one().estado == "emitida"


def test_no_se_reembolsa_dos_veces(api, db):
    envio_id, pago = cobrar(db)
    registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    assert api.post(f"/pagos/{pago.id}/reembolsar", headers=ADMIN).status_code == 200
    r = api.post(f"/pagos/{pago.id}/reembolsar", headers=ADMIN)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "PAGO_YA_REEMBOLSADO"


def test_pago_pendiente_no_se_reembolsa(api, db):
    envio_id, pago = cobrar(db)
    pago.estado = "pendiente"; db.commit()
    registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    r = api.post(f"/pagos/{pago.id}/reembolsar", headers=ADMIN)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "PAGO_NO_REEMBOLSABLE"


def test_pago_inexistente_es_404(api):
    r = api.post(f"/pagos/{uuid.uuid4()}/reembolsar", headers=ADMIN)
    assert r.status_code == 404 and r.json()["detail"]["codigo"] == "PAGO_NO_ENCONTRADO"


def test_la_solicitud_puede_llegar_antes_que_el_pago(api, db):
    """Cancelar justo después de crear: si la solicitud se registra primero, el reembolso funciona al aparecer el pago."""
    envio_id = str(uuid.uuid4())
    registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    pago = registrar_cobro(db, {"envio_id": envio_id, "cliente_id": str(CLIENTE), "monto_cop": 86528.0})
    assert api.post(f"/pagos/{pago.id}/reembolsar", headers=ADMIN).status_code == 200


def test_lista_de_pagos_por_reembolsar(api, db):
    e1, p1 = cobrar(db)
    e2, p2 = cobrar(db)
    cobrar(db)                                                 # sin devolución: no aparece
    registrar_solicitud(db, "shipment.cancelled", cancelado(e1))
    registrar_solicitud(db, "shipment.returned", devuelto(e2))
    lista = api.get("/pagos/por-reembolsar").json()
    assert {x["id"] for x in lista} == {str(p1.id), str(p2.id)}
    assert {x["motivo"] for x in lista} == {"cancelado", "devuelto"}
    api.post(f"/pagos/{p1.id}/reembolsar", headers=ADMIN)
    assert [x["id"] for x in api.get("/pagos/por-reembolsar").json()] == [str(p2.id)]   # ya reembolsado sale de la lista


def test_el_reembolso_aparece_en_el_listado_de_pagos_del_cliente(api, db):
    envio_id, pago = cobrar(db)
    registrar_solicitud(db, "shipment.cancelled", cancelado(envio_id))
    api.post(f"/pagos/{pago.id}/reembolsar", headers=ADMIN)
    propio = api.get("/pagos/", headers={"x-cliente-id": str(CLIENTE)}).json()
    assert propio[0]["estado"] == "reembolsado"
    facturas = api.get("/facturas-pedido/", headers={"x-cliente-id": str(CLIENTE)}).json()
    assert facturas[0]["estado"] == "anulada"


# ---------- consumidor RabbitMQ ----------

class MensajeFalso:
    """Imita aio_pika.IncomingMessage lo justo para probar el consumidor sin RabbitMQ."""
    def __init__(self, clave, cuerpo):
        import json
        self.routing_key, self.body, self.requeue = clave, json.dumps(cuerpo).encode(), None

    def process(self, requeue=False):
        mensaje = self

        class Ctx:
            async def __aenter__(self):
                mensaje.requeue = requeue
                return mensaje

            async def __aexit__(self, *a):
                return False
        return Ctx()


def test_el_consumidor_registra_la_solicitud_y_descarta_lo_mal_formado(db, monkeypatch, capsys):
    import asyncio
    from app import events
    monkeypatch.setattr(events, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    envio_id, _ = cobrar(db)

    msg = MensajeFalso("shipment.cancelled", cancelado(envio_id))
    asyncio.run(events._on_cierre_de_pedido(msg))
    assert msg.requeue is True and db.query(SolicitudReembolso).count() == 1

    asyncio.run(events._on_cierre_de_pedido(MensajeFalso("shipment.cancelled", cancelado("no-es-uuid"))))   # no revienta
    assert "descartado" in capsys.readouterr().out and db.query(SolicitudReembolso).count() == 1

    envio2, _ = cobrar(db)
    asyncio.run(events._on_cierre_de_pedido(MensajeFalso("shipment.returned", devuelto(envio2))))
    assert db.query(SolicitudReembolso).count() == 2
