# Plan de Recuperacion ante Desastres (DRP) y Continuidad de Negocio (BCP)

## FinCore - Version 1.0

**Clasificacion:** Confidencial
**Ultima Revision:** 2026-03-25
**Proxima Revision:** Trimestral
**Responsable:** CTO / CISO

---

## Tabla de Contenidos

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Objetivos de Recuperacion](#2-objetivos-de-recuperacion)
3. [Arquitectura de Alta Disponibilidad](#3-arquitectura-de-alta-disponibilidad)
4. [Escenarios de Desastre](#4-escenarios-de-desastre)
5. [Procedimientos de Recuperacion](#5-procedimientos-de-recuperacion)
6. [Plan de Continuidad de Negocio](#6-plan-de-continuidad-de-negocio)
7. [Pruebas y Simulacros](#7-pruebas-y-simulacros)
8. [Contactos de Emergencia](#8-contactos-de-emergencia)
9. [Anexos](#9-anexos)

---

## 1. Resumen Ejecutivo

### 1.1 Proposito

Este documento establece los procedimientos para:
- Recuperar los sistemas de FinCore ante eventos catastróficos
- Mantener la continuidad de operaciones críticas
- Minimizar el impacto financiero y reputacional
- Cumplir con requisitos regulatorios

### 1.2 Alcance

| Sistema | Criticidad | RPO | RTO |
|---------|-----------|-----|-----|
| API Core | Crítica | 15 min | 60 min |
| Base de Datos | Crítica | 15 min | 60 min |
| Blockchain Services | Crítica | 0 min* | 60 min |
| Bank Integration | Alta | 30 min | 120 min |
| Status Page | Media | 60 min | 240 min |

*Los datos en blockchain son inmutables y no requieren backup tradicional.

### 1.3 Definiciones

| Termino | Definicion |
|---------|-----------|
| **RTO** | Recovery Time Objective - Tiempo maximo para restaurar el servicio |
| **RPO** | Recovery Point Objective - Perdida maxima de datos aceptable |
| **MTTR** | Mean Time To Recovery - Tiempo promedio de recuperacion |
| **MTBF** | Mean Time Between Failures - Tiempo promedio entre fallas |
| **BIA** | Business Impact Analysis - Analisis de impacto al negocio |

---

## 2. Objetivos de Recuperacion

### 2.1 Metricas Objetivo

```
+------------------+--------+--------+--------+
|     Metrica      | Tier 1 | Tier 2 | Tier 3 |
+------------------+--------+--------+--------+
| RTO              | 1 hora | 4 hrs  | 24 hrs |
| RPO              | 15 min | 1 hora | 4 hrs  |
| Disponibilidad   | 99.99% | 99.9%  | 99%    |
| Uptime Mensual   | 52.6m  | 8.77h  | 7.31h  |
+------------------+--------+--------+--------+

Tier 1: Sistemas criticos (API, DB, Blockchain)
Tier 2: Sistemas importantes (Banking, Webhooks)
Tier 3: Sistemas de soporte (Analytics, Logs)
```

### 2.2 Impacto por Tiempo de Inactividad

| Duracion | Impacto Financiero Est. | Impacto Reputacional |
|----------|------------------------|---------------------|
| 0-15 min | $5,000 | Bajo |
| 15-60 min | $25,000 | Medio |
| 1-4 horas | $100,000 | Alto |
| 4-24 horas | $500,000 | Severo |
| > 24 horas | $1,000,000+ | Critico |

---

## 3. Arquitectura de Alta Disponibilidad

### 3.1 Infraestructura Multi-Region

```
                    +-----------------+
                    |   Route 53      |
                    | (DNS Failover)  |
                    +--------+--------+
                             |
              +--------------+--------------+
              |                             |
    +---------v---------+         +---------v---------+
    |   US-EAST-1       |         |   US-WEST-2       |
    |   (Primary)       |         |   (DR)            |
    +-------------------+         +-------------------+
    |                   |         |                   |
    | +---------------+ |         | +---------------+ |
    | |     ALB       | |         | |     ALB       | |
    | +-------+-------+ |         | +-------+-------+ |
    |         |         |         |         |         |
    | +-------v-------+ |         | +-------v-------+ |
    | |  ECS Fargate  | |         | |  ECS Fargate  | |
    | |  (2-10 tasks) | |         | |  (0-10 tasks) | |
    | +-------+-------+ |         | +-------+-------+ |
    |         |         |         |         |         |
    | +-------v-------+ |         | +-------v-------+ |
    | |   RDS Multi-AZ| |    -->  | |  RDS Replica  | |
    | |   (Primary)   | |   Sync  | |  (Read-only)  | |
    | +---------------+ |         | +---------------+ |
    |                   |         |                   |
    | +---------------+ |         | +---------------+ |
    | |  ElastiCache  | |         | |  ElastiCache  | |
    | |  (Cluster)    | |         | |  (Standalone) | |
    | +---------------+ |         | +---------------+ |
    +-------------------+         +-------------------+
```

### 3.2 Replicacion de Datos

| Componente | Tipo de Replicacion | Frecuencia | Lag Maximo |
|------------|-------------------|------------|------------|
| PostgreSQL | Streaming (async) | Continuo | 15 min |
| S3 | Cross-region | Continuo | 15 min |
| Redis | Snapshot | Horario | 1 hora |
| Vault | Snapshot | Diario | 24 horas |

### 3.3 Backups

```yaml
PostgreSQL:
  tipo: WAL Archiving + Snapshots
  frecuencia_wal: Continuo
  frecuencia_snapshot: Diario a las 03:00 UTC
  retencion: 30 dias
  ubicacion: S3 (encriptado con KMS)
  prueba_restauracion: Semanal

S3:
  tipo: Versionado + Replicacion
  retencion_versiones: 90 dias
  lifecycle:
    - STANDARD -> IA: 90 dias
    - IA -> Glacier: 365 dias
    - Eliminacion: 7 años

Secrets (Vault):
  tipo: Snapshot
  frecuencia: Diario
  retencion: 90 dias
  ubicacion: S3 separado
```

---

## 4. Escenarios de Desastre

### 4.1 Matriz de Escenarios

| ID | Escenario | Probabilidad | Impacto | Prioridad |
|----|-----------|--------------|---------|-----------|
| D1 | Falla de region AWS completa | Baja | Critico | Alta |
| D2 | Corrupcion de base de datos | Muy Baja | Critico | Alta |
| D3 | Brecha de seguridad / Ransomware | Baja | Critico | Alta |
| D4 | Exploit de smart contract | Baja | Critico | Alta |
| D5 | Falla de proveedor (RPC, Oracle) | Media | Alto | Media |
| D6 | DDoS sostenido | Media | Alto | Media |
| D7 | Error de configuracion | Media | Medio | Media |
| D8 | Falla de red | Baja | Medio | Baja |

### 4.2 D1: Falla de Region AWS

**Descripcion:** La region primaria (us-east-1) no esta disponible.

**Deteccion:**
- Route53 health checks fallan
- CloudWatch alarmas de replicacion
- Alertas de servicios externos (Datadog, PagerDuty)

**Procedimiento:**
1. Confirmar que no es falla parcial (verificar AWS Health Dashboard)
2. Ejecutar failover a region DR: `python dr_runbook.py failover`
3. Promover replica de DB a primaria
4. Escalar servicios en DR
5. Actualizar DNS
6. Notificar a usuarios via Status Page

**Tiempo Estimado:** 30-60 minutos

### 4.3 D2: Corrupcion de Base de Datos

**Descripcion:** Datos corruptos o eliminados accidentalmente.

**Deteccion:**
- Errores de integridad en aplicacion
- Reportes de usuarios
- Alertas de consistencia

**Procedimiento:**
1. Activar Kill Switch para prevenir mas dano
2. Identificar punto de corrupcion (timestamps, logs)
3. Evaluar opciones:
   - PITR: `python dr_runbook.py rollback --point-in-time "TIMESTAMP"`
   - Snapshot: `python dr_runbook.py rollback --snapshot "SNAPSHOT_ID"`
4. Restaurar a nueva instancia
5. Validar integridad de datos
6. Swap de instancias
7. Desactivar Kill Switch

**Tiempo Estimado:** 60-120 minutos

### 4.4 D3: Brecha de Seguridad

**Descripcion:** Acceso no autorizado o ransomware detectado.

**Procedimiento:**
1. **INMEDIATO:** Activar Kill Switch
2. Aislar sistemas afectados (security groups)
3. Preservar evidencia forense (no reiniciar)
4. Revocar todas las credenciales comprometidas
5. Notificar a equipo legal y reguladores
6. Analisis forense completo
7. Restaurar desde backups verificados
8. Rotar TODOS los secretos
9. Post-mortem y mejoras

**Tiempo Estimado:** 4-24 horas (dependiendo del alcance)

### 4.5 D4: Exploit de Smart Contract

**Descripcion:** Vulnerabilidad explotada en contratos.

**Procedimiento:**
1. **INMEDIATO:** Activar Kill Switch
2. Pausar contratos via multisig
3. Evaluar dano (fondos perdidos/en riesgo)
4. Contactar security researchers si es necesario
5. Preparar parche/migracion
6. Coordinar comunicacion con usuarios
7. Desplegar fix via proceso de gobernanza
8. Considerar compensacion a afectados

**Tiempo Estimado:** Variable (horas a dias)

---

## 5. Procedimientos de Recuperacion

### 5.1 Procedimiento General de DR

```
+------------+     +-------------+     +------------+
|  DETECTAR  | --> | EVALUAR     | --> |  DECIDIR   |
+------------+     +-------------+     +------------+
                                             |
                   +-------------------------+
                   |
          +--------v--------+
          | FAILOVER /      |
          | RECUPERACION    |
          +-----------------+
                   |
          +--------v--------+
          |    VALIDAR      |
          +-----------------+
                   |
          +--------v--------+
          |   COMUNICAR     |
          +-----------------+
                   |
          +--------v--------+
          | POST-MORTEM     |
          +-----------------+
```

### 5.2 Failover a Region DR

```bash
# 1. Verificar estado de DR
python dr_runbook.py health

# 2. Ejecutar failover (dry-run primero)
python dr_runbook.py failover --dry-run

# 3. Ejecutar failover real
python dr_runbook.py failover

# 4. Verificar estado post-failover
python dr_runbook.py health
```

### 5.3 Rollback de Base de Datos

```bash
# Ver ventana de recuperacion disponible
python dr_runbook.py recovery-window

# Listar snapshots disponibles
python dr_runbook.py list-snapshots

# Opcion A: Point-in-Time Recovery
python dr_runbook.py rollback --point-in-time "2024-01-15T14:30:00Z"

# Opcion B: Restaurar desde snapshot
python dr_runbook.py rollback --snapshot "rds:fincore-production-2024-01-15-03-00"
```

### 5.4 Failback a Region Primaria

```bash
# Solo despues de resolver el incidente y validar primaria

# 1. Sincronizar datos de DR a primaria
# (Crear nueva replica desde DR hacia primaria)

# 2. Verificar sincronizacion completa
python dr_runbook.py health

# 3. Actualizar DNS gradualmente (weighted routing)

# 4. Monitorear por 24 horas antes de completar failback
```

---

## 6. Plan de Continuidad de Negocio

### 6.1 Funciones Criticas del Negocio

| Funcion | Sistema | Modo Degradado | Duracion Maxima |
|---------|---------|----------------|-----------------|
| Procesar remesas | API + Blockchain | Solo consultas | 4 horas |
| Verificar KYC/AML | Compliance | Proceso manual | 24 horas |
| Soporte al cliente | CRM | Email/telefono | Ilimitado |
| Reportes regulatorios | Analytics | Diferido | 72 horas |

### 6.2 Operacion en Modo Degradado

Durante una interrupcion parcial, el sistema puede operar en modo degradado:

**Modo Solo-Lectura:**
- Usuarios pueden ver balances y transacciones
- No se procesan nuevas remesas
- Activado via: `READONLY_MODE=true`

**Modo Offline:**
- Pagina de mantenimiento
- Comunicacion via email/SMS
- Status page actualizada cada 15 minutos

### 6.3 Comunicaciones de Crisis

**Plantilla de Comunicacion Inicial:**
```
ASUNTO: [Aviso de Servicio] FinCore - Interrupcion Temporal

Estimado usuario,

Estamos experimentando una interrupcion tecnica que afecta
temporalmente nuestros servicios.

Estado actual: [DESCRIPCION]
Impacto: [SERVICIOS AFECTADOS]
Proxima actualizacion: [HORA]

Sus fondos estan seguros. Actualizaremos via este canal.

- Equipo FinCore
```

---

## 7. Pruebas y Simulacros

### 7.1 Calendario de Pruebas

| Prueba | Frecuencia | Responsable | Duracion |
|--------|-----------|-------------|----------|
| Backup restore DB | Semanal | DBA | 2 horas |
| Failover DR (dry-run) | Mensual | SRE | 1 hora |
| Failover DR (real) | Trimestral | SRE + Ops | 4 horas |
| Chaos Engineering | Quincenal | SRE | 1 hora |
| Tabletop exercise | Trimestral | Liderazgo | 2 horas |
| Full DR drill | Anual | Toda la org | 1 dia |

### 7.2 Simulacro de Failover

```bash
# Ejecutar simulacro completo
python dr_runbook.py simulate --scenario full-failover

# Resultados esperados:
# - Tiempo de deteccion: < 5 minutos
# - Tiempo de decision: < 10 minutos
# - Tiempo de failover: < 45 minutos
# - Tiempo total: < 60 minutos (dentro de RTO)
```

### 7.3 Chaos Engineering

```bash
# Inyectar latencia en DB
python -c "
from app.services.chaos_engineering_service import ChaosService
chaos = ChaosService()
await chaos.run_latency_experiment(
    target='database',
    latency_ms=200,
    duration_seconds=60,
)
"

# Simular falla de dependencia
python -c "
from app.services.chaos_engineering_service import ChaosService
chaos = ChaosService()
await chaos.run_dependency_failure_experiment(
    dependency='blockchain-rpc',
    duration_seconds=60,
)
"
```

### 7.4 Metricas de Exito

| Metrica | Objetivo | Actual |
|---------|----------|--------|
| RTO cumplido | 100% | - |
| RPO cumplido | 100% | - |
| Pruebas completadas | 100% | - |
| Issues encontrados/resueltos | < 5 abiertos | - |

---

## 8. Contactos de Emergencia

### 8.1 Equipo Interno

| Rol | Nombre | Telefono | Email |
|-----|--------|----------|-------|
| Incident Commander | [CTO] | +1-XXX-XXX-XXXX | cto@fincore.com |
| Tech Lead | [VP Eng] | +1-XXX-XXX-XXXX | vpeng@fincore.com |
| Security Lead | [CISO] | +1-XXX-XXX-XXXX | ciso@fincore.com |
| On-Call Primary | [Rotativo] | +1-XXX-XXX-XXXX | oncall@fincore.com |
| On-Call Secondary | [Rotativo] | +1-XXX-XXX-XXXX | oncall-backup@fincore.com |

### 8.2 Proveedores Criticos

| Proveedor | Servicio | Contacto | SLA |
|-----------|----------|----------|-----|
| AWS | Cloud Infrastructure | premium-support | 24/7 |
| Alchemy | Blockchain RPC | support@alchemy.com | 24/7 |
| Safe (Gnosis) | Multisig | support@safe.global | Business hours |
| PagerDuty | Alerting | support@pagerduty.com | 24/7 |

### 8.3 Reguladores y Legales

| Entidad | Contacto | Cuando Notificar |
|---------|----------|------------------|
| [Regulador Local] | compliance@regulador.gov | Brecha de datos, incidente mayor |
| Legal Counsel | [Firma Legal] | Cualquier incidente de seguridad |
| Cyber Insurance | [Aseguradora] | Incidente de seguridad confirmado |

---

## 9. Anexos

### A. Checklist de Failover

- [ ] Alertas recibidas y confirmadas
- [ ] Incidente confirmado (no falso positivo)
- [ ] Incident Commander designado
- [ ] War Room convocado
- [ ] Comunicacion inicial enviada
- [ ] Health check de DR completado
- [ ] Replication lag verificado (< RPO)
- [ ] Failover ejecutado
- [ ] DNS actualizado
- [ ] Servicios escalados en DR
- [ ] Health checks post-failover OK
- [ ] Status page actualizada
- [ ] Usuarios notificados
- [ ] Reguladores notificados (si aplica)
- [ ] Post-mortem programado

### B. Comandos de Emergencia

```bash
# Estado del sistema
curl https://api.fincore.com/health

# Activar Kill Switch
curl -X POST https://api.fincore.com/api/v1/admin/security/kill-switch \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"reason": "Emergency", "initiated_by": "admin@fincore.com"}'

# Ver alertas activas
curl https://api.fincore.com/api/v1/admin/security/alerts?severity=critical

# Verificar DR
python dr_runbook.py health

# Failover
python dr_runbook.py failover --dry-run
python dr_runbook.py failover

# Rollback DB
python dr_runbook.py rollback --point-in-time "TIMESTAMP"
```

### C. Diagrama de Escalacion

```
T+0 min    Alerta detectada
           |
T+5 min    On-Call Engineer responde
           |
T+15 min   Si no resuelto -> Escalar a Tech Lead
           |
T+30 min   Si no resuelto -> Escalar a CTO
           |
T+60 min   Si impacto critico -> Escalar a CEO
           |
           Comunicacion externa si necesario
```

### D. Historial de Revisiones

| Version | Fecha | Autor | Cambios |
|---------|-------|-------|---------|
| 1.0 | 2026-03-25 | CTO | Version inicial |

---

**Fin del Documento**

*Este documento debe ser revisado trimestralmente y actualizado
despues de cada incidente o cambio significativo en la infraestructura.*
