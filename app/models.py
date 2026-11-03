import uuid
from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Numeric, String, UniqueConstraint, text
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


# ---------- Cobro por pedido (aditivo: las tablas anteriores no se tocan) ----------

class Cotizacion(Base):
    """Precio calculado para un pedido, en pesos colombianos (COP)."""
    __tablename__ = "cotizaciones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    peso_kg = Column(Numeric(10, 2), nullable=False)
    distancia_km = Column(Numeric(10, 2), nullable=False)
    monto_cop = Column(Numeric(14, 2), nullable=False)
    moneda = Column(String(3), nullable=False, default="COP")
    base_cop = Column(Numeric(14, 2), nullable=False)
    variable_cop = Column(Numeric(14, 2), nullable=False)
    minimo_cop = Column(Numeric(14, 2), nullable=False)
    aplico_minimo = Column(Boolean, nullable=False, default=False)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())


class Pago(Base):
    """Pago de un pedido. Simulado: aceptar el precio al crear el pedido lo deja 'confirmado'.
    Estados: pendiente | confirmado | reembolsado. Un pedido solo figura pagado si su pago está confirmado."""
    __tablename__ = "pagos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envio_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    codigo_envio = Column(String(20), nullable=True)
    cliente_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    monto_cop = Column(Numeric(14, 2), nullable=False)
    moneda = Column(String(3), nullable=False, default="COP")
    estado = Column(String(15), nullable=False, default="pendiente")
    metodo = Column(String(20), nullable=False, default="simulado")
    referencia = Column(String(30), nullable=True)
    creado_en = Column(DateTime(timezone=True), server_default=func.now())
    confirmado_en = Column(DateTime(timezone=True), nullable=True)
    reembolsado_en = Column(DateTime(timezone=True), nullable=True)


class FacturaPedido(Base):
    """Factura de un solo pedido (la mensual de arriba sigue existiendo aparte)."""
    __tablename__ = "facturas_pedido"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    consecutivo = Column(BigInteger, server_default=text("nextval('seq_factura_pedido')"), unique=True, nullable=False)
    pago_id = Column(UUID(as_uuid=True), ForeignKey("pagos.id"), nullable=False, unique=True)
    envio_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)
    codigo_envio = Column(String(20), nullable=True)
    cliente_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    concepto = Column(String(255), nullable=False)
    monto_cop = Column(Numeric(14, 2), nullable=False)
    moneda = Column(String(3), nullable=False, default="COP")
    estado = Column(String(15), nullable=False, default="emitida")  # emitida | anulada
    emitida_en = Column(DateTime(timezone=True), server_default=func.now())
    anulada_en = Column(DateTime(timezone=True), nullable=True)

    @property
    def numero(self):
        return f"FP-{self.consecutivo:08d}" if self.consecutivo is not None else None


class SolicitudReembolso(Base):
    """Un pedido pagado que se canceló o se devolvió y por lo tanto puede reembolsarse.
    La registra Billing al recibir shipment.cancelled / shipment.returned; el reembolso en sí
    (pago -> 'reembolsado', factura -> 'anulada') lo ejecuta un administrador. Simulado: no mueve dinero."""
    __tablename__ = "solicitudes_reembolso"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    envio_id = Column(UUID(as_uuid=True), nullable=False, unique=True, index=True)  # el pedido (padre si está dividido)
    codigo_envio = Column(String(20), nullable=True)
    cliente_id = Column(UUID(as_uuid=True), nullable=True)
    monto_cop = Column(Numeric(14, 2), nullable=True)
    motivo = Column(String(15), nullable=False)  # cancelado | devuelto
    detalle = Column(String(255), nullable=True)
    registrada_en = Column(DateTime(timezone=True), server_default=func.now())
    ejecutada_en = Column(DateTime(timezone=True), nullable=True)
    ejecutada_por = Column(UUID(as_uuid=True), nullable=True)
    nota = Column(String(255), nullable=True)
