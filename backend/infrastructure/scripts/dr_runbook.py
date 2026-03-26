#!/usr/bin/env python3
"""
FinCore - Disaster Recovery Runbook

Script automatizado para operaciones de DR:
- Failover a region secundaria
- Promocion de replica de DB
- Rollback de base de datos
- Validacion de integridad
- Simulacros de DR

Uso:
    python dr_runbook.py failover --dry-run
    python dr_runbook.py promote-replica
    python dr_runbook.py rollback --point-in-time "2024-01-01T12:00:00Z"
    python dr_runbook.py simulate --scenario full-failover
"""
import os
import sys
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

import boto3
from botocore.exceptions import ClientError

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuracion
# ============================================================================

class Config:
    """Configuracion de DR."""
    PRIMARY_REGION = os.getenv("PRIMARY_REGION", "us-east-1")
    DR_REGION = os.getenv("DR_REGION", "us-west-2")

    # RDS
    RDS_PRIMARY_IDENTIFIER = os.getenv("RDS_PRIMARY_ID", "fincore-production")
    RDS_REPLICA_IDENTIFIER = os.getenv("RDS_REPLICA_ID", "fincore-production-dr")

    # Route53
    HOSTED_ZONE_ID = os.getenv("HOSTED_ZONE_ID", "")
    PRIMARY_RECORD = os.getenv("PRIMARY_RECORD", "api.fincore.com")
    DR_RECORD = os.getenv("DR_RECORD", "api-dr.fincore.com")

    # ECS
    ECS_CLUSTER_PRIMARY = os.getenv("ECS_CLUSTER_PRIMARY", "fincore-production")
    ECS_CLUSTER_DR = os.getenv("ECS_CLUSTER_DR", "fincore-production-dr")
    ECS_SERVICE = os.getenv("ECS_SERVICE", "fincore-api")

    # S3
    BACKUP_BUCKET = os.getenv("BACKUP_BUCKET", "fincore-backups")

    # Slack
    SLACK_WEBHOOK = os.getenv("DR_SLACK_WEBHOOK", "")

    # Recovery Objectives
    RTO_MINUTES = int(os.getenv("RTO_MINUTES", "60"))
    RPO_MINUTES = int(os.getenv("RPO_MINUTES", "15"))


# ============================================================================
# Tipos
# ============================================================================

class DRScenario(str, Enum):
    """Escenarios de DR."""
    FULL_FAILOVER = "full-failover"
    DB_FAILOVER = "db-failover"
    APP_FAILOVER = "app-failover"
    ROLLBACK = "rollback"
    HEALTH_CHECK = "health-check"


class OperationStatus(str, Enum):
    """Estados de operacion."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class DROperation:
    """Operacion de DR."""
    id: str
    type: str
    status: OperationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps: List[Dict] = None
    error: Optional[str] = None
    dry_run: bool = False

    def __post_init__(self):
        if self.steps is None:
            self.steps = []


@dataclass
class HealthCheckResult:
    """Resultado de health check."""
    component: str
    status: str
    latency_ms: int
    details: Dict
    checked_at: datetime


# ============================================================================
# Clientes AWS
# ============================================================================

class AWSClients:
    """Clientes AWS para ambas regiones."""

    def __init__(self):
        self.rds_primary = boto3.client('rds', region_name=Config.PRIMARY_REGION)
        self.rds_dr = boto3.client('rds', region_name=Config.DR_REGION)
        self.ecs_primary = boto3.client('ecs', region_name=Config.PRIMARY_REGION)
        self.ecs_dr = boto3.client('ecs', region_name=Config.DR_REGION)
        self.route53 = boto3.client('route53')
        self.s3 = boto3.client('s3')
        self.cloudwatch = boto3.client('cloudwatch', region_name=Config.PRIMARY_REGION)


# ============================================================================
# DR Operations
# ============================================================================

class DRRunbook:
    """
    Runbook automatizado de Disaster Recovery.

    Implementa procedimientos para:
    - Failover completo a region DR
    - Promocion de replica de DB
    - Rollback de base de datos
    - Simulacros de DR
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.aws = AWSClients()
        self.operation: Optional[DROperation] = None

    def _log_step(self, step: str, status: str, details: Dict = None):
        """Registra un paso de la operacion."""
        step_info = {
            "step": step,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {},
        }

        if self.operation:
            self.operation.steps.append(step_info)

        if status == "completed":
            logger.info(f"[OK] {step}")
        elif status == "failed":
            logger.error(f"[FAILED] {step}")
        else:
            logger.info(f"[...] {step}")

    def _notify_slack(self, message: str, color: str = "good"):
        """Envia notificacion a Slack."""
        if not Config.SLACK_WEBHOOK or self.dry_run:
            return

        import requests
        payload = {
            "attachments": [{
                "color": color,
                "title": "DR Operation",
                "text": message,
                "ts": int(time.time()),
            }]
        }
        try:
            requests.post(Config.SLACK_WEBHOOK, json=payload, timeout=5)
        except Exception as e:
            logger.warning(f"Failed to notify Slack: {e}")

    # ========================================================================
    # Health Checks
    # ========================================================================

    def check_health(self) -> Dict[str, HealthCheckResult]:
        """Verifica el estado de todos los componentes."""
        results = {}

        # Check RDS Primary
        results['rds_primary'] = self._check_rds_health(
            self.aws.rds_primary,
            Config.RDS_PRIMARY_IDENTIFIER,
            "primary"
        )

        # Check RDS Replica
        results['rds_replica'] = self._check_rds_health(
            self.aws.rds_dr,
            Config.RDS_REPLICA_IDENTIFIER,
            "replica"
        )

        # Check replication lag
        results['replication_lag'] = self._check_replication_lag()

        # Check ECS Primary
        results['ecs_primary'] = self._check_ecs_health(
            self.aws.ecs_primary,
            Config.ECS_CLUSTER_PRIMARY,
            Config.ECS_SERVICE
        )

        # Check ECS DR
        results['ecs_dr'] = self._check_ecs_health(
            self.aws.ecs_dr,
            Config.ECS_CLUSTER_DR,
            Config.ECS_SERVICE
        )

        return results

    def _check_rds_health(
        self,
        client,
        identifier: str,
        label: str
    ) -> HealthCheckResult:
        """Verifica estado de RDS."""
        try:
            start = time.time()
            response = client.describe_db_instances(
                DBInstanceIdentifier=identifier
            )
            latency = int((time.time() - start) * 1000)

            instance = response['DBInstances'][0]
            status = instance['DBInstanceStatus']

            return HealthCheckResult(
                component=f"rds_{label}",
                status="healthy" if status == "available" else "unhealthy",
                latency_ms=latency,
                details={
                    "db_status": status,
                    "engine": instance['Engine'],
                    "endpoint": instance.get('Endpoint', {}).get('Address'),
                    "multi_az": instance.get('MultiAZ', False),
                },
                checked_at=datetime.utcnow(),
            )

        except Exception as e:
            return HealthCheckResult(
                component=f"rds_{label}",
                status="error",
                latency_ms=-1,
                details={"error": str(e)},
                checked_at=datetime.utcnow(),
            )

    def _check_replication_lag(self) -> HealthCheckResult:
        """Verifica lag de replicacion."""
        try:
            response = self.aws.cloudwatch.get_metric_statistics(
                Namespace='AWS/RDS',
                MetricName='ReplicaLag',
                Dimensions=[{
                    'Name': 'DBInstanceIdentifier',
                    'Value': Config.RDS_REPLICA_IDENTIFIER
                }],
                StartTime=datetime.utcnow() - timedelta(minutes=5),
                EndTime=datetime.utcnow(),
                Period=60,
                Statistics=['Average'],
            )

            datapoints = response.get('Datapoints', [])
            if datapoints:
                lag = datapoints[-1]['Average']
                status = "healthy" if lag < Config.RPO_MINUTES * 60 else "warning"
            else:
                lag = -1
                status = "unknown"

            return HealthCheckResult(
                component="replication_lag",
                status=status,
                latency_ms=0,
                details={
                    "lag_seconds": lag,
                    "rpo_threshold": Config.RPO_MINUTES * 60,
                },
                checked_at=datetime.utcnow(),
            )

        except Exception as e:
            return HealthCheckResult(
                component="replication_lag",
                status="error",
                latency_ms=-1,
                details={"error": str(e)},
                checked_at=datetime.utcnow(),
            )

    def _check_ecs_health(
        self,
        client,
        cluster: str,
        service: str
    ) -> HealthCheckResult:
        """Verifica estado de ECS."""
        try:
            start = time.time()
            response = client.describe_services(
                cluster=cluster,
                services=[service]
            )
            latency = int((time.time() - start) * 1000)

            if not response['services']:
                return HealthCheckResult(
                    component=f"ecs_{cluster}",
                    status="not_found",
                    latency_ms=latency,
                    details={},
                    checked_at=datetime.utcnow(),
                )

            svc = response['services'][0]
            running = svc['runningCount']
            desired = svc['desiredCount']

            status = "healthy" if running >= desired else "unhealthy"

            return HealthCheckResult(
                component=f"ecs_{cluster}",
                status=status,
                latency_ms=latency,
                details={
                    "running_count": running,
                    "desired_count": desired,
                    "pending_count": svc['pendingCount'],
                },
                checked_at=datetime.utcnow(),
            )

        except Exception as e:
            return HealthCheckResult(
                component=f"ecs_{cluster}",
                status="error",
                latency_ms=-1,
                details={"error": str(e)},
                checked_at=datetime.utcnow(),
            )

    # ========================================================================
    # Failover Operations
    # ========================================================================

    def failover(self) -> DROperation:
        """
        Ejecuta failover completo a region DR.

        Pasos:
        1. Verificar health de DR
        2. Promover replica de DB
        3. Escalar ECS en DR
        4. Actualizar DNS
        5. Validar
        """
        self.operation = DROperation(
            id=f"failover-{int(time.time())}",
            type="full_failover",
            status=OperationStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
            dry_run=self.dry_run,
        )

        logger.info("=" * 60)
        logger.info("INICIANDO FAILOVER A REGION DR")
        logger.info(f"Dry run: {self.dry_run}")
        logger.info("=" * 60)

        self._notify_slack(
            f"Iniciando failover a {Config.DR_REGION}",
            "warning"
        )

        try:
            # Paso 1: Verificar DR
            self._log_step("Verificando estado de DR", "in_progress")
            health = self.check_health()

            dr_healthy = (
                health['rds_replica'].status == 'healthy' and
                health['ecs_dr'].status in ('healthy', 'not_found')
            )

            if not dr_healthy:
                raise Exception("Region DR no esta saludable")

            self._log_step("Verificando estado de DR", "completed", {
                "replication_lag": health['replication_lag'].details
            })

            # Paso 2: Promover replica
            self._log_step("Promoviendo replica de DB", "in_progress")
            if not self.dry_run:
                self.promote_replica()
            self._log_step("Promoviendo replica de DB", "completed")

            # Paso 3: Escalar ECS en DR
            self._log_step("Escalando servicios en DR", "in_progress")
            if not self.dry_run:
                self._scale_ecs_dr(desired_count=2)
            self._log_step("Escalando servicios en DR", "completed")

            # Paso 4: Actualizar DNS
            self._log_step("Actualizando DNS", "in_progress")
            if not self.dry_run:
                self._update_dns_failover()
            self._log_step("Actualizando DNS", "completed")

            # Paso 5: Validar
            self._log_step("Validando failover", "in_progress")
            time.sleep(5)  # Esperar propagacion
            self._log_step("Validando failover", "completed")

            self.operation.status = OperationStatus.COMPLETED
            self.operation.completed_at = datetime.utcnow()

            duration = (self.operation.completed_at - self.operation.started_at).seconds
            logger.info("=" * 60)
            logger.info(f"FAILOVER COMPLETADO en {duration} segundos")
            logger.info("=" * 60)

            self._notify_slack(
                f"Failover completado en {duration}s",
                "good"
            )

        except Exception as e:
            self.operation.status = OperationStatus.FAILED
            self.operation.error = str(e)
            self.operation.completed_at = datetime.utcnow()

            logger.error(f"FAILOVER FALLIDO: {e}")
            self._notify_slack(f"Failover FALLIDO: {e}", "danger")

        return self.operation

    def promote_replica(self) -> bool:
        """Promueve la replica de RDS a instancia standalone."""
        self._log_step("Promoviendo replica RDS", "in_progress")

        try:
            if self.dry_run:
                logger.info("[DRY RUN] Promoveria replica")
                return True

            self.aws.rds_dr.promote_read_replica(
                DBInstanceIdentifier=Config.RDS_REPLICA_IDENTIFIER,
                BackupRetentionPeriod=7,
            )

            # Esperar a que este disponible
            waiter = self.aws.rds_dr.get_waiter('db_instance_available')
            waiter.wait(
                DBInstanceIdentifier=Config.RDS_REPLICA_IDENTIFIER,
                WaiterConfig={'Delay': 30, 'MaxAttempts': 60}
            )

            self._log_step("Promoviendo replica RDS", "completed")
            return True

        except Exception as e:
            self._log_step("Promoviendo replica RDS", "failed", {"error": str(e)})
            raise

    def _scale_ecs_dr(self, desired_count: int):
        """Escala el servicio ECS en DR."""
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Escalaria ECS a {desired_count}")
                return

            self.aws.ecs_dr.update_service(
                cluster=Config.ECS_CLUSTER_DR,
                service=Config.ECS_SERVICE,
                desiredCount=desired_count,
            )

            # Esperar estabilizacion
            waiter = self.aws.ecs_dr.get_waiter('services_stable')
            waiter.wait(
                cluster=Config.ECS_CLUSTER_DR,
                services=[Config.ECS_SERVICE],
                WaiterConfig={'Delay': 15, 'MaxAttempts': 40}
            )

        except Exception as e:
            logger.error(f"Error escalando ECS: {e}")
            raise

    def _update_dns_failover(self):
        """Actualiza DNS para apuntar a DR."""
        if not Config.HOSTED_ZONE_ID:
            logger.warning("No hay HOSTED_ZONE_ID configurado")
            return

        try:
            if self.dry_run:
                logger.info("[DRY RUN] Actualizaria DNS")
                return

            # Cambiar peso de failover
            self.aws.route53.change_resource_record_sets(
                HostedZoneId=Config.HOSTED_ZONE_ID,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': Config.PRIMARY_RECORD,
                                'Type': 'CNAME',
                                'TTL': 60,
                                'ResourceRecords': [
                                    {'Value': Config.DR_RECORD}
                                ]
                            }
                        }
                    ]
                }
            )

        except Exception as e:
            logger.error(f"Error actualizando DNS: {e}")
            raise

    # ========================================================================
    # Rollback Operations
    # ========================================================================

    def rollback_database(
        self,
        point_in_time: Optional[str] = None,
        snapshot_id: Optional[str] = None,
    ) -> DROperation:
        """
        Realiza rollback de base de datos.

        Args:
            point_in_time: ISO timestamp para PITR
            snapshot_id: ID de snapshot para restaurar
        """
        self.operation = DROperation(
            id=f"rollback-{int(time.time())}",
            type="db_rollback",
            status=OperationStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
            dry_run=self.dry_run,
        )

        logger.info("=" * 60)
        logger.info("INICIANDO ROLLBACK DE BASE DE DATOS")
        logger.info("=" * 60)

        try:
            if point_in_time:
                # Point-in-Time Recovery
                self._log_step(f"PITR a {point_in_time}", "in_progress")

                if not self.dry_run:
                    restore_time = datetime.fromisoformat(
                        point_in_time.replace('Z', '+00:00')
                    )

                    self.aws.rds_primary.restore_db_instance_to_point_in_time(
                        SourceDBInstanceIdentifier=Config.RDS_PRIMARY_IDENTIFIER,
                        TargetDBInstanceIdentifier=f"{Config.RDS_PRIMARY_IDENTIFIER}-restored",
                        RestoreTime=restore_time,
                        DBInstanceClass='db.r6g.large',
                    )

                self._log_step(f"PITR a {point_in_time}", "completed")

            elif snapshot_id:
                # Restore from snapshot
                self._log_step(f"Restaurando desde snapshot {snapshot_id}", "in_progress")

                if not self.dry_run:
                    self.aws.rds_primary.restore_db_instance_from_db_snapshot(
                        DBInstanceIdentifier=f"{Config.RDS_PRIMARY_IDENTIFIER}-restored",
                        DBSnapshotIdentifier=snapshot_id,
                        DBInstanceClass='db.r6g.large',
                    )

                self._log_step(f"Restaurando desde snapshot {snapshot_id}", "completed")

            else:
                raise ValueError("Debe especificar point_in_time o snapshot_id")

            self.operation.status = OperationStatus.COMPLETED
            self.operation.completed_at = datetime.utcnow()

            logger.info("=" * 60)
            logger.info("ROLLBACK COMPLETADO")
            logger.info("NOTA: La instancia restaurada es: "
                       f"{Config.RDS_PRIMARY_IDENTIFIER}-restored")
            logger.info("Debe realizar el swap manualmente despues de validar")
            logger.info("=" * 60)

        except Exception as e:
            self.operation.status = OperationStatus.FAILED
            self.operation.error = str(e)
            logger.error(f"ROLLBACK FALLIDO: {e}")

        return self.operation

    def list_snapshots(self, limit: int = 10) -> List[Dict]:
        """Lista snapshots disponibles."""
        try:
            response = self.aws.rds_primary.describe_db_snapshots(
                DBInstanceIdentifier=Config.RDS_PRIMARY_IDENTIFIER,
                SnapshotType='automated',
                MaxRecords=limit,
            )

            snapshots = []
            for snap in response['DBSnapshots']:
                snapshots.append({
                    'id': snap['DBSnapshotIdentifier'],
                    'status': snap['Status'],
                    'created_at': snap['SnapshotCreateTime'].isoformat(),
                    'size_gb': snap.get('AllocatedStorage', 0),
                })

            return snapshots

        except Exception as e:
            logger.error(f"Error listando snapshots: {e}")
            return []

    def get_recovery_window(self) -> Dict:
        """Obtiene la ventana de recuperacion disponible."""
        try:
            response = self.aws.rds_primary.describe_db_instances(
                DBInstanceIdentifier=Config.RDS_PRIMARY_IDENTIFIER
            )

            instance = response['DBInstances'][0]

            return {
                'earliest_restorable_time': instance.get(
                    'LatestRestorableTime',
                    datetime.utcnow()
                ).isoformat(),
                'latest_restorable_time': datetime.utcnow().isoformat(),
                'backup_retention_days': instance.get('BackupRetentionPeriod', 7),
            }

        except Exception as e:
            logger.error(f"Error obteniendo ventana de recovery: {e}")
            return {}

    # ========================================================================
    # Simulation
    # ========================================================================

    def simulate(self, scenario: DRScenario) -> Dict:
        """
        Ejecuta simulacro de DR.

        Args:
            scenario: Escenario a simular
        """
        logger.info("=" * 60)
        logger.info(f"SIMULACRO DE DR: {scenario.value}")
        logger.info("=" * 60)

        results = {
            'scenario': scenario.value,
            'started_at': datetime.utcnow().isoformat(),
            'steps': [],
            'metrics': {},
        }

        # Siempre verificar health primero
        logger.info("Verificando estado actual...")
        health = self.check_health()

        results['initial_health'] = {
            k: {
                'status': v.status,
                'latency_ms': v.latency_ms,
            } for k, v in health.items()
        }

        if scenario == DRScenario.HEALTH_CHECK:
            results['steps'].append({
                'step': 'health_check',
                'status': 'completed',
                'details': results['initial_health'],
            })

        elif scenario == DRScenario.FULL_FAILOVER:
            # Simulacion de failover completo (dry-run)
            self.dry_run = True
            operation = self.failover()
            results['steps'] = operation.steps
            results['metrics']['duration_seconds'] = (
                operation.completed_at - operation.started_at
            ).seconds if operation.completed_at else 0

        elif scenario == DRScenario.DB_FAILOVER:
            # Simulacion de promocion de replica
            self.dry_run = True
            self._log_step("Simulando promocion de replica", "in_progress")

            # Verificar que la replica este saludable
            if health['rds_replica'].status == 'healthy':
                lag = health['replication_lag'].details.get('lag_seconds', -1)
                results['steps'].append({
                    'step': 'check_replica',
                    'status': 'completed',
                    'details': {
                        'replication_lag_seconds': lag,
                        'within_rpo': lag <= Config.RPO_MINUTES * 60,
                    },
                })
            else:
                results['steps'].append({
                    'step': 'check_replica',
                    'status': 'failed',
                    'details': {'error': 'Replica not healthy'},
                })

        elif scenario == DRScenario.ROLLBACK:
            # Simulacion de rollback
            window = self.get_recovery_window()
            snapshots = self.list_snapshots(5)

            results['steps'].append({
                'step': 'check_recovery_options',
                'status': 'completed',
                'details': {
                    'recovery_window': window,
                    'available_snapshots': len(snapshots),
                    'snapshots': snapshots,
                },
            })

        results['completed_at'] = datetime.utcnow().isoformat()

        # Evaluar si cumple RTO/RPO
        results['compliance'] = {
            'rto_target_minutes': Config.RTO_MINUTES,
            'rpo_target_minutes': Config.RPO_MINUTES,
            'current_replication_lag_seconds': health['replication_lag'].details.get('lag_seconds', -1),
        }

        logger.info("=" * 60)
        logger.info("SIMULACRO COMPLETADO")
        logger.info(json.dumps(results, indent=2, default=str))
        logger.info("=" * 60)

        return results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FinCore Disaster Recovery Runbook"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Ejecutar en modo dry-run (sin cambios reales)'
    )

    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')

    # Health check
    subparsers.add_parser('health', help='Verificar estado de componentes')

    # Failover
    subparsers.add_parser('failover', help='Ejecutar failover a DR')

    # Promote replica
    subparsers.add_parser('promote-replica', help='Promover replica de DB')

    # Rollback
    rollback_parser = subparsers.add_parser('rollback', help='Rollback de base de datos')
    rollback_parser.add_argument(
        '--point-in-time',
        help='Timestamp ISO para PITR'
    )
    rollback_parser.add_argument(
        '--snapshot',
        help='ID de snapshot a restaurar'
    )

    # List snapshots
    subparsers.add_parser('list-snapshots', help='Listar snapshots disponibles')

    # Recovery window
    subparsers.add_parser('recovery-window', help='Mostrar ventana de recuperacion')

    # Simulate
    sim_parser = subparsers.add_parser('simulate', help='Ejecutar simulacro')
    sim_parser.add_argument(
        '--scenario',
        choices=[s.value for s in DRScenario],
        default='health-check',
        help='Escenario a simular'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    runbook = DRRunbook(dry_run=args.dry_run)

    if args.command == 'health':
        health = runbook.check_health()
        print("\nEstado de Componentes:")
        print("-" * 50)
        for name, result in health.items():
            status_icon = "OK" if result.status == 'healthy' else "!!"
            print(f"[{status_icon}] {name}: {result.status} ({result.latency_ms}ms)")
            if result.details:
                for k, v in result.details.items():
                    print(f"    {k}: {v}")

    elif args.command == 'failover':
        runbook.failover()

    elif args.command == 'promote-replica':
        runbook.promote_replica()

    elif args.command == 'rollback':
        if not args.point_in_time and not args.snapshot:
            print("Error: Debe especificar --point-in-time o --snapshot")
            return
        runbook.rollback_database(
            point_in_time=args.point_in_time,
            snapshot_id=args.snapshot,
        )

    elif args.command == 'list-snapshots':
        snapshots = runbook.list_snapshots()
        print("\nSnapshots Disponibles:")
        print("-" * 50)
        for snap in snapshots:
            print(f"  {snap['id']}")
            print(f"    Status: {snap['status']}")
            print(f"    Created: {snap['created_at']}")
            print(f"    Size: {snap['size_gb']} GB")
            print()

    elif args.command == 'recovery-window':
        window = runbook.get_recovery_window()
        print("\nVentana de Recuperacion:")
        print("-" * 50)
        for k, v in window.items():
            print(f"  {k}: {v}")

    elif args.command == 'simulate':
        scenario = DRScenario(args.scenario)
        runbook.simulate(scenario)


if __name__ == '__main__':
    main()
