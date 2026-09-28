import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TarifaClienteCrear(BaseModel):
    cliente_id: uuid.UUID
    modelo: str  # "por_km" | "por_envio" | "tarifa_plana"
    valor: Decimal


class TarifaClienteLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cliente_id: uuid.UUID
    modelo: str
    valor: Decimal


class CostoRutaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ruta_id: uuid.UUID
    envio_id: uuid.UUID
    distancia_km: Decimal
    costo_combustible: Decimal
    costo_peajes: Decimal
    horas_conductor: Decimal
    costo_total: Decimal
    creado_en: datetime


class FacturaLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cliente_id: uuid.UUID
    periodo: str
    monto_total: Decimal
    estado: str
    creado_en: datetime
    actualizado_en: datetime