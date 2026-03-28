# Changelog

Todos los cambios notables en este proyecto seran documentados en este archivo.

El formato esta basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [Unreleased]

## [1.5.0] - 2026-03-27

### Seguridad
- **CRITICAL**: Eliminados hardcoded secrets en security.go, encryption_service.py, webhook_service.py
- **CRITICAL**: JWT_SECRET_KEY ahora es obligatorio en produccion (minimo 32 caracteres)
- **CRITICAL**: Salt dinamico implementado para PBKDF2
- **CRITICAL**: Generador seguro de contrasenas para script de admin
- **HIGH**: Rate limiting implementado con SlowAPI (5-100 req/min)
- **HIGH**: CORS restrictivo con origins especificos
- **HIGH**: Headers de seguridad agregados (CSP, HSTS, X-Frame-Options)
- **HIGH**: Verificacion HMAC-SHA256 en webhooks STP
- **HIGH**: Dependencias npm actualizadas (brace-expansion vulnerability)
- **MEDIUM**: Excepciones especificas en lugar de Exception generica
- **MEDIUM**: Paginacion y eager loading en queries de proyectos
- **MEDIUM**: asyncio.sleep en lugar de time.sleep bloqueante
- **MEDIUM**: Validacion de path traversal en ejecucion de Slither
- **MEDIUM**: Validacion de credenciales Bitso en produccion
- **MEDIUM**: MD5 marcado con usedforsecurity=False
- **LOW**: print() reemplazado por logger en 6 archivos
- **LOW**: Metricas de sistema implementadas (requests/s, response time)

### Agregado
- `SECURITY.md` con documentacion completa de seguridad
- Modelos `ScreeningAuditLog` y `SARReport` para compliance
- Middleware de metricas de requests en main.py
- Funcion `_validate_credentials()` en BitsoService
- Validacion de path en `_run_slither()`
- Tipo de alerta `RECONCILIATION_DISCREPANCY`
- Campo `avg_wait_time_ms` en QueueStats

### Cambiado
- Seccion de Seguridad en README.md expandida
- `NewSecurityManager()` en Go ahora retorna error si faltan secrets
- `_generate_dev_key()` ahora genera clave aleatoria en desarrollo
- Token expiration reducido de 60 a 30 minutos
- Queries de estadisticas optimizadas con COUNT agregado

### Corregido
- N+1 queries en endpoint de proyectos
- TIR, defaults e historico en portal de inversionista
- Queries de auditoria en compliance screening
- Integracion de alertas en reconciliacion

## [1.4.0] - 2026-03-25

### Agregado
- Sistema completo de monitoreo y alertas en tiempo real
- WebSocket para dashboard en vivo
- Integracion con Forta para alertas blockchain

## [1.3.0] - 2026-03-20

### Agregado
- Modulo completo de remesas con reconciliacion
- Integracion STP para pagos SPEI
- Integracion Bitso para conversion crypto/fiat

### Corregido
- Rutas de remesas (prefijo duplicado eliminado)

## [1.2.0] - 2026-03-15

### Agregado
- Suite de tests completa
- Pipelines CI/CD con GitHub Actions
- Tests de auditoria de smart contracts

## [1.1.0] - 2026-03-10

### Cambiado
- Actualizacion a Python 3.12
- Actualizacion de dependencias para compatibilidad

## [1.0.0] - 2026-03-01

### Agregado
- Tokenizacion de activos con contratos ERC-20
- Motor financiero (VAN, TIR, ROI, Payback)
- Sistema de compliance PLD/AML
- Portal de inversionista
- Dashboard de administracion
- Integracion multi-chain (Polygon, Ethereum, Arbitrum, Base)

---

[Unreleased]: https://github.com/clinaresh-alt/fincore/compare/v1.5.0...HEAD
[1.5.0]: https://github.com/clinaresh-alt/fincore/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/clinaresh-alt/fincore/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/clinaresh-alt/fincore/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/clinaresh-alt/fincore/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/clinaresh-alt/fincore/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/clinaresh-alt/fincore/releases/tag/v1.0.0
