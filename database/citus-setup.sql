-- FinCore - Configuración Citus para Escalabilidad Distribuida
-- Este script se ejecuta después de init.sql

-- Habilitar extensión Citus
CREATE EXTENSION IF NOT EXISTS citus;

-- ===========================================
-- TABLAS DISTRIBUIDAS (Sharding por user_id o project_id)
-- ===========================================

-- Las tablas de alto volumen se distribuyen horizontalmente
-- Esto permite escalar agregando más nodos worker

-- Nota: Las tablas deben existir antes de distribuirlas
-- Este script asume que las migraciones ya crearon las tablas

-- Función para distribuir tablas de forma segura
CREATE OR REPLACE FUNCTION safe_distribute_table(
    table_name text,
    distribution_column text
) RETURNS void AS $$
BEGIN
    -- Verificar si la tabla existe y no está distribuida
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = safe_distribute_table.table_name
    ) AND NOT EXISTS (
        SELECT 1 FROM citus_tables
        WHERE table_name::text = safe_distribute_table.table_name
    ) THEN
        EXECUTE format('SELECT create_distributed_table(%L, %L)', table_name, distribution_column);
        RAISE NOTICE 'Tabla % distribuida por columna %', table_name, distribution_column;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ===========================================
-- DISTRIBUCIÓN DE TABLAS PRINCIPALES
-- ===========================================

-- Inversiones: distribuidas por user_id (cada usuario ve sus inversiones)
SELECT safe_distribute_table('inversiones', 'usuario_id');

-- Transacciones: distribuidas por investment_id
SELECT safe_distribute_table('transacciones_inversion', 'inversion_id');

-- Ledger inmutable: distribuido por secuencia (balanceado)
SELECT safe_distribute_table('immutable_ledger', 'user_id');

-- Flujos de caja: distribuidos por project_id
SELECT safe_distribute_table('flujos_caja_proyectados', 'proyecto_id');

-- Evaluaciones financieras: distribuidas por project_id
SELECT safe_distribute_table('evaluaciones_financieras', 'proyecto_id');

-- Análisis de sensibilidad: distribuidos por project_id
SELECT safe_distribute_table('analisis_sensibilidad', 'proyecto_id');

-- ===========================================
-- TABLAS DE REFERENCIA (Replicadas en todos los nodos)
-- ===========================================

-- Las tablas pequeñas que se usan en JOINs se replican
CREATE OR REPLACE FUNCTION safe_reference_table(table_name text)
RETURNS void AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = safe_reference_table.table_name
    ) AND NOT EXISTS (
        SELECT 1 FROM citus_tables
        WHERE table_name::text = safe_reference_table.table_name
    ) THEN
        EXECUTE format('SELECT create_reference_table(%L)', table_name);
        RAISE NOTICE 'Tabla % configurada como referencia', table_name;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Usuarios: tabla de referencia (replicada)
SELECT safe_reference_table('usuarios');

-- Proyectos: tabla de referencia
SELECT safe_reference_table('proyectos');

-- Configuraciones: tabla de referencia
SELECT safe_reference_table('alertas_config');

-- ===========================================
-- CONFIGURACIÓN DE RENDIMIENTO
-- ===========================================

-- Configurar número de shards (32 es un buen balance)
-- En producción, ajustar según número de workers
ALTER SYSTEM SET citus.shard_count = 32;

-- Habilitar rebalanceo automático
ALTER SYSTEM SET citus.rebalance_by_disk_size = on;

-- Optimizaciones para queries distribuidos
ALTER SYSTEM SET citus.enable_repartition_joins = on;
ALTER SYSTEM SET citus.task_assignment_policy = 'round-robin';

-- Aplicar cambios
SELECT pg_reload_conf();

-- ===========================================
-- ÍNDICES DISTRIBUIDOS
-- ===========================================

-- Los índices se crean automáticamente en cada shard
-- Aquí agregamos índices adicionales para queries comunes

-- Índice para búsqueda rápida de inversiones por estado
-- CREATE INDEX IF NOT EXISTS idx_inversiones_estado ON inversiones(estado);

-- Índice para ledger por tipo de entrada
-- CREATE INDEX IF NOT EXISTS idx_ledger_entry_type ON immutable_ledger(entry_type);

-- ===========================================
-- MONITOREO
-- ===========================================

-- Vista para monitorear distribución de datos
CREATE OR REPLACE VIEW citus_shard_stats AS
SELECT
    logicalrelid::text AS table_name,
    count(*) AS shard_count,
    sum(shard_size) AS total_size_bytes,
    pg_size_pretty(sum(shard_size)) AS total_size
FROM citus_shards
GROUP BY logicalrelid
ORDER BY sum(shard_size) DESC;

-- Vista para monitorear queries distribuidos
CREATE OR REPLACE VIEW citus_query_stats AS
SELECT
    query,
    calls,
    total_time,
    mean_time,
    rows
FROM citus_stat_statements
ORDER BY total_time DESC
LIMIT 20;

-- Log de configuración
DO $$
BEGIN
    RAISE NOTICE 'Citus configurado exitosamente para FinCore';
    RAISE NOTICE 'Shards: 32, Rebalanceo: ON, Repartition Joins: ON';
END $$;
