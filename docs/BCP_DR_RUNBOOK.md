# FinCore - Business Continuity Plan (BCP) y Disaster Recovery (DR)

## Clasificación: CONFIDENCIAL - Solo personal autorizado

**Versión:** 1.0
**Última actualización:** 2024
**Propietario:** Equipo de Infraestructura FinCore

---

## 1. Resumen Ejecutivo

Este documento describe los procedimientos de continuidad de negocio y recuperación ante desastres para la plataforma FinCore. Define:

- Objetivos de recuperación (RTO/RPO)
- Procedimientos de escalamiento
- Modos de operación degradada
- Runbooks de recuperación

---

## 2. Definiciones y Métricas

### 2.1 Recovery Time Objective (RTO)

| Categoría | Servicio | RTO | Justificación |
|-----------|----------|-----|---------------|
| **Crítico** | Base de datos | 15 min | Core del sistema |
| **Crítico** | API Core | 15 min | Acceso a plataforma |
| **Crítico** | Redis | 30 min | Sesiones y cache |
| **Alto** | Pagos/STP | 1 hora | Operaciones financieras |
| **Alto** | Blockchain | 2 horas | Puede usar fallback |
| **Medio** | Notificaciones | 4 horas | No crítico |
| **Bajo** | AI/Analytics | 8 horas | Funcionalidad auxiliar |

### 2.2 Recovery Point Objective (RPO)

| Datos | RPO | Estrategia |
|-------|-----|------------|
| Transacciones financieras | 0 (síncr.) | Replicación síncrona |
| Datos de usuario | 5 min | WAL shipping |
| Logs de auditoría | 1 min | Streaming a S3 |
| Cache/sesiones | N/A | Regenerable |
| Analytics | 1 hora | Batch backup |

---

## 3. Arquitectura de Alta Disponibilidad

```
                    ┌──────────────────┐
                    │   Cloudflare     │
                    │   (WAF + CDN)    │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │   ALB     │  │   ALB     │  │   ALB     │
        │  us-east  │  │  us-west  │  │  eu-west  │
        └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
              │              │              │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │   EKS     │  │   EKS     │  │   EKS     │
        │  Cluster  │  │  Cluster  │  │  Cluster  │
        └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
              │              │              │
              └──────────────┼──────────────┘
                             │
                    ┌────────▼────────┐
                    │   Aurora Global │
                    │   (Multi-Region)│
                    └─────────────────┘
```

### 3.1 Componentes Redundantes

| Componente | Primario | Secundario | Failover |
|------------|----------|------------|----------|
| Database | Aurora us-east-1 | Aurora us-west-2 | Automático (<1 min) |
| Redis | ElastiCache cluster | Cross-AZ replica | Automático |
| API | EKS us-east-1 | EKS us-west-2 | Route53 health check |
| Storage | S3 us-east-1 | S3 us-west-2 | Cross-region replication |
| Secrets | Secrets Manager | Cross-region | Automático |

---

## 4. Modos de Operación

### 4.1 Modo Normal
- Todos los servicios operativos
- Todas las funcionalidades disponibles
- Latencia < 200ms P99

### 4.2 Modo Degradado
**Activación automática cuando:** 2+ servicios no críticos fallan

**Funcionalidades deshabilitadas:**
- Análisis AI
- Notificaciones en tiempo real
- Streaming de datos de mercado

**Funcionalidades disponibles:**
- Login/Logout
- Consulta de balances
- Remesas (con confirmación manual)
- Trading básico

### 4.3 Modo Emergencia
**Activación automática cuando:** Servicios críticos fallan O 4+ servicios fallan

**Funcionalidades deshabilitadas:**
- Todo lo de Modo Degradado
- Nuevas remesas
- Trading
- Operaciones blockchain

**Funcionalidades disponibles:**
- Login/Logout (solo lectura)
- Consulta de balances
- Visualización de historial
- Soporte/tickets

### 4.4 Modo Solo Lectura
**Activación manual:** Para mantenimientos o incidentes graves

**Funcionalidades:**
- Solo operaciones de lectura
- No se permiten transacciones
- Banner informativo a usuarios

---

## 5. Procedimientos de Escalamiento

### 5.1 Niveles de Severidad

| Nivel | Descripción | Tiempo Respuesta | Escalamiento |
|-------|-------------|------------------|--------------|
| SEV1 | Outage total | 5 min | CEO, CTO, On-call |
| SEV2 | Funcionalidad crítica | 15 min | CTO, On-call |
| SEV3 | Degradación | 30 min | On-call |
| SEV4 | Menor | 4 horas | Ticket |

### 5.2 Cadena de Escalamiento

```
SEV1/SEV2:
1. PagerDuty → On-call Engineer (5 min)
2. Si no responde → Backup on-call (10 min)
3. Si persiste 30 min → Engineering Manager
4. Si persiste 1 hora → CTO + CEO

SEV3:
1. PagerDuty → On-call Engineer (15 min)
2. Si no responde → Slack #incidents
3. Si persiste 2 horas → Engineering Manager
```

### 5.3 Contactos de Emergencia

| Rol | Primario | Backup |
|-----|----------|--------|
| On-call Engineer | Rotación semanal | Ver PagerDuty |
| Engineering Manager | [REDACTED] | [REDACTED] |
| CTO | [REDACTED] | [REDACTED] |
| Proveedor DB (AWS) | AWS Support | 1-800-xxx |
| Proveedor Pagos (STP) | [REDACTED] | [REDACTED] |

---

## 6. Runbooks de Recuperación

### 6.1 Database Failover

**Síntomas:**
- Conexiones fallando
- Timeout en queries
- Aurora primary unreachable

**Pasos:**
```bash
# 1. Verificar estado
aws rds describe-db-cluster-endpoints --db-cluster-identifier fincore-prod

# 2. Iniciar failover manual (si automático no ocurrió)
aws rds failover-db-cluster --db-cluster-identifier fincore-prod

# 3. Verificar nuevo primary
aws rds describe-db-cluster-endpoints --db-cluster-identifier fincore-prod

# 4. Actualizar DNS si es necesario (Route53)
aws route53 change-resource-record-sets --hosted-zone-id ZONE_ID --change-batch file://dns-failover.json

# 5. Verificar conectividad desde apps
kubectl exec -it deploy/api-server -- python -c "from app.core.database import engine; print(engine.connect())"

# 6. Monitorear replicación
aws rds describe-db-clusters --db-cluster-identifier fincore-prod | jq '.DBClusters[0].ReplicaLag'
```

**Rollback:**
```bash
# Failback al primary original (cuando esté recuperado)
aws rds failover-db-cluster --db-cluster-identifier fincore-prod --target-db-instance-identifier fincore-prod-instance-1
```

### 6.2 Redis Cluster Recovery

**Síntomas:**
- Sesiones perdidas
- Cache miss rate alto
- Timeout en operaciones MFA

**Pasos:**
```bash
# 1. Verificar estado del cluster
aws elasticache describe-replication-groups --replication-group-id fincore-redis

# 2. Si nodo primario falló, promover replica
aws elasticache modify-replication-group \
  --replication-group-id fincore-redis \
  --primary-cluster-id fincore-redis-002

# 3. Reiniciar pods que dependen de Redis
kubectl rollout restart deployment/api-server -n fincore

# 4. Forzar regeneración de sesiones (usuarios deberán re-login)
# Las sesiones se regenerarán automáticamente

# 5. Verificar conectividad
kubectl exec -it deploy/api-server -- redis-cli -h redis.fincore.local PING
```

### 6.3 API Server Recovery

**Síntomas:**
- 5xx errors aumentando
- Pods en CrashLoopBackOff
- Health checks fallando

**Pasos:**
```bash
# 1. Verificar estado de pods
kubectl get pods -n fincore -l app=api-server

# 2. Ver logs de pods fallando
kubectl logs -n fincore -l app=api-server --tail=100

# 3. Rollback a versión anterior si es deployment reciente
kubectl rollout undo deployment/api-server -n fincore

# 4. Si es problema de recursos, escalar
kubectl scale deployment/api-server --replicas=10 -n fincore

# 5. Si persiste, forzar recreación
kubectl delete pods -n fincore -l app=api-server

# 6. Verificar health
curl -s https://api.fincore.com/health | jq
```

### 6.4 Payment Provider (STP) Failover

**Síntomas:**
- Remesas pendientes aumentando
- Circuit breaker STP abierto
- Timeouts en webhooks

**Pasos:**
```bash
# 1. Verificar estado del circuit breaker
curl -s https://api.fincore.com/circuit-breakers/status -H "x-admin-key: $ADMIN_KEY" | jq

# 2. Activar modo degradado si es necesario
curl -X POST https://api.fincore.com/admin/system/mode \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"mode": "degraded"}'

# 3. Notificar a usuarios via banner
# (Configurar en admin panel)

# 4. Contactar a STP para verificar estado
# Tel: [REDACTED]

# 5. Monitorear cola de remesas pendientes
SELECT COUNT(*) FROM remittances WHERE status = 'pending' AND created_at > NOW() - INTERVAL '1 hour';

# 6. Cuando STP recupere, resetear circuit breaker
curl -X POST https://api.fincore.com/admin/circuit-breaker/stp/reset \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### 6.5 Complete Site Failover (DR)

**Escenario:** Pérdida completa de región primaria

**Tiempo estimado:** 30-60 minutos

**Pasos:**
```bash
# 1. Confirmar pérdida de región primaria
aws ec2 describe-availability-zones --region us-east-1

# 2. Activar DR en región secundaria
./scripts/dr-activate.sh us-west-2

# 3. Actualizar DNS global
aws route53 change-resource-record-sets \
  --hosted-zone-id ZONE_ID \
  --change-batch file://dr-dns-failover.json

# 4. Verificar que Aurora secondary sea writable
aws rds modify-db-cluster \
  --db-cluster-identifier fincore-dr \
  --master-user-password $DB_PASSWORD \
  --apply-immediately

# 5. Escalar pods en región DR
kubectl --context fincore-us-west-2 scale deployment/api-server --replicas=10

# 6. Verificar funcionalidad
curl -s https://api.fincore.com/health

# 7. Notificar a stakeholders
./scripts/notify-stakeholders.sh "DR activated - us-west-2"

# 8. Monitorear métricas críticas
watch -n 5 'curl -s https://api.fincore.com/metrics | grep -E "^(http_requests|error_rate)"'
```

---

## 7. Testing y Validación

### 7.1 Calendario de Pruebas

| Prueba | Frecuencia | Última | Próxima |
|--------|------------|--------|---------|
| Failover DB | Mensual | [DATE] | [DATE] |
| Failover Redis | Mensual | [DATE] | [DATE] |
| DR completo | Trimestral | [DATE] | [DATE] |
| Chaos engineering | Semanal | [DATE] | [DATE] |

### 7.2 Checklist Post-Incidente

- [ ] Incidente documentado en Confluence
- [ ] Timeline de eventos creado
- [ ] Root cause identificado
- [ ] Action items asignados
- [ ] Métricas de impacto registradas
- [ ] Post-mortem meeting programado (SEV1/SEV2)
- [ ] Runbooks actualizados si es necesario

---

## 8. Monitoreo y Alertas

### 8.1 Dashboards Críticos

- **Grafana:** https://grafana.fincore.internal/d/overview
- **CloudWatch:** AWS Console > CloudWatch > Dashboards > FinCore-Prod
- **Status Page:** https://status.fincore.com

### 8.2 Alertas PagerDuty

| Alerta | Condición | Severidad |
|--------|-----------|-----------|
| API Down | Health check fail > 2 min | SEV1 |
| DB Failover | Aurora failover event | SEV1 |
| Error Rate High | 5xx > 5% por 5 min | SEV2 |
| Latency High | P99 > 2s por 10 min | SEV2 |
| Circuit Breaker Open | Cualquier CB abierto | SEV2 |
| Disk Space Low | > 85% usado | SEV3 |
| Certificate Expiring | < 14 días | SEV3 |

---

## 9. Apéndices

### 9.1 Comandos Útiles

```bash
# Estado general del sistema
kubectl get pods -A | grep -v Running

# Logs de los últimos 30 minutos
kubectl logs -n fincore -l app=api-server --since=30m

# Métricas de Redis
redis-cli -h redis.fincore.local INFO stats

# Conexiones de DB activas
psql -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"

# Estado de circuit breakers
curl -s localhost:8000/circuit-breakers/status | jq
```

### 9.2 Credenciales y Accesos

Las credenciales de emergencia están almacenadas en:
- AWS Secrets Manager: `fincore/emergency/credentials`
- 1Password: Vault "FinCore Emergency"

### 9.3 Proveedores y SLAs

| Proveedor | Servicio | SLA | Contacto Emergencia |
|-----------|----------|-----|---------------------|
| AWS | Infraestructura | 99.99% | AWS Support Premium |
| STP | Pagos SPEI | 99.9% | [REDACTED] |
| Bitso | Exchange | 99.5% | [REDACTED] |
| Cloudflare | WAF/CDN | 100% | Enterprise Support |

---

**Documento revisado y aprobado por:**
- CTO: _________________ Fecha: _________
- CISO: _________________ Fecha: _________
- VP Engineering: _________________ Fecha: _________
