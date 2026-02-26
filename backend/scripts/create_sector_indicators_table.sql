-- Migracion: Crear tabla indicadores_sector
-- Fecha: 2026-02-25
-- Descripcion: Indicadores especificos del sector para proyectos

CREATE TABLE IF NOT EXISTS indicadores_sector (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proyecto_id UUID NOT NULL UNIQUE REFERENCES proyectos(id) ON DELETE CASCADE,

    -- Indicadores Tecnologia/SaaS
    ltv_cac_ratio NUMERIC(10, 4),
    burn_rate NUMERIC(18, 2),
    runway_meses INTEGER,
    mrr NUMERIC(18, 2),
    arr NUMERIC(18, 2),
    churn_rate NUMERIC(7, 4),
    nps INTEGER,

    -- Indicadores Inmobiliario
    cap_rate NUMERIC(7, 4),
    precio_m2 NUMERIC(18, 2),
    yield_bruto NUMERIC(7, 4),
    yield_neto NUMERIC(7, 4),
    loan_to_value NUMERIC(7, 4),
    debt_service_coverage NUMERIC(7, 4),

    -- Indicadores Energia
    lcoe NUMERIC(18, 4),
    factor_capacidad NUMERIC(7, 4),
    ingresos_kwh NUMERIC(10, 4),
    costo_instalacion_kw NUMERIC(18, 2),
    vida_util_anos INTEGER,

    -- Indicadores Fintech
    take_rate NUMERIC(7, 4),
    volumen_procesado NUMERIC(18, 2),
    costo_adquisicion NUMERIC(18, 2),
    lifetime_value NUMERIC(18, 2),
    default_rate NUMERIC(7, 4),

    -- Indicadores Comercio/Industrial
    margen_bruto NUMERIC(7, 4),
    margen_operativo NUMERIC(7, 4),
    rotacion_inventario NUMERIC(7, 2),
    ticket_promedio NUMERIC(18, 2),
    conversion_rate NUMERIC(7, 4),
    ventas_m2 NUMERIC(18, 2),
    utilizacion_capacidad NUMERIC(7, 4),
    costo_unitario NUMERIC(18, 4),
    punto_equilibrio_unidades INTEGER,

    -- Indicadores Agrotech
    rendimiento_hectarea NUMERIC(18, 4),
    costo_produccion_ton NUMERIC(18, 2),
    punto_equilibrio NUMERIC(18, 2),

    -- Indicadores Infraestructura
    eirr NUMERIC(7, 4),
    firr NUMERIC(7, 4),
    beneficio_costo_ratio NUMERIC(7, 4),
    trafico_proyectado INTEGER,
    tarifa_promedio NUMERIC(18, 2),

    -- Indicadores Servicios
    rotacion_clientes NUMERIC(7, 4),

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Indice para busqueda por proyecto
CREATE INDEX IF NOT EXISTS idx_indicadores_sector_proyecto ON indicadores_sector(proyecto_id);

-- Comentario de tabla
COMMENT ON TABLE indicadores_sector IS 'Indicadores especificos del sector para cada proyecto de inversion';
