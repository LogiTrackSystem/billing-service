import uuid
from decimal import Decimal as D

import pytest

from app.models import Cotizacion, FacturaPedido, Pago
from app.pedidos import PayloadInvalido, registrar_cobro
from app.tarifa_pedido import calcular_monto

CLIENTE_A, CLIENTE_B = uuid.uuid4(), uuid.uuid4()


@pytest.fixture(autouse=True)
def tarifas_por_defecto(monkeypatch):
    for n in ("TARIFA_MINIMA_COP", "TARIFA_BASE_COP", "TARIFA_COP_POR_TON_KM"):
        monkeypatch.delenv(n, raising=False)


# ---------- fórmula ----------

def test_ejemplo_800_kg_297_km():
    # 20.000 + 0,8 t × 297 km × 280 = 86.528
    c = calcular_monto(800, 297)
    assert c["monto_cop"] == D("86528.00") and c["moneda"] == "COP" and c["aplico_minimo"] is False
    assert c["variable_cop"] == D("66528.00")


def test_aplica_el_minimo_en_pedidos_pequenos():
    c = calcular_monto(10, 5)       # 20.000 + 0,01 × 5 × 280 = 20.014 < 50.000
    assert c["monto_cop"] == D("50000.00") and c["aplico_minimo"] is True


def test_el_precio_crece_con_el_peso_y_con_la_distancia():
    assert calcular_monto(2000, 300)["monto_cop"] > calcular_monto(1000, 300)["monto_cop"]
    assert calcular_monto(1000, 600)["monto_cop"] > calcular_monto(1000, 300)["monto_cop"]


def test_dividir_la_carga_no_cambia_el_precio_total():
    # 1200 kg en una sola cotización vs. la suma de las dos partes (1000 + 200) menos un cargo base
    total = calcular_monto(1200, 300)["variable_cop"]
    assert calcular_monto(1000, 300)["variable_cop"] + calcular_monto(200, 300)["variable_cop"] == total


def test_los_parametros_se_leen_del_entorno(monkeypatch):
    monkeypatch.setenv("TARIFA_BASE_COP", "0")
    monkeypatch.setenv("TARIFA_MINIMA_COP", "0")
    monkeypatch.setenv("TARIFA_COP_POR_TON_KM", "1000")
    assert calcular_monto(1000, 10)["monto_cop"] == D("10000.00")


def test_un_valor_de_entorno_invalido_usa_el_defecto(monkeypatch):
    monkeypatch.setenv("TARIFA_COP_POR_TON_KM", "abc")
    assert calcular_monto(800, 297)["monto_cop"] == D("86528.00")


# ---------- cotizaciones ----------

def test_calcular_registra_la_cotizacion_y_devuelve_el_desglose(api, db):
    r = api.post("/cotizaciones/calcular", json={"peso_kg": 800, "distancia_km": 297, "cliente_id": str(CLIENTE_A)})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["monto_cop"] == 86528 and d["moneda"] == "COP"
    assert d["desglose"]["base_cop"] == 20000 and d["desglose"]["variable_cop"] == 66528 and d["desglose"]["toneladas"] == 0.8
    assert db.query(Cotizacion).count() == 1


@pytest.mark.parametrize("cuerpo", [{"peso_kg": 0, "distancia_km": 10}, {"peso_kg": -5, "distancia_km": 10}, {"peso_kg": 10, "distancia_km": -1}, {"distancia_km": 10}])
def test_calcular_rechaza_datos_invalidos(api, cuerpo):
    assert api.post("/cotizaciones/calcular", json=cuerpo).status_code == 422


def test_cotizaciones_del_cliente_solo_las_propias(api):
    api.post("/cotizaciones/calcular", json={"peso_kg": 100, "distancia_km": 10, "cliente_id": str(CLIENTE_A)})
    api.post("/cotizaciones/calcular", json={"peso_kg": 100, "distancia_km": 10, "cliente_id": str(CLIENTE_B)})
    h = {"x-cliente-id": str(CLIENTE_A)}
    assert len(api.get("/cotizaciones/", headers=h).json()) == 1
    assert len(api.get(f"/cotizaciones/?cliente_id={CLIENTE_B}", headers=h).json()) == 1   # se ignora lo que pida
    assert api.get(f"/cotizaciones/?cliente_id={CLIENTE_B}", headers=h).json()[0]["cliente_id"] == str(CLIENTE_A)
    assert len(api.get("/cotizaciones/").json()) == 2


# ---------- cobro del pedido ----------

def evento(**extra):
    base = {"envio_id": str(uuid.uuid4()), "codigo_envio": "ENV-00000032", "cliente_id": str(CLIENTE_A), "monto_cop": 86528.0}
    return {**base, **extra}


def test_shipment_created_con_monto_registra_pago_confirmado_y_factura(db):
    p = registrar_cobro(db, evento())
    assert p.estado == "confirmado" and p.metodo == "simulado" and p.monto_cop == D("86528") and p.referencia.startswith("SIM-")
    assert p.confirmado_en is not None
    f = db.query(FacturaPedido).one()
    assert f.pago_id == p.id and f.monto_cop == D("86528") and f.estado == "emitida" and f.numero.startswith("FP-")


def test_es_idempotente_un_solo_pago_y_una_factura_por_envio(db):
    ev = evento()
    a, b = registrar_cobro(db, ev), registrar_cobro(db, ev)
    assert a.id == b.id and db.query(Pago).count() == 1 and db.query(FacturaPedido).count() == 1


def test_sin_monto_no_se_cobra(db):
    assert registrar_cobro(db, {"envio_id": str(uuid.uuid4()), "cliente_id": str(CLIENTE_A)}) is None
    assert db.query(Pago).count() == 0


@pytest.mark.parametrize("malo", [{"monto_cop": 0}, {"monto_cop": -10}, {"monto_cop": "abc"}, {"cliente_id": "no-es-uuid"}])
def test_evento_mal_formado_se_rechaza_sin_crear_nada(db, malo):
    with pytest.raises(PayloadInvalido):
        registrar_cobro(db, evento(**malo))
    assert db.query(Pago).count() == 0 and db.query(FacturaPedido).count() == 0


def test_las_facturas_se_numeran_en_orden(db):
    a = registrar_cobro(db, evento()); b = registrar_cobro(db, evento())
    fa = db.query(FacturaPedido).filter_by(pago_id=a.id).one(); fb = db.query(FacturaPedido).filter_by(pago_id=b.id).one()
    assert fb.consecutivo == fa.consecutivo + 1


# ---------- consulta y propiedad ----------

def test_cliente_solo_ve_sus_pagos_y_facturas(api, db):
    propio = registrar_cobro(db, evento())
    ajeno = registrar_cobro(db, evento(cliente_id=str(CLIENTE_B)))
    h = {"x-cliente-id": str(CLIENTE_A)}
    assert [x["id"] for x in api.get("/pagos/", headers=h).json()] == [str(propio.id)]
    assert api.get(f"/pagos/{propio.id}", headers=h).status_code == 200
    assert api.get(f"/pagos/{ajeno.id}", headers=h).status_code == 404
    assert api.get(f"/pagos/envio/{ajeno.envio_id}", headers=h).status_code == 404
    assert len(api.get("/facturas-pedido/", headers=h).json()) == 1
    assert api.get(f"/facturas-pedido/envio/{propio.envio_id}", headers=h).status_code == 200
    assert api.get(f"/facturas-pedido/envio/{ajeno.envio_id}", headers=h).status_code == 404
    factura_ajena = db.query(FacturaPedido).filter_by(pago_id=ajeno.id).one()
    assert api.get(f"/facturas-pedido/{factura_ajena.id}", headers=h).status_code == 404


def test_personal_ve_todo_y_filtra(api, db):
    registrar_cobro(db, evento()); registrar_cobro(db, evento(cliente_id=str(CLIENTE_B)))
    assert len(api.get("/pagos/").json()) == 2
    assert len(api.get(f"/pagos/?cliente_id={CLIENTE_B}").json()) == 1
    assert len(api.get("/pagos/?estado=reembolsado").json()) == 0
    f = api.get("/facturas-pedido/").json()[0]
    assert f["numero"].startswith("FP-") and f["moneda"] == "COP"


def test_identidad_de_cliente_invalida_es_403(api):
    assert api.get("/pagos/", headers={"x-cliente-id": "basura"}).status_code == 403


def test_pedido_dividido_se_cobra_una_vez_con_el_monto_del_pedido(db):
    pedido = evento(partes=[{"codigo_envio": "ENV-00000032-P1"}, {"codigo_envio": "ENV-00000032-P2"}])
    p = registrar_cobro(db, pedido)
    f = db.query(FacturaPedido).one()
    assert p.monto_cop == D("86528") and "dividido en 2 envíos" in f.concepto
    # las partes se anuncian sin monto: no generan cobro
    assert registrar_cobro(db, {"envio_id": str(uuid.uuid4()), "cliente_id": str(CLIENTE_A), "monto_cop": None}) is None
    assert db.query(Pago).count() == 1


def test_pagos_y_facturas_se_paginan_con_offset_sin_repetir_ni_perder(api, db):
    """Analytics recorre /pagos y /facturas-pedido por páginas para calcular ingresos."""
    for _ in range(5):
        registrar_cobro(db, evento())
    for ruta in ("/pagos/", "/facturas-pedido/"):
        p1 = api.get(ruta, params={"limite": 2, "offset": 0}).json()
        p2 = api.get(ruta, params={"limite": 2, "offset": 2}).json()
        p3 = api.get(ruta, params={"limite": 2, "offset": 4}).json()
        ids = [x["id"] for x in p1 + p2 + p3]
        assert len(p1) == 2 and len(p2) == 2 and len(p3) == 1
        assert len(set(ids)) == 5
    assert api.get("/pagos/", params={"offset": -1}).status_code == 422
