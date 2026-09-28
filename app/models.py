import uuid
from sqlalchemy import Column, String, Numeric, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from .database import Base


class TarifaCliente(Base):
    __tablename__ = "tarifas_cliente"

    cliente_id = Column(UUID(as_uuid=True), primary_key=True)
    modelo = Column(String, nullable=False, default="por_envio")
    valor = Column(Numeric(12, 2), nullable=False)


class CostoRuta(Base):
    __tablename__ = "costos_ruta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ruta_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    envio_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    distancia_km = Column(Numeric(10, 2), nullable=False, default=0)
    costo_combustible = Column(Numeric(12, 2), nullable=False, default=0)
    costo_peajes = Column(Numeric(12, 2), nullable=False, default=0)
    horas_conductor = Column(Numeric(6, 2), nullable=False, default=0)
    costo_total = Column(Numeric(12, 2), nullable=False, default=0)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())


class Factura(Base):
    __tablename__ = "facturas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    periodo = Column(String(7), nullable=False)  # formato "YYYY-MM"
    monto_total = Column(Numeric(12, 2), nullable=False, default=0)
    estado = Column(String, nullable=False, default="abierta")
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_en = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("cliente_id", "periodo", name="uq_factura_cliente_periodo"),)