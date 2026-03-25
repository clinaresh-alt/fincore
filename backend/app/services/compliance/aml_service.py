"""
Servicio AML (Anti Money Laundering) - Prevencion de Lavado de Dinero.

Implementa:
- Monitoreo de transacciones en tiempo real
- Deteccion de patrones sospechosos
- Sistema de alertas automaticas
- Reglas configurables de deteccion

Reglas base segun LFPIORPI:
- Operaciones >= $7,500 USD (efectivo)
- Operaciones >= $15,000 USD (activos virtuales)
- Fraccionamiento (structuring)
- Patrones inusuales
"""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.compliance import (
    AMLAlert,
    AMLRule,
    TransactionMonitor,
    KYCProfile,
    AlertType,
    AlertSeverity,
    AlertStatus,
    RiskLevel,
)


@dataclass
class TransactionData:
    """Datos de transaccion para analisis."""
    user_id: uuid.UUID
    transaction_type: str
    amount: Decimal
    currency: str = "MXN"
    source_type: Optional[str] = None
    source_identifier: Optional[str] = None
    destination_type: Optional[str] = None
    destination_identifier: Optional[str] = None
    blockchain_network: Optional[str] = None
    tx_hash: Optional[str] = None
    ip_address: Optional[str] = None
    country_code: Optional[str] = None


class AMLService:
    """Servicio de monitoreo AML."""

    # Umbrales de reporte (MXN)
    THRESHOLDS = {
        "cash_report": Decimal("145000"),      # ~7,500 USD
        "virtual_asset_report": Decimal("290000"),  # ~15,000 USD
        "large_transaction": Decimal("500000"),
        "structuring_threshold": Decimal("140000"),  # Justo bajo el limite
    }

    # Paises de alto riesgo (GAFI)
    HIGH_RISK_COUNTRIES = {
        "AF", "IR", "KP", "SY", "YE",  # Lista GAFI
        "VE", "CU", "NI",  # Sanciones
    }

    def __init__(self, db: Session):
        self.db = db
        self._load_rules()

    def _load_rules(self):
        """Carga reglas activas de la BD."""
        self.rules = self.db.query(AMLRule).filter(
            AMLRule.is_active == True
        ).all()

    # ============ Transaction Monitoring ============

    def analyze_transaction(
        self,
        transaction: TransactionData
    ) -> List[AMLAlert]:
        """
        Analiza transaccion y genera alertas si corresponde.
        Ejecuta todas las reglas de deteccion.
        """
        alerts = []

        # Registrar transaccion
        monitor = self._record_transaction(transaction)

        # Ejecutar reglas de deteccion
        alerts.extend(self._check_large_transaction(transaction))
        alerts.extend(self._check_structuring(transaction))
        alerts.extend(self._check_rapid_movement(transaction))
        alerts.extend(self._check_high_risk_country(transaction))
        alerts.extend(self._check_pep_transaction(transaction))
        alerts.extend(self._check_unusual_pattern(transaction))

        # Calcular risk score de la transaccion
        risk_score = self._calculate_transaction_risk(transaction, alerts)
        monitor.risk_score = risk_score
        monitor.flagged = len(alerts) > 0

        if alerts:
            monitor.rules_triggered = [a.rule_id for a in alerts]
            monitor.alerts_generated = [str(a.id) for a in alerts]

        self.db.commit()

        return alerts

    def _record_transaction(self, tx: TransactionData) -> TransactionMonitor:
        """Registra transaccion en el monitor."""
        monitor = TransactionMonitor(
            user_id=tx.user_id,
            transaction_type=tx.transaction_type,
            amount=tx.amount,
            currency=tx.currency,
            source_type=tx.source_type,
            source_identifier=tx.source_identifier,
            destination_type=tx.destination_type,
            destination_identifier=tx.destination_identifier,
            blockchain_network=tx.blockchain_network,
            tx_hash=tx.tx_hash,
            ip_address=tx.ip_address,
            country_code=tx.country_code,
        )
        self.db.add(monitor)
        self.db.flush()
        return monitor

    # ============ Detection Rules ============

    def _check_large_transaction(
        self,
        tx: TransactionData
    ) -> List[AMLAlert]:
        """Detecta transacciones grandes que requieren reporte."""
        alerts = []

        threshold = self.THRESHOLDS["virtual_asset_report"]

        if tx.amount >= threshold:
            alert = AMLAlert(
                user_id=tx.user_id,
                alert_type=AlertType.LARGE_TRANSACTION,
                severity=AlertSeverity.HIGH,
                title=f"Transaccion grande: {tx.amount:,.2f} {tx.currency}",
                description=(
                    f"Transaccion de {tx.transaction_type} por {tx.amount:,.2f} {tx.currency} "
                    f"excede umbral de reporte ({threshold:,.2f} MXN). "
                    f"Requiere revision y posible reporte ROV a UIF."
                ),
                amount=tx.amount,
                currency=tx.currency,
                rule_id="LARGE_TX_001",
                rule_name="Transaccion Grande",
                rule_parameters={"threshold": float(threshold)},
            )
            self.db.add(alert)
            alerts.append(alert)

        return alerts

    def _check_structuring(self, tx: TransactionData) -> List[AMLAlert]:
        """
        Detecta fraccionamiento (structuring).
        Multiples transacciones justo bajo el umbral.
        """
        alerts = []

        # Buscar transacciones en las ultimas 24h
        since = datetime.utcnow() - timedelta(hours=24)
        threshold = self.THRESHOLDS["structuring_threshold"]

        recent_txs = self.db.query(TransactionMonitor).filter(
            TransactionMonitor.user_id == tx.user_id,
            TransactionMonitor.executed_at >= since,
            TransactionMonitor.amount >= threshold * Decimal("0.7"),
            TransactionMonitor.amount < threshold,
        ).all()

        # Si hay 3+ transacciones cerca del umbral
        if len(recent_txs) >= 2:  # Esta seria la tercera
            total = sum(t.amount for t in recent_txs) + tx.amount

            if total >= self.THRESHOLDS["virtual_asset_report"]:
                alert = AMLAlert(
                    user_id=tx.user_id,
                    alert_type=AlertType.STRUCTURING,
                    severity=AlertSeverity.CRITICAL,
                    title="Posible fraccionamiento detectado",
                    description=(
                        f"Se detectaron {len(recent_txs) + 1} transacciones en 24h "
                        f"con montos cercanos al umbral de reporte. "
                        f"Total acumulado: {total:,.2f} MXN. "
                        f"Patron consistente con fraccionamiento (structuring)."
                    ),
                    amount=total,
                    currency=tx.currency,
                    rule_id="STRUCT_001",
                    rule_name="Fraccionamiento",
                    rule_parameters={
                        "transactions_count": len(recent_txs) + 1,
                        "time_window_hours": 24,
                    },
                    metadata={
                        "related_transactions": [str(t.id) for t in recent_txs],
                    },
                )
                self.db.add(alert)
                alerts.append(alert)

        return alerts

    def _check_rapid_movement(self, tx: TransactionData) -> List[AMLAlert]:
        """Detecta movimiento rapido de fondos."""
        alerts = []

        # Buscar patron: deposito seguido de retiro rapido
        since = datetime.utcnow() - timedelta(hours=4)

        # Depositos recientes
        deposits = self.db.query(
            func.sum(TransactionMonitor.amount)
        ).filter(
            TransactionMonitor.user_id == tx.user_id,
            TransactionMonitor.executed_at >= since,
            TransactionMonitor.transaction_type == "deposit",
        ).scalar() or Decimal("0")

        # Si es un retiro grande despues de depositos recientes
        if tx.transaction_type == "withdrawal" and deposits > Decimal("0"):
            ratio = tx.amount / deposits if deposits > 0 else 0

            if ratio >= Decimal("0.8") and tx.amount >= Decimal("100000"):
                alert = AMLAlert(
                    user_id=tx.user_id,
                    alert_type=AlertType.RAPID_MOVEMENT,
                    severity=AlertSeverity.HIGH,
                    title="Movimiento rapido de fondos",
                    description=(
                        f"Retiro de {tx.amount:,.2f} {tx.currency} representa "
                        f"{ratio * 100:.0f}% de depositos recientes ({deposits:,.2f} MXN). "
                        f"Patron de pass-through detectado."
                    ),
                    amount=tx.amount,
                    currency=tx.currency,
                    rule_id="RAPID_001",
                    rule_name="Movimiento Rapido",
                    rule_parameters={
                        "time_window_hours": 4,
                        "withdrawal_ratio": float(ratio),
                    },
                )
                self.db.add(alert)
                alerts.append(alert)

        return alerts

    def _check_high_risk_country(self, tx: TransactionData) -> List[AMLAlert]:
        """Detecta transacciones de/hacia paises de alto riesgo."""
        alerts = []

        if tx.country_code in self.HIGH_RISK_COUNTRIES:
            alert = AMLAlert(
                user_id=tx.user_id,
                alert_type=AlertType.HIGH_RISK_COUNTRY,
                severity=AlertSeverity.HIGH,
                title=f"Transaccion desde pais de alto riesgo: {tx.country_code}",
                description=(
                    f"Transaccion originada desde {tx.country_code}, "
                    f"pais identificado en listas GAFI/sanciones. "
                    f"Requiere revision de due diligence reforzado."
                ),
                amount=tx.amount,
                currency=tx.currency,
                rule_id="COUNTRY_001",
                rule_name="Pais Alto Riesgo",
                rule_parameters={"country_code": tx.country_code},
                metadata={"ip_address": tx.ip_address},
            )
            self.db.add(alert)
            alerts.append(alert)

        return alerts

    def _check_pep_transaction(self, tx: TransactionData) -> List[AMLAlert]:
        """Detecta transacciones de PEPs."""
        alerts = []

        # Verificar si usuario es PEP
        profile = self.db.query(KYCProfile).filter(
            KYCProfile.user_id == tx.user_id,
            KYCProfile.is_pep == True,
        ).first()

        if profile and tx.amount >= Decimal("50000"):
            alert = AMLAlert(
                user_id=tx.user_id,
                alert_type=AlertType.PEP_TRANSACTION,
                severity=AlertSeverity.MEDIUM,
                title="Transaccion de Persona Politicamente Expuesta",
                description=(
                    f"Transaccion de {tx.amount:,.2f} {tx.currency} realizada por PEP. "
                    f"Cargo: {profile.pep_position or 'No especificado'}. "
                    f"Requiere monitoreo reforzado."
                ),
                amount=tx.amount,
                currency=tx.currency,
                rule_id="PEP_001",
                rule_name="Transaccion PEP",
                rule_parameters={"pep_position": profile.pep_position},
            )
            self.db.add(alert)
            alerts.append(alert)

        return alerts

    def _check_unusual_pattern(self, tx: TransactionData) -> List[AMLAlert]:
        """Detecta patrones inusuales basados en historico del usuario."""
        alerts = []

        # Calcular promedio historico del usuario
        avg_amount = self.db.query(
            func.avg(TransactionMonitor.amount)
        ).filter(
            TransactionMonitor.user_id == tx.user_id,
            TransactionMonitor.transaction_type == tx.transaction_type,
        ).scalar() or Decimal("0")

        if avg_amount > 0:
            # Si la transaccion es 5x mayor que el promedio
            ratio = tx.amount / avg_amount

            if ratio >= Decimal("5") and tx.amount >= Decimal("100000"):
                alert = AMLAlert(
                    user_id=tx.user_id,
                    alert_type=AlertType.UNUSUAL_PATTERN,
                    severity=AlertSeverity.MEDIUM,
                    title="Transaccion inusualmente grande",
                    description=(
                        f"Transaccion de {tx.amount:,.2f} {tx.currency} es "
                        f"{ratio:.1f}x mayor que el promedio historico "
                        f"({avg_amount:,.2f} MXN). Patron inusual detectado."
                    ),
                    amount=tx.amount,
                    currency=tx.currency,
                    rule_id="UNUSUAL_001",
                    rule_name="Patron Inusual",
                    rule_parameters={
                        "average_amount": float(avg_amount),
                        "ratio": float(ratio),
                    },
                )
                self.db.add(alert)
                alerts.append(alert)

        return alerts

    def _calculate_transaction_risk(
        self,
        tx: TransactionData,
        alerts: List[AMLAlert]
    ) -> int:
        """Calcula risk score de transaccion (0-100)."""
        score = 20  # Base score

        # Por monto
        if tx.amount >= Decimal("500000"):
            score += 30
        elif tx.amount >= Decimal("200000"):
            score += 20
        elif tx.amount >= Decimal("100000"):
            score += 10

        # Por alertas generadas
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                score += 30
            elif alert.severity == AlertSeverity.HIGH:
                score += 20
            elif alert.severity == AlertSeverity.MEDIUM:
                score += 10

        # Por pais
        if tx.country_code in self.HIGH_RISK_COUNTRIES:
            score += 25

        return min(100, score)

    # ============ Alert Management ============

    def get_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        limit: int = 50
    ) -> List[AMLAlert]:
        """Obtiene alertas con filtros."""
        query = self.db.query(AMLAlert)

        if status:
            query = query.filter(AMLAlert.status == status)
        if severity:
            query = query.filter(AMLAlert.severity == severity)

        return query.order_by(AMLAlert.detected_at.desc()).limit(limit).all()

    def get_user_alerts(self, user_id: uuid.UUID) -> List[AMLAlert]:
        """Obtiene alertas de un usuario."""
        return self.db.query(AMLAlert).filter(
            AMLAlert.user_id == user_id
        ).order_by(AMLAlert.detected_at.desc()).all()

    def update_alert_status(
        self,
        alert_id: uuid.UUID,
        status: AlertStatus,
        investigator_id: uuid.UUID,
        notes: Optional[str] = None,
        false_positive: Optional[bool] = None
    ) -> AMLAlert:
        """Actualiza estado de alerta."""
        alert = self.db.query(AMLAlert).filter(
            AMLAlert.id == alert_id
        ).first()

        if not alert:
            raise ValueError("Alerta no encontrada")

        alert.status = status
        alert.updated_at = datetime.utcnow()

        if status == AlertStatus.INVESTIGATING:
            alert.assigned_to = investigator_id
            alert.investigation_started_at = datetime.utcnow()
            alert.investigation_notes = notes

        elif status in [AlertStatus.CLOSED_FALSE_POSITIVE, AlertStatus.CLOSED_CONFIRMED]:
            alert.resolved_by = investigator_id
            alert.resolved_at = datetime.utcnow()
            alert.resolution_notes = notes
            alert.false_positive = false_positive

            # Actualizar estadisticas de regla
            if alert.rule_id:
                rule = self.db.query(AMLRule).filter(
                    AMLRule.id == alert.rule_id
                ).first()
                if rule and false_positive:
                    rule.false_positive_count += 1

        self.db.commit()
        self.db.refresh(alert)
        return alert

    def escalate_alert(
        self,
        alert_id: uuid.UUID,
        escalator_id: uuid.UUID,
        notes: str
    ) -> AMLAlert:
        """Escala alerta para revision superior."""
        alert = self.db.query(AMLAlert).filter(
            AMLAlert.id == alert_id
        ).first()

        if not alert:
            raise ValueError("Alerta no encontrada")

        alert.status = AlertStatus.ESCALATED
        alert.investigation_notes = (
            f"{alert.investigation_notes or ''}\n\n"
            f"[ESCALADO {datetime.utcnow().isoformat()}]\n{notes}"
        )
        alert.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(alert)
        return alert

    # ============ Rules Management ============

    def create_rule(
        self,
        name: str,
        description: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        parameters: Dict[str, Any],
        created_by: uuid.UUID
    ) -> AMLRule:
        """Crea nueva regla de deteccion."""
        rule = AMLRule(
            name=name,
            description=description,
            alert_type=alert_type,
            severity=severity,
            parameters=parameters,
            created_by=created_by,
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        # Recargar reglas
        self._load_rules()

        return rule

    def toggle_rule(self, rule_id: uuid.UUID, active: bool) -> AMLRule:
        """Activa/desactiva regla."""
        rule = self.db.query(AMLRule).filter(
            AMLRule.id == rule_id
        ).first()

        if not rule:
            raise ValueError("Regla no encontrada")

        rule.is_active = active
        self.db.commit()
        self._load_rules()

        return rule

    # ============ Statistics ============

    def get_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Obtiene estadisticas AML."""
        since = datetime.utcnow() - timedelta(days=days)

        # Alertas por severidad
        alerts_by_severity = {}
        for sev in AlertSeverity:
            count = self.db.query(AMLAlert).filter(
                AMLAlert.detected_at >= since,
                AMLAlert.severity == sev,
            ).count()
            alerts_by_severity[sev.value] = count

        # Alertas por tipo
        alerts_by_type = {}
        for atype in AlertType:
            count = self.db.query(AMLAlert).filter(
                AMLAlert.detected_at >= since,
                AMLAlert.alert_type == atype,
            ).count()
            alerts_by_type[atype.value] = count

        # Alertas por estado
        alerts_by_status = {}
        for status in AlertStatus:
            count = self.db.query(AMLAlert).filter(
                AMLAlert.detected_at >= since,
                AMLAlert.status == status,
            ).count()
            alerts_by_status[status.value] = count

        # Transacciones monitoreadas
        total_monitored = self.db.query(TransactionMonitor).filter(
            TransactionMonitor.created_at >= since
        ).count()

        flagged_count = self.db.query(TransactionMonitor).filter(
            TransactionMonitor.created_at >= since,
            TransactionMonitor.flagged == True,
        ).count()

        # Volumen total
        total_volume = self.db.query(
            func.sum(TransactionMonitor.amount)
        ).filter(
            TransactionMonitor.created_at >= since
        ).scalar() or Decimal("0")

        # Tasa de falsos positivos
        closed_alerts = self.db.query(AMLAlert).filter(
            AMLAlert.resolved_at >= since,
            AMLAlert.status.in_([AlertStatus.CLOSED_FALSE_POSITIVE, AlertStatus.CLOSED_CONFIRMED]),
        ).all()

        false_positives = sum(1 for a in closed_alerts if a.false_positive)
        fp_rate = (false_positives / len(closed_alerts) * 100) if closed_alerts else 0

        return {
            "period_days": days,
            "alerts": {
                "total": sum(alerts_by_severity.values()),
                "by_severity": alerts_by_severity,
                "by_type": alerts_by_type,
                "by_status": alerts_by_status,
                "false_positive_rate": round(fp_rate, 2),
            },
            "transactions": {
                "total_monitored": total_monitored,
                "flagged": flagged_count,
                "flagged_rate": round((flagged_count / total_monitored * 100) if total_monitored else 0, 2),
                "total_volume_mxn": float(total_volume),
            },
            "rules": {
                "total": len(self.rules),
                "active": sum(1 for r in self.rules if r.is_active),
            },
        }
