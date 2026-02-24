-- FinCore Database Initialization
-- Arquitectura Bunker - Base de Datos Segura

-- Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Crear roles con permisos minimos (Principio de Menor Privilegio)
CREATE ROLE fincore_readonly;
CREATE ROLE fincore_readwrite;
CREATE ROLE fincore_admin;

-- Permisos por rol
GRANT CONNECT ON DATABASE fincore TO fincore_readonly;
GRANT CONNECT ON DATABASE fincore TO fincore_readwrite;
GRANT CONNECT ON DATABASE fincore TO fincore_admin;

-- Schema para datos sensibles (cifrados)
CREATE SCHEMA IF NOT EXISTS secure;

-- Tabla de configuracion de seguridad
CREATE TABLE IF NOT EXISTS secure.encryption_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_name VARCHAR(100) UNIQUE NOT NULL,
    key_version INTEGER NOT NULL DEFAULT 1,
    algorithm VARCHAR(50) NOT NULL DEFAULT 'AES-256-GCM',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    rotated_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Tabla de dispositivos registrados
CREATE TABLE IF NOT EXISTS secure.registered_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    device_name VARCHAR(255),
    user_agent TEXT,
    first_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_trusted BOOLEAN DEFAULT FALSE,
    trust_level INTEGER DEFAULT 0,
    UNIQUE(user_id, fingerprint)
);

-- Indice para busqueda rapida de dispositivos
CREATE INDEX idx_devices_user ON secure.registered_devices(user_id);
CREATE INDEX idx_devices_fingerprint ON secure.registered_devices(fingerprint);

-- Funcion para prevenir eliminacion de registros criticos
CREATE OR REPLACE FUNCTION prevent_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'DELETE operation not allowed on this table';
END;
$$ LANGUAGE plpgsql;

-- Funcion para registrar cambios en audit log
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (
            action, resource_type, resource_id,
            new_values, timestamp
        ) VALUES (
            TG_OP, TG_TABLE_NAME, NEW.id,
            row_to_json(NEW), NOW()
        );
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (
            action, resource_type, resource_id,
            old_values, new_values, timestamp
        ) VALUES (
            TG_OP, TG_TABLE_NAME, NEW.id,
            row_to_json(OLD), row_to_json(NEW), NOW()
        );
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO audit_log (
            action, resource_type, resource_id,
            old_values, timestamp
        ) VALUES (
            TG_OP, TG_TABLE_NAME, OLD.id,
            row_to_json(OLD), NOW()
        );
        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Configuracion de TDE (Transparent Data Encryption)
-- Nota: Requiere configuracion a nivel de disco/volumen en produccion

-- Log de inicializacion
DO $$
BEGIN
    RAISE NOTICE 'FinCore database initialized with Bunker security settings';
END $$;
