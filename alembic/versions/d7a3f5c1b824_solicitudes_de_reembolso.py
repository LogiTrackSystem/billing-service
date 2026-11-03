"""solicitudes de reembolso (devoluciones y cancelaciones de pedidos cobrados)

Revision ID: d7a3f5c1b824
Revises: c4d8a2f6b913
Create Date: 2026-10-19 12:00:00.000000

Solo agrega una tabla nueva. No modifica pagos ni facturas existentes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd7a3f5c1b824'
down_revision: Union[str, Sequence[str], None] = 'c4d8a2f6b913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'solicitudes_reembolso',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('envio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('codigo_envio', sa.String(length=20), nullable=True),
        sa.Column('cliente_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('monto_cop', sa.Numeric(14, 2), nullable=True),
        sa.Column('motivo', sa.String(length=15), nullable=False),
        sa.Column('detalle', sa.String(length=255), nullable=True),
        sa.Column('registrada_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('ejecutada_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ejecutada_por', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('nota', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_solicitudes_reembolso_envio_id'), 'solicitudes_reembolso', ['envio_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_solicitudes_reembolso_envio_id'), table_name='solicitudes_reembolso')
    op.drop_table('solicitudes_reembolso')
