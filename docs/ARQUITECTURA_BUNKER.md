# Arquitectura Bunker - FinCore

## Resumen Ejecutivo

FinCore implementa una **Arquitectura Bunker** de grado militar, diseñada para garantizar la supervivencia del dato y máxima velocidad de ejecución en operaciones financieras.

## Stack Tecnológico Elite 2026

| Componente | Tecnología | Justificación |
|------------|------------|---------------|
| Backend Core | **Go (Golang)** | Concurrencia nativa, binarios estáticos, usado por Nubank/Stripe |
| Motor de Cálculo | **Python (FastAPI)** | NumPy/Pandas para VAN/TIR, latencia mínima |
| Base de Datos | **PostgreSQL + Citus** | ACID, escalabilidad distribuida |
| Frontend | **Next.js 15+ TypeScript** | Tipado seguro, SSR |
| Cifrado | **Libsodium (NaCl)** | Criptografía de alta seguridad |
| Secretos | **HashiCorp Vault** | Gestión de credenciales Zero Trust |

## Capas de Seguridad

```
┌─────────────────────────────────────────────────────────────┐
│                    CAPA 1: API GATEWAY                       │
│                  (WAF, TLS 1.3, Rate Limiting)              │
├─────────────────────────────────────────────────────────────┤
│                    CAPA 2: FRONTEND                          │
│              (Edge Crypto, Device Fingerprint)              │
├─────────────────────────────────────────────────────────────┤
│                    CAPA 3: BACKEND                           │
│         (Go Core + Python Engine, Zero Trust, mTLS)         │
├─────────────────────────────────────────────────────────────┤
│                    CAPA 4: DATOS                             │
│      (PostgreSQL, Ledger Inmutable, Cifrado en Reposo)      │
├─────────────────────────────────────────────────────────────┤
│                    CAPA 5: VAULT                             │
│         (Secretos Dinámicos, Tokens Temporales)             │
└─────────────────────────────────────────────────────────────┘
```

## Componentes Implementados

### 1. Ledger Inmutable (`backend/app/models/ledger.py`)

```python
# Características:
- Solo INSERT permitido (triggers SQL bloquean UPDATE/DELETE)
- Cadena de hashes SHA-256 (similar a blockchain)
- Verificación automática de integridad
- Snapshots periódicos para auditoría
```

### 2. Cifrado Libsodium (`backend/app/core/bunker_security.py`)

```python
# Algoritmos:
- XSalsa20-Poly1305 para datos
- Argon2id para derivación de claves
- Ed25519 para firmas digitales
```

### 3. Device Fingerprinting (`frontend/src/lib/security/edge-crypto.ts`)

```typescript
// Identifica dispositivos mediante:
- Canvas fingerprint
- WebGL fingerprint
- User-Agent + Headers
- Resolución de pantalla
- Timezone
```

### 4. Zero Trust Auth (`backend/app/core/bunker_security.py`)

```python
# Principios:
- Nunca confiar, siempre verificar
- Tokens temporales (5 min) para servicios
- mTLS para comunicación interna
- HMAC-SHA256 para firmas
```

### 5. Servicio Go (`services/core-go/`)

```go
// Características:
- Procesamiento concurrente (goroutines)
- Latencia < 10ms para transacciones
- Binario estático sin dependencias
- Middleware de seguridad integrado
```

## Flujo del Dato Blindado

```
Usuario                API Gateway           Backend              Base de Datos
   │                        │                   │                       │
   │ 1. Cifra datos PII    │                   │                       │
   │  (Edge Crypto)        │                   │                       │
   │───────────────────────>│                   │                       │
   │                        │ 2. WAF + JWT      │                       │
   │                        │   Validation      │                       │
   │                        │──────────────────>│                       │
   │                        │                   │ 3. Descifra con       │
   │                        │                   │    Vault Key          │
   │                        │                   │──────────────────────>│
   │                        │                   │                       │ 4. Almacena
   │                        │                   │                       │    con Hash
   │                        │                   │<──────────────────────│
   │                        │                   │ 5. Registra en        │
   │                        │                   │    Ledger Inmutable   │
   │                        │<──────────────────│                       │
   │<───────────────────────│                   │                       │
```

## Comparativa de Seguridad

| Característica | Sistema Estándar | Arquitectura Búnker |
|----------------|------------------|---------------------|
| Acceso a BD | Contraseña directa | Tokens temporales (Vault) |
| Cifrado | Solo HTTPS | Tránsito + Reposo + Uso |
| Auditoría | Logs básicos | Ledger inmutable con hash |
| Resiliencia | Backup diario | Replicación Multi-Región |
| Device Check | Ninguno | Fingerprinting |
| Servicios | Monolítico | Microservicios con mTLS |

## Configuración de Despliegue

### Variables de Entorno Requeridas

```bash
# Seguridad
SECRET_KEY=<clave-secreta-256-bits>
ENCRYPTION_KEY=<clave-cifrado-256-bits>

# Vault
VAULT_ADDR=http://vault:8200
VAULT_TOKEN=<token-root>

# Base de datos
DB_PASSWORD=<password-seguro>
DATABASE_URL=postgresql://fincore:${DB_PASSWORD}@postgres:5432/fincore

# Redis
REDIS_PASSWORD=<password-redis>
```

### Iniciar Sistema Completo

```bash
# Desarrollo
docker-compose -f docker-compose.bunker.yml up -d

# Producción (con secretos externos)
docker-compose -f docker-compose.bunker.yml \
  --env-file .env.production up -d
```

## Endpoints de Seguridad

### Backend Python (Puerto 8001)

```
POST /api/v1/auth/login          # Login con MFA
POST /api/v1/auth/verify-mfa     # Verificación TOTP
GET  /api/v1/security/devices    # Dispositivos registrados
POST /api/v1/ledger/verify       # Verificar integridad
```

### Backend Go (Puerto 8002)

```
POST /api/v1/transactions/process    # Procesar transacción
POST /api/v1/transactions/batch      # Batch concurrente
GET  /api/v1/ledger/verify           # Verificar cadena
POST /api/v1/internal/calculate      # Métricas (Zero Trust)
```

## Cumplimiento Normativo

Esta arquitectura está diseñada para cumplir con:

- **SOC 2 Type II**: Controles de seguridad auditables
- **ISO 27001**: Sistema de gestión de seguridad
- **PCI-DSS**: Protección de datos de pago
- **GDPR**: Protección de datos personales
- **Ley Fintech México**: Regulación de tecnología financiera

## Monitoreo y Alertas

```
Prometheus (métricas) → Grafana (dashboards)
                     → AlertManager (alertas)
                     → PagerDuty (incidentes)
```

### Métricas Clave

- `fincore_transactions_total`: Total de transacciones
- `fincore_ledger_integrity`: Estado de integridad
- `fincore_auth_failures`: Intentos de login fallidos
- `fincore_latency_p99`: Latencia percentil 99

## Escalabilidad

### Horizontal

```
                    ┌─────────────┐
                    │ Load Balancer│
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  Go Core 1  │ │  Go Core 2  │ │  Go Core 3  │
    └─────────────┘ └─────────────┘ └─────────────┘
           │               │               │
           └───────────────┼───────────────┘
                           ▼
                    ┌─────────────┐
                    │ PostgreSQL  │
                    │   (Citus)   │
                    └─────────────┘
```

### Multi-Región

- **Primario**: us-east-1 (Virginia)
- **Secundario**: eu-west-1 (Irlanda)
- **RTO**: < 30 segundos
- **RPO**: 0 (replicación síncrona)

---

*Documento generado para FinCore v1.0 - Arquitectura Búnker*
*Última actualización: 2026-02-24*
