# Protocolos de Emergencia - FinCore

## Tabla de Contenidos

1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Equipo de Respuesta](#equipo-de-respuesta)
3. [Kill Switch](#kill-switch)
4. [Incidentes de Seguridad](#incidentes-de-seguridad)
5. [Recuperacion ante Desastres](#recuperacion-ante-desastres)
6. [Comunicaciones](#comunicaciones)
7. [Procedimientos Post-Incidente](#procedimientos-post-incidente)

---

## Resumen Ejecutivo

Este documento establece los protocolos de emergencia para FinCore, una plataforma de remesas blockchain. Los procedimientos aqui descritos deben ser seguidos estrictamente en caso de:

- Brechas de seguridad
- Exploits de smart contracts
- Fallas de infraestructura critica
- Incidentes regulatorios
- Manipulacion de oracles/precios

**Tiempo Maximo de Respuesta (SLA):**

| Severidad | Tiempo de Respuesta | Tiempo de Resolucion |
|-----------|--------------------|-----------------------|
| CRITICAL  | 15 minutos         | 4 horas              |
| HIGH      | 30 minutos         | 8 horas              |
| MEDIUM    | 2 horas            | 24 horas             |
| LOW       | 24 horas           | 72 horas             |

---

## Equipo de Respuesta

### Roles y Responsabilidades

```
+---------------------------+
|    INCIDENT COMMANDER     |
|   (Decision final)        |
+---------------------------+
           |
    +------+------+
    |             |
+-------+    +---------+
| TECH  |    | COMMS   |
| LEAD  |    | LEAD    |
+-------+    +---------+
    |
+---+---+---+
|   |   |   |
SEC DEV OPS BIZ
```

### Contactos de Emergencia

| Rol | Primario | Secundario | Escalacion |
|-----|----------|------------|------------|
| Incident Commander | CTO | VP Engineering | CEO |
| Tech Lead | Lead Backend | Lead Blockchain | CTO |
| Security Lead | CISO | Security Engineer | CTO |
| Comms Lead | Head of Comms | Legal Counsel | CEO |
| On-Call Engineer | Rotativo | Backup | Tech Lead |

### Canales de Comunicacion

- **Slack**: #incident-response (primario)
- **PagerDuty**: Alertas criticas automaticas
- **War Room**: meet.google.com/fincore-emergency
- **Telefono**: Linea de emergencia 24/7

---

## Kill Switch

### Que es el Kill Switch?

El Kill Switch es un mecanismo de emergencia que pausa **todas** las operaciones criticas de FinCore de forma inmediata.

### Cuando Activar

**ACTIVAR INMEDIATAMENTE si:**

1. Se detecta un exploit activo en smart contracts
2. Hay evidencia de acceso no autorizado a wallets operativas
3. Se observa drenaje de fondos no explicado
4. Los oracles reportan precios anormales (>20% desviacion)
5. Se recibe notificacion de vulnerabilidad 0-day
6. Orden regulatoria de suspension

**NO activar por:**

- Alertas de bajo nivel no confirmadas
- Errores de UI/UX
- Latencia temporal
- Falsos positivos aislados

### Procedimiento de Activacion

#### Paso 1: Validar la Amenaza (< 5 min)

```bash
# Verificar alertas activas
curl -s http://localhost:8000/api/v1/admin/security/alerts?severity=critical

# Verificar transacciones recientes sospechosas
curl -s http://localhost:8000/api/v1/admin/transactions/anomalies
```

#### Paso 2: Notificar al Equipo

```
@incident-team ALERTA: Posible [descripcion]. Evaluando activacion de Kill Switch.
```

#### Paso 3: Activar Kill Switch

**Via API (preferido):**

```bash
curl -X POST http://localhost:8000/api/v1/admin/security/kill-switch \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "DESCRIPCION_DEL_INCIDENTE",
    "initiated_by": "email@fincore.com",
    "affected_services": ["remittance_service", "relayer_service"],
    "estimated_resolution": "2024-01-01T12:00:00Z"
  }'
```

**Via Dashboard Admin:**

1. Navegar a /admin/security
2. Click en "ACTIVAR KILL SWITCH"
3. Completar formulario con razon
4. Confirmar con segundo factor (requiere 2 admins)

**Via CLI de Emergencia:**

```bash
python -m app.cli.emergency activate-kill-switch \
  --reason "Exploit detectado" \
  --initiator "admin@fincore.com"
```

#### Paso 4: Pausar Smart Contracts (si aplica)

Los contratos FinCoreRemittance tienen funcion `pause()` que requiere multisig:

```solidity
// Requiere 2 de 3 firmantes
safe.createTransaction({
    to: remittanceContract,
    data: "0x8456cb59", // pause()
    value: 0
});
```

### Procedimiento de Desactivacion

**SOLO desactivar cuando:**

1. La amenaza ha sido neutralizada
2. Se han implementado mitigaciones
3. El equipo de seguridad autoriza
4. Se ha documentado el incidente

```bash
curl -X DELETE http://localhost:8000/api/v1/admin/security/kill-switch \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "initiated_by": "email@fincore.com",
    "resolution_notes": "Vulnerability patched in commit abc123"
  }'
```

---

## Incidentes de Seguridad

### Clasificacion de Incidentes

#### Nivel 1: CRITICAL - Brecha Activa

- Fondos en riesgo inmediato
- Acceso no autorizado confirmado
- Exploit activo

**Acciones:**
1. Activar Kill Switch inmediatamente
2. Convocar War Room
3. Notificar a reguladores si hay fuga de datos
4. Preservar evidencia forense

#### Nivel 2: HIGH - Vulnerabilidad Confirmada

- Vulnerabilidad explotable identificada
- Sin evidencia de explotacion actual
- Riesgo significativo

**Acciones:**
1. Evaluar necesidad de Kill Switch
2. Implementar mitigacion temporal
3. Desplegar parche en < 8 horas
4. Monitoreo intensivo

#### Nivel 3: MEDIUM - Anomalia

- Comportamiento inusual
- Requiere investigacion
- Sin riesgo inmediato

**Acciones:**
1. Investigar causa raiz
2. Documentar hallazgos
3. Planificar remediacion

#### Nivel 4: LOW - Informativo

- Alertas de bajo impacto
- Mejoras de seguridad
- Falsos positivos

**Acciones:**
1. Registrar en sistema de tickets
2. Revisar en proxima iteracion

### Playbooks por Tipo de Incidente

#### Playbook: Exploit de Smart Contract

```
T+0:00  Detectar anomalia (alertas automaticas o reporte)
T+0:05  Validar que es un exploit real
T+0:10  ACTIVAR KILL SWITCH
T+0:15  Pausar contratos via multisig
T+0:20  Convocar War Room
T+0:30  Analisis forense inicial
T+1:00  Comunicado interno
T+2:00  Comunicado a usuarios afectados
T+4:00  Plan de remediacion
T+24:00 Post-mortem inicial
```

#### Playbook: Fuga de Claves Privadas

```
T+0:00  Detectar compromiso de claves
T+0:05  ACTIVAR KILL SWITCH
T+0:10  Revocar acceso de clave comprometida
T+0:15  Mover fondos a nueva wallet (si es posible)
T+0:30  Rotar TODOS los secretos relacionados
T+1:00  Investigar alcance del compromiso
T+2:00  Notificar a usuarios si hay datos expuestos
```

#### Playbook: Ataque DDoS

```
T+0:00  Detectar degradacion de servicio
T+0:05  Confirmar ataque DDoS (no falla interna)
T+0:10  Activar protecciones adicionales (Cloudflare/WAF)
T+0:15  Escalar con proveedor de mitigacion
T+0:30  Comunicar estado a usuarios
T+1:00  Evaluar necesidad de Kill Switch
```

---

## Recuperacion ante Desastres

### Objetivos de Recuperacion

| Metrica | Objetivo | Descripcion |
|---------|----------|-------------|
| RTO (Recovery Time Objective) | 4 horas | Tiempo maximo para restaurar operaciones |
| RPO (Recovery Point Objective) | 15 minutos | Perdida maxima de datos aceptable |
| MTTR (Mean Time To Recovery) | 2 horas | Tiempo promedio de recuperacion |

### Backups y Replicacion

#### Base de Datos

```yaml
PostgreSQL:
  - Backup: Cada 15 minutos (WAL archiving)
  - Replica: Standby sincrono en otra region
  - Retencion: 30 dias
  - Ubicacion: AWS S3 (encriptado)
```

#### Blockchain State

```yaml
Indexed Data:
  - The Graph: Redundante en 3 indexers
  - Custom Index: Replica cada 5 minutos
  - Events: Log permanente en S3
```

#### Secrets

```yaml
HashiCorp Vault:
  - Backup: Cada hora (snapshots)
  - Replicacion: Multi-region
  - Rotacion: Automatica cada 24h
```

### Procedimiento de Recuperacion

#### Escenario: Falla Total de Region

1. **Deteccion** (T+0:00)
   - Alertas de monitoreo
   - Confirmacion manual

2. **Decision** (T+0:10)
   - Evaluar si es temporal o prolongado
   - Decidir failover a region secundaria

3. **Failover** (T+0:15)
   ```bash
   # Actualizar DNS
   aws route53 change-resource-record-sets \
     --hosted-zone-id Z1234567890 \
     --change-batch file://failover-dns.json

   # Promover replica de DB
   aws rds promote-read-replica \
     --db-instance-identifier fincore-replica-us-west-2
   ```

4. **Validacion** (T+0:30)
   - Verificar conectividad
   - Ejecutar health checks
   - Confirmar integridad de datos

5. **Comunicacion** (T+0:45)
   - Notificar a usuarios
   - Actualizar status page

---

## Comunicaciones

### Templates de Comunicacion

#### Template: Incidente en Progreso

```
ASUNTO: [URGENTE] Incidente de Servicio - FinCore

Estimado usuario,

Estamos experimentando dificultades tecnicas que pueden afectar
temporalmente algunos servicios de FinCore.

ESTADO: En investigacion
IMPACTO: [Describir servicios afectados]
INICIO: [Timestamp]

Nuestro equipo esta trabajando para resolver el problema.
Actualizaremos cada 30 minutos.

Para consultas urgentes: emergency@fincore.com

- Equipo FinCore
```

#### Template: Resolucion

```
ASUNTO: [RESUELTO] Incidente de Servicio - FinCore

Estimado usuario,

El incidente reportado anteriormente ha sido resuelto.

RESOLUCION: [Timestamp]
DURACION: [X horas/minutos]
CAUSA: [Breve descripcion]

Nos disculpamos por cualquier inconveniente causado.

- Equipo FinCore
```

### Canales de Comunicacion

| Audiencia | Canal | Frecuencia |
|-----------|-------|------------|
| Equipo Interno | Slack #incident-response | Tiempo real |
| Usuarios | Email + Status Page | Cada 30 min |
| Reguladores | Email oficial | Segun requerimiento |
| Prensa | Solo via PR | Por aprobacion |

---

## Procedimientos Post-Incidente

### Post-Mortem

Completar dentro de 72 horas del incidente:

```markdown
# Post-Mortem: [Titulo del Incidente]

**Fecha:** YYYY-MM-DD
**Severidad:** CRITICAL/HIGH/MEDIUM/LOW
**Duracion:** X horas
**Impacto:** [Descripcion del impacto]

## Timeline

| Hora | Evento |
|------|--------|
| HH:MM | Descripcion |

## Causa Raiz

[Analisis detallado]

## Que Funciono Bien

- Item 1
- Item 2

## Que Se Puede Mejorar

- Item 1
- Item 2

## Acciones Correctivas

| Accion | Responsable | Fecha Limite |
|--------|-------------|--------------|
| | | |

## Lecciones Aprendidas

[Narrativa]
```

### Revision de Controles

Despues de cada incidente CRITICAL o HIGH:

- [ ] Revisar efectividad del Kill Switch
- [ ] Evaluar tiempos de respuesta vs SLA
- [ ] Verificar que alertas funcionaron
- [ ] Actualizar runbooks si es necesario
- [ ] Programar simulacro de seguimiento

---

## Anexos

### A. Comandos Utiles

```bash
# Estado del sistema
curl http://localhost:8000/health

# Alertas activas
curl http://localhost:8000/api/v1/admin/security/alerts

# Estado del Kill Switch
curl http://localhost:8000/api/v1/admin/security/kill-switch/status

# Metricas de seguridad
curl http://localhost:9090/metrics | grep security_

# Logs de emergencia
kubectl logs -l app=fincore -n production --since=1h

# Transacciones pendientes
curl http://localhost:8000/api/v1/admin/transactions/pending
```

### B. Checksums de Contratos

```
FinCoreRemittance (Polygon): 0x...
  Bytecode Hash: keccak256(...)

FinCoreToken (Polygon): 0x...
  Bytecode Hash: keccak256(...)
```

### C. Contactos de Proveedores

| Proveedor | Servicio | Contacto Emergencia |
|-----------|----------|---------------------|
| AWS | Infraestructura | aws.amazon.com/support |
| Cloudflare | CDN/WAF | cloudflare.com/support |
| PagerDuty | Alertas | support@pagerduty.com |
| Alchemy | RPC Nodes | support@alchemy.com |
| Safe | Multisig | support@safe.global |

---

**Ultima actualizacion:** 2026-03-25
**Proxima revision:** Trimestral
**Responsable:** CISO / CTO
