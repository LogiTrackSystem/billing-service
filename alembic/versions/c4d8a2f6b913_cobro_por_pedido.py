"""cobro por pedido: cotizaciones, pagos y facturas_pedido (aditiva)

Revision ID: c4d8a2f6b913
Revises: 88333680000a
Create Date: 2026-10-19 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c4d8a2f6b913'
down_revision: Union[str, Sequence[str], None] = '88333680000a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS seq_factura_pedido START 1")

    op.create_table(
        'cotizaciones',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cliente_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('peso_kg', sa.Numeric(10, 2), nullable=False),
        sa.Column('distancia_km', sa.Numeric(10, 2), nullable=False),
        sa.Column('monto_cop', sa.Numeric(14, 2), nullable=False),
        sa.Column('moneda', sa.String(3), nullable=False),
        sa.Column('base_cop', sa.Numeric(14, 2), nullable=False),
        sa.Column('variable_cop', sa.Numeric(14, 2), nullable=False),
        sa.Column('minimo_cop', sa.Numeric(14, 2), nullable=False),
        sa.Column('aplico_minimo', sa.Boolean(), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cotizaciones_cliente_id', 'cotizaciones', ['cliente_id'])

    op.create_table(
        'pagos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('envio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('codigo_envio', sa.String(20), nullable=True),
        sa.Column('cliente_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('monto_cop', sa.Numeric(14, 2), nullable=False),
        sa.Column('moneda', sa.String(3), nullable=False),
        sa.Column('estado', sa.String(15), nullable=False),
        sa.Column('metodo', sa.String(20), nullable=False),
        sa.Column('referencia', sa.String(30), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('confirmado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reembolsado_en', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("estado IN ('pendiente','confirmado','reembolsado')", name='ck_pagos_estado'),
    )
    op.create_index('ix_pagos_envio_id', 'pagos', ['envio_id'], unique=True)
    op.create_index('ix_pagos_cliente_id', 'pagos', ['cliente_id'])

    op.create_table(
        'facturas_pedido',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('consecutivo', sa.BigInteger(), server_default=sa.text("nextval('seq_factura_pedido')"), nullable=False),
        sa.Column('pago_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('envio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('codigo_envio', sa.String(20), nullable=True),
        sa.Column('cliente_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('concepto', sa.String(255), nullable=False),
        sa.Column('monto_cop', sa.Numeric(14, 2), nullable=False),
        sa.Column('moneda', sa.String(3), nullable=False),
        sa.Column('estado', sa.String(15), nullable=False),
        sa.Column('emitida_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('anulada_en', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['pago_id'], ['pagos.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('consecutivo', name='uq_facturas_pedido_consecutivo'),
        sa.UniqueConstraint('pago_id', name='uq_facturas_pedido_pago'),
        sa.CheckConstraint("estado IN ('emitida','anulada')", name='ck_facturas_pedido_estado'),
    )
    op.create_index('ix_facturas_pedido_envio_id', 'facturas_pedido', ['envio_id'], unique=True)
    op.create_index('ix_facturas_pedido_cliente_id', 'facturas_pedido', ['cliente_id'])


def downgrade() -> None:
    op.drop_table('facturas_pedido')
    op.drop_table('pagos')
    op.drop_table('cotizaciones')
    op.execute("DROP SEQUENCE IF EXISTS seq_factura_pedido")
