import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


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


# ---------- Cobro por pedido ----------

class CotizacionSolicitud(BaseModel):
    peso_kg: Decimal = Field(..., gt=0)
    distancia_km: Decimal = Field(..., ge=0)
    cliente_id: Optional[uuid.UUID] = None


class CotizacionLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cliente_id: Optional[uuid.UUID] = None
    peso_kg: Decimal
    distancia_km: Decimal
    monto_cop: Decimal
    moneda: str
    base_cop: Decimal
    variable_cop: Decimal
    minimo_cop: Decimal
    aplico_minimo: bool
    creado_en: datetime


class PagoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    envio_id: uuid.UUID
    codigo_envio: Optional[str] = None
    cliente_id: uuid.UUID
    monto_cop: Decimal
    moneda: str
    estado: str
    metodo: str
    referencia: Optional[str] = None
    creado_en: datetime
    confirmado_en: Optional[datetime] = None
    reembolsado_en: Optional[datetime] = None


class FacturaPedidoLeer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero: Optional[str] = None
    pago_id: uuid.UUID
    envio_id: uuid.UUID
    codigo_envio: Optional[str] = None
    cliente_id: uuid.UUID
    concepto: str
    monto_cop: Decimal
    moneda: str
    estado: str
    emitida_en: datetime
    anulada_en: Optional[datetime] = None


class ReembolsoCrear(BaseModel):
    nota: Optional[str] = Field(default=None, max_length=255)


class PagoPorReembolsar(PagoLeer):
    motivo: str  # cancelado | devuelto
    detalle: Optional[str] = None
    solicitado_en: Optional[datetime] = None
