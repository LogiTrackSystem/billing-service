"""Precio de un pedido en pesos colombianos (COP), según peso y distancia.

    monto = max(TARIFA_MINIMA_COP, TARIFA_BASE_COP + toneladas × km × TARIFA_COP_POR_TON_KM)

Los tres valores se leen de variables de entorno. Los valores por defecto son de EJEMPLO para el
proyecto académico, no tarifas de mercado.
"""
import os
from decimal import ROUND_HALF_UP, Decimal

MONEDA = "COP"
DEFECTOS = {
    "TARIFA_MINIMA_COP": "50000",
    "TARIFA_BASE_COP": "20000",
    "TARIFA_COP_POR_TON_KM": "280",
}


def parametros() -> dict:
    out = {}
    for nombre, defecto in DEFECTOS.items():
        crudo = os.getenv(nombre, "").strip() or defecto
        try:
            valor = Decimal(crudo)
        except Exception:
            valor = Decimal(defecto)
        out[nombre] = valor if valor >= 0 else Decimal(defecto)
    return out


def _pesos(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))


def calcular_monto(peso_kg, distancia_km) -> dict:
    p = parametros()
    toneladas = Decimal(str(peso_kg)) / Decimal("1000")
    km = Decimal(str(distancia_km))
    variable = toneladas * km * p["TARIFA_COP_POR_TON_KM"]
    bruto = p["TARIFA_BASE_COP"] + variable
    minimo = p["TARIFA_MINIMA_COP"]
    aplico_minimo = bruto < minimo
    return {
        "monto_cop": _pesos(max(bruto, minimo)),
        "moneda": MONEDA,
        "base_cop": _pesos(p["TARIFA_BASE_COP"]),
        "variable_cop": _pesos(variable),
        "minimo_cop": _pesos(minimo),
        "aplico_minimo": aplico_minimo,
        "toneladas": toneladas.quantize(Decimal("0.001")),
        "distancia_km": km,
        "cop_por_ton_km": p["TARIFA_COP_POR_TON_KM"],
    }
