# HashiCorp Vault Configuration for FinCore
# Arquitectura Bunker - Gestion de Secretos

storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = "true"  # En produccion, usar TLS
}

# API address
api_addr = "http://127.0.0.1:8200"

# UI habilitada para desarrollo
ui = true

# Logging
log_level = "info"

# Telemetry
telemetry {
  prometheus_retention_time = "30s"
  disable_hostname          = true
}
