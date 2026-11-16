"""Unitaria 1: tarifa_pedido.calcular_monto = base + toneladas x km x tarifa, con mínimo."""
from decimal import Decimal

from app.tarifa_pedido import calcular_monto


def test_calcular_monto_aplica_formula_y_minimo(monkeypatch):
    for nombre in ("TARIFA_MINIMA_COP", "TARIFA_BASE_COP", "TARIFA_COP_POR_TON_KM"):
        monkeypatch.delenv(nombre, raising=False)  # se usan los valores por defecto
    # 20.000 + 0,8 t x 297 km x 280 = 86.528
    assert calcular_monto(800, 297)["monto_cop"] == Decimal("86528.00")
    # un pedido pequeño paga el mínimo
    pequeno = calcular_monto(10, 5)
    assert pequeno["monto_cop"] == Decimal("50000.00") and pequeno["aplico_minimo"] is True
