-- Esquema de billing_db (billing-service): SQL generado por 'alembic upgrade head --sql' a partir de alembic/versions.
-- Crea todas las tablas, secuencias y restricciones. No contiene datos.
BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 88333680000a

CREATE TABLE costos_ruta (
    id UUID NOT NULL, 
    ruta_id UUID NOT NULL, 
    envio_id UUID NOT NULL, 
    distancia_km NUMERIC(10, 2) NOT NULL, 
    costo_combustible NUMERIC(12, 2) NOT NULL, 
    costo_peajes NUMERIC(12, 2) NOT NULL, 
    horas_conductor NUMERIC(6, 2) NOT NULL, 
    costo_total NUMERIC(12, 2) NOT NULL, 
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE INDEX ix_costos_ruta_envio_id ON costos_ruta (envio_id);

CREATE UNIQUE INDEX ix_costos_ruta_ruta_id ON costos_ruta (ruta_id);

CREATE TABLE facturas (
    id UUID NOT NULL, 
    cliente_id UUID NOT NULL, 
    periodo VARCHAR(7) NOT NULL, 
    monto_total NUMERIC(12, 2) NOT NULL, 
    estado VARCHAR NOT NULL, 
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id), 
    CONSTRAINT uq_factura_cliente_periodo UNIQUE (cliente_id, periodo)
);

CREATE INDEX ix_facturas_cliente_id ON facturas (cliente_id);

CREATE TABLE tarifas_cliente (
    cliente_id UUID NOT NULL, 
    modelo VARCHAR NOT NULL, 
    valor NUMERIC(12, 2) NOT NULL, 
    PRIMARY KEY (cliente_id)
);

INSERT INTO alembic_version (version_num) VALUES ('88333680000a') RETURNING alembic_version.version_num;

-- Running upgrade 88333680000a -> c4d8a2f6b913

CREATE SEQUENCE IF NOT EXISTS seq_factura_pedido START 1;

CREATE TABLE cotizaciones (
    id UUID NOT NULL, 
    cliente_id UUID, 
    peso_kg NUMERIC(10, 2) NOT NULL, 
    distancia_km NUMERIC(10, 2) NOT NULL, 
    monto_cop NUMERIC(14, 2) NOT NULL, 
    moneda VARCHAR(3) NOT NULL, 
    base_cop NUMERIC(14, 2) NOT NULL, 
    variable_cop NUMERIC(14, 2) NOT NULL, 
    minimo_cop NUMERIC(14, 2) NOT NULL, 
    aplico_minimo BOOLEAN NOT NULL, 
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    PRIMARY KEY (id)
);

CREATE INDEX ix_cotizaciones_cliente_id ON cotizaciones (cliente_id);

CREATE TABLE pagos (
    id UUID NOT NULL, 
    envio_id UUID NOT NULL, 
    codigo_envio VARCHAR(20), 
    cliente_id UUID NOT NULL, 
    monto_cop NUMERIC(14, 2) NOT NULL, 
    moneda VARCHAR(3) NOT NULL, 
    estado VARCHAR(15) NOT NULL, 
    metodo VARCHAR(20) NOT NULL, 
    referencia VARCHAR(30), 
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    confirmado_en TIMESTAMP WITH TIME ZONE, 
    reembolsado_en TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_pagos_estado CHECK (estado IN ('pendiente','confirmado','reembolsado'))
);

CREATE UNIQUE INDEX ix_pagos_envio_id ON pagos (envio_id);

CREATE INDEX ix_pagos_cliente_id ON pagos (cliente_id);

CREATE TABLE facturas_pedido (
    id UUID NOT NULL, 
    consecutivo BIGINT DEFAULT nextval('seq_factura_pedido') NOT NULL, 
    pago_id UUID NOT NULL, 
    envio_id UUID NOT NULL, 
    codigo_envio VARCHAR(20), 
    cliente_id UUID NOT NULL, 
    concepto VARCHAR(255) NOT NULL, 
    monto_cop NUMERIC(14, 2) NOT NULL, 
    moneda VARCHAR(3) NOT NULL, 
    estado VARCHAR(15) NOT NULL, 
    emitida_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    anulada_en TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(pago_id) REFERENCES pagos (id), 
    CONSTRAINT uq_facturas_pedido_consecutivo UNIQUE (consecutivo), 
    CONSTRAINT uq_facturas_pedido_pago UNIQUE (pago_id), 
    CONSTRAINT ck_facturas_pedido_estado CHECK (estado IN ('emitida','anulada'))
);

CREATE UNIQUE INDEX ix_facturas_pedido_envio_id ON facturas_pedido (envio_id);

CREATE INDEX ix_facturas_pedido_cliente_id ON facturas_pedido (cliente_id);

UPDATE alembic_version SET version_num='c4d8a2f6b913' WHERE alembic_version.version_num = '88333680000a';

-- Running upgrade c4d8a2f6b913 -> d7a3f5c1b824

CREATE TABLE solicitudes_reembolso (
    id UUID NOT NULL, 
    envio_id UUID NOT NULL, 
    codigo_envio VARCHAR(20), 
    cliente_id UUID, 
    monto_cop NUMERIC(14, 2), 
    motivo VARCHAR(15) NOT NULL, 
    detalle VARCHAR(255), 
    registrada_en TIMESTAMP WITH TIME ZONE DEFAULT now(), 
    ejecutada_en TIMESTAMP WITH TIME ZONE, 
    ejecutada_por UUID, 
    nota VARCHAR(255), 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_solicitudes_reembolso_envio_id ON solicitudes_reembolso (envio_id);

UPDATE alembic_version SET version_num='d7a3f5c1b824' WHERE alembic_version.version_num = 'c4d8a2f6b913';

COMMIT;

