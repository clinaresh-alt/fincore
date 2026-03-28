# Seguridad - FinCore

Este documento describe las medidas de seguridad implementadas en FinCore y el historial de auditorias de seguridad.

## Arquitectura de Seguridad

### Autenticacion y Autorizacion
- **JWT con refresh tokens**: Access tokens de 30 minutos, refresh tokens de 7 dias
- **Roles**: Admin, Operador, Inversionista, Solicitante
- **MFA**: Autenticacion de dos factores con TOTP (Google Authenticator)
- **Sesiones**: Control de sesiones activas por usuario

### Cifrado
- **En transito**: TLS 1.3 obligatorio
- **En reposo**: AES-256-GCM para datos sensibles
- **Derivacion de claves**: PBKDF2 con salt dinamico (SHA-256, 100k iteraciones)
- **Secretos**: HashiCorp Vault para gestion centralizada

### Proteccion de API
- **Rate Limiting**: SlowAPI con limites por endpoint
  - Auth: 5 requests/minuto
  - API general: 100 requests/minuto
  - Webhooks: 30 requests/minuto
- **CORS**: Origins especificos configurados
- **Headers de Seguridad**:
  - Content-Security-Policy
  - Strict-Transport-Security (HSTS)
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
  - X-XSS-Protection

### Validacion de Webhooks
- **STP**: Verificacion HMAC-SHA256 con timestamp
- **Bitso**: Firma criptografica validada
- **Replay Protection**: Ventana de 5 minutos para timestamps

## Audit de Seguridad - Marzo 2026

### Resumen Ejecutivo

Se realizo un audit completo del codebase identificando y corrigiendo **23 vulnerabilidades**:

| Severidad | Cantidad | Estado |
|-----------|----------|--------|
| CRITICAL | 5 | Corregido |
| HIGH | 5 | Corregido |
| MEDIUM | 8 | Corregido |
| LOW | 5 | Corregido |

### Fase 1: Vulnerabilidades CRITICAL

#### 1.1 Hardcoded Secrets Eliminados
- `services/core-go/internal/security/security.go`: Claves por defecto removidas
- `backend/app/services/encryption_service.py`: Clave de desarrollo ahora es aleatoria
- `backend/app/services/webhook_service.py`: Webhook secret obligatorio desde env
- `backend/scripts/create_admin.py`: Generador seguro de contrasenas

#### 1.2 Validacion de Secretos en Produccion
```python
# backend/app/core/config.py
def _get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not debug_mode and not secret:
        raise ValueError("JWT_SECRET_KEY es OBLIGATORIO en produccion")
    if secret and len(secret) < 32:
        raise ValueError("JWT_SECRET_KEY debe tener al menos 32 caracteres")
```

### Fase 2: Vulnerabilidades HIGH

#### 2.1 Rate Limiting Implementado
```python
# backend/app/main.py
limiter = Limiter(key_func=get_real_client_ip)
app.state.limiter = limiter

@app.get("/api/v1/auth/login")
@limiter.limit("5/minute")
async def login():
    ...
```

#### 2.2 CORS Restrictivo
```python
ALLOWED_ORIGINS = [
    "https://app.fincore.com",
    "https://admin.fincore.com",
]
if settings.DEBUG:
    ALLOWED_ORIGINS.extend(["http://localhost:3000"])
```

#### 2.3 Verificacion de Webhooks STP
```python
def verify_stp_webhook_signature(request, signature, timestamp):
    payload = f"{timestamp}.{body}"
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
```

### Fase 3: Vulnerabilidades MEDIUM

#### 3.1 Excepciones Especificas
- Reemplazo de `except Exception` generico por excepciones especificas
- Archivos: `financial_engine.py`, `security_service.py`, `chaos_engineering_service.py`

#### 3.2 Optimizacion de Queries
```python
# Eager loading para evitar N+1
query = db.query(Project).options(
    joinedload(Project.evaluacion),
    selectinload(Project.flujos_caja),
)
```

#### 3.3 Async/Await Correcto
- Reemplazo de `time.sleep()` por `asyncio.sleep()` en blockchain_service.py

#### 3.4 Modelos de Compliance
- `ScreeningAuditLog`: Registro de screenings AML
- `SARReport`: Reportes de Actividad Sospechosa

### Fase 4: Vulnerabilidades LOW

#### 4.1 Logging Apropiado
- Reemplazo de `print()` por `logger` en 6 archivos
- Archivos: bunker_security.py, monitoring_service.py, incident_response.py, dashboard.py, slither_service.py

#### 4.2 Metricas del Sistema
```python
# Middleware de metricas en main.py
@app.middleware("http")
async def collect_request_metrics(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response_time_ms = (time.time() - start_time) * 1000
    # Actualizar metricas...
```

### Fase 5: Correcciones Adicionales

#### 5.1 Validacion de Path Traversal
```python
# backend/app/services/audit.py
resolved_path = os.path.realpath(contract_path)
allowed_dirs = ["./contracts", "/tmp/contracts"]
if not any(resolved_path.startswith(d) for d in allowed_dirs):
    raise PermissionError("Path no permitido")
```

#### 5.2 Validacion de Credenciales
```python
# backend/app/services/bitso_service.py
def _validate_credentials(self):
    if not self.config.use_sandbox:
        if not self.config.api_key:
            raise ValueError("BITSO_API_KEY obligatorio en produccion")
```

#### 5.3 MD5 Seguro
```python
# Uso de MD5 solo para cache keys, no seguridad
cache_key = hashlib.md5(data.encode(), usedforsecurity=False).hexdigest()
```

## Herramientas de Seguridad

### Analisis Estatico
```bash
# Bandit - Analisis de seguridad Python
bandit -r backend/app -f html -o security-report.html

# Gitleaks - Deteccion de secretos
gitleaks detect --source .

# pip-audit - Vulnerabilidades en dependencias
pip-audit -r requirements.txt
```

### Resultados Actuales
```
Bandit:
  - HIGH: 0
  - MEDIUM: 3 (aceptables - binding 0.0.0.0, uso de /tmp)
  - LOW: 34 (falsos positivos)

npm audit:
  - Vulnerabilities: 0

gitleaks:
  - .env files: No trackeados en git
```

## Configuracion Segura

### Variables de Entorno Requeridas (Produccion)

```env
# OBLIGATORIAS
JWT_SECRET_KEY=<min 32 caracteres>
ENCRYPTION_KEY=<32 bytes base64>
DB_PASSWORD=<password seguro>
STP_WEBHOOK_SECRET=<secret compartido con STP>
BITSO_API_KEY=<api key de Bitso>
BITSO_API_SECRET=<api secret de Bitso>

# RECOMENDADAS
VAULT_TOKEN=<token de HashiCorp Vault>
CHAINALYSIS_API_KEY=<para screening AML>
```

### Checklist de Despliegue

- [ ] Todas las variables de entorno configuradas
- [ ] DEBUG=false en produccion
- [ ] HTTPS habilitado (TLS 1.3)
- [ ] Rate limiting activo
- [ ] CORS configurado con origins especificos
- [ ] Logs no contienen datos sensibles
- [ ] Backups de base de datos encriptados
- [ ] Vault configurado para secretos

## Reporte de Vulnerabilidades

Para reportar vulnerabilidades de seguridad:

1. **NO** crear issues publicos
2. Enviar email a: security@fincore.com
3. Incluir:
   - Descripcion de la vulnerabilidad
   - Pasos para reproducir
   - Impacto potencial
   - Sugerencia de remediacion (opcional)

Tiempo de respuesta esperado: 48 horas.

## Historial de Auditorias

| Fecha | Tipo | Hallazgos | Estado |
|-------|------|-----------|--------|
| 2026-03-27 | Audit Interno | 23 vulnerabilidades | Corregido |

## Referencias

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [PCI DSS v4.0](https://www.pcisecuritystandards.org/)
