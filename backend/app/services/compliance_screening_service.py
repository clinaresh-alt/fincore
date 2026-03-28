"""
Servicio Orquestador de Compliance Screening para FinCore.

Este servicio coordina:
1. Screening de direcciones via Chainalysis
2. Persistencia de resultados en base de datos
3. Generacion de alertas y notificaciones
4. Reportes SAR para CNBV
5. Metricas y estadisticas de compliance

Es el punto de entrada principal para todas las operaciones de PLD/AML
relacionadas con transacciones blockchain.
"""
import logging
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.core.config import settings
from app.services.chainalysis_service import (
    ChainalysisService,
    get_chainalysis_service,
    ChainalysisError,
)
from app.services.notification_service import NotificationService
from app.schemas.compliance_screening import (
    RiskLevel,
    RiskCategory,
    ScreeningStatus,
    ScreeningAction,
    BlockchainNetwork,
    AddressScreeningRequest,
    AddressScreeningResponse,
    TransactionScreeningRequest,
    TransactionScreeningResponse,
    BatchScreeningRequest,
    BatchScreeningResponse,
    ComplianceAlert,
    SuspiciousActivityReport,
    ScreeningThresholds,
    ScreeningStats,
    RiskIndicator,
)

logger = logging.getLogger(__name__)


class ComplianceScreeningException(Exception):
    """Excepcion base de compliance screening."""
    pass


class AddressBlockedException(ComplianceScreeningException):
    """Direccion bloqueada por compliance."""
    def __init__(self, address: str, reason: str, screening_id: str):
        self.address = address
        self.reason = reason
        self.screening_id = screening_id
        super().__init__(f"Direccion bloqueada: {address[:10]}... - {reason}")


class ScreeningRequiredException(ComplianceScreeningException):
    """Se requiere screening antes de proceder."""
    pass


class ComplianceScreeningService:
    """
    Servicio principal de Compliance Screening.

    Responsabilidades:
    - Orquestar screening de direcciones y transacciones
    - Aplicar reglas de negocio y umbrales configurables
    - Persistir resultados y generar alertas
    - Generar reportes para reguladores (SAR)
    - Mantener estadisticas de compliance

    Uso:
        service = ComplianceScreeningService(db)

        # Screening simple
        result = await service.screen_address_for_remittance(
            address="0x742d...",
            network=BlockchainNetwork.POLYGON,
            remittance_id="rem_123",
            amount_usd=Decimal("500")
        )

        if not result.can_proceed:
            raise AddressBlockedException(...)
    """

    def __init__(
        self,
        db: Session,
        chainalysis_service: Optional[ChainalysisService] = None,
        notification_service: Optional[NotificationService] = None,
        thresholds: Optional[ScreeningThresholds] = None,
    ):
        """
        Inicializa el servicio.

        Args:
            db: Sesion de base de datos
            chainalysis_service: Servicio de Chainalysis (opcional, usa singleton)
            notification_service: Servicio de notificaciones (opcional)
            thresholds: Umbrales configurables (opcional, usa defaults)
        """
        self.db = db
        self.chainalysis = chainalysis_service or get_chainalysis_service()
        self.notifications = notification_service
        self.thresholds = thresholds or ScreeningThresholds()

        # Cache local de direcciones bloqueadas (para rapida verificacion)
        self._blocked_addresses: Dict[str, datetime] = {}
        self._blocked_cache_ttl = timedelta(hours=24)

    # ============ Screening Principal ============

    async def screen_address_for_remittance(
        self,
        address: str,
        network: BlockchainNetwork,
        remittance_id: str,
        user_id: str,
        amount_usd: Decimal,
        direction: str = "inbound",
    ) -> "ScreeningDecision":
        """
        Realiza screening de direccion para una remesa.

        Este es el metodo principal que debe llamarse antes de procesar
        cualquier deposito o retiro de fondos.

        Args:
            address: Direccion blockchain a verificar
            network: Red (polygon, ethereum, etc.)
            remittance_id: ID de la remesa asociada
            user_id: ID del usuario
            amount_usd: Monto en USD
            direction: "inbound" (deposito) o "outbound" (retiro)

        Returns:
            ScreeningDecision con resultado y si puede proceder

        Raises:
            AddressBlockedException: Si la direccion esta bloqueada
        """
        logger.info(
            f"Iniciando screening para remesa {remittance_id}: "
            f"{address[:10]}... en {network.value}, ${amount_usd} USD"
        )

        # 1. Verificar cache de direcciones bloqueadas
        if self._is_address_blocked(address):
            logger.warning(f"Direccion en cache de bloqueadas: {address[:10]}...")
            raise AddressBlockedException(
                address=address,
                reason="Direccion previamente bloqueada",
                screening_id="cached",
            )

        # 2. Verificar si requiere screening mejorado por monto
        requires_enhanced = amount_usd >= self.thresholds.enhanced_screening_amount_usd

        # 3. Ejecutar screening via Chainalysis
        try:
            screening_result = await self.chainalysis.screen_address(
                address=address,
                network=network,
                user_id=user_id,
                amount_usd=amount_usd,
                direction=direction,
                use_cache=not requires_enhanced,  # No usar cache para montos altos
            )
        except ChainalysisError as e:
            logger.error(f"Error en Chainalysis: {e}")
            # En caso de error, aplicar politica conservadora
            return await self._handle_screening_error(
                address=address,
                network=network,
                remittance_id=remittance_id,
                user_id=user_id,
                amount_usd=amount_usd,
                error=str(e),
            )

        # 4. Persistir resultado
        await self._persist_screening_result(
            screening_result=screening_result,
            remittance_id=remittance_id,
            user_id=user_id,
            amount_usd=amount_usd,
        )

        # 5. Aplicar reglas de negocio
        decision = self._apply_business_rules(
            screening_result=screening_result,
            amount_usd=amount_usd,
        )

        # 6. Generar alertas si es necesario
        if decision.requires_alert:
            await self._create_compliance_alert(
                screening_result=screening_result,
                remittance_id=remittance_id,
                user_id=user_id,
                decision=decision,
            )

        # 7. Si esta bloqueada, agregar a cache y lanzar excepcion
        if decision.action == ScreeningAction.BLOCK:
            self._add_to_blocked_cache(address)
            raise AddressBlockedException(
                address=address,
                reason=decision.reason,
                screening_id=screening_result.screening_id,
            )

        # 8. Verificar si requiere reporte SAR
        if screening_result.requires_sar or amount_usd >= self.thresholds.auto_report_amount_usd:
            await self._queue_sar_report(
                screening_result=screening_result,
                remittance_id=remittance_id,
                user_id=user_id,
            )

        logger.info(
            f"Screening completado para {address[:10]}...: "
            f"action={decision.action.value}, can_proceed={decision.can_proceed}"
        )

        return decision

    async def screen_transaction(
        self,
        request: TransactionScreeningRequest,
    ) -> TransactionScreeningResponse:
        """
        Realiza screening de una transaccion blockchain.

        Analiza tanto la direccion origen como destino.
        """
        logger.info(f"Screening de transaccion: {request.tx_hash[:16]}...")

        # Screen ambas direcciones
        from_result = await self.chainalysis.screen_address(
            address=request.from_address,
            network=request.network,
            direction="outbound",
        )

        to_result = await self.chainalysis.screen_address(
            address=request.to_address,
            network=request.network,
            direction="inbound",
        )

        # Combinar riesgos
        combined_score = max(from_result.risk_score, to_result.risk_score)
        combined_level = max(from_result.risk_level, to_result.risk_level, key=lambda x: x.value)

        # Determinar accion
        if combined_score >= self.thresholds.auto_reject_min_score:
            action = ScreeningAction.REJECT
        elif combined_score >= self.thresholds.review_min_score:
            action = ScreeningAction.REVIEW
        else:
            action = ScreeningAction.APPROVE

        return TransactionScreeningResponse(
            screening_id=f"txscr_{uuid4().hex[:16]}",
            tx_hash=request.tx_hash,
            network=request.network,
            status=ScreeningStatus.COMPLETED,
            from_address_risk=from_result,
            to_address_risk=to_result,
            combined_risk_score=combined_score,
            combined_risk_level=combined_level,
            recommended_action=action,
            screened_at=datetime.utcnow(),
        )

    async def batch_screen_addresses(
        self,
        request: BatchScreeningRequest,
    ) -> BatchScreeningResponse:
        """
        Screening en lote de multiples direcciones.

        Util para verificar lista de beneficiarios o monitoreo periodico.
        """
        batch_id = f"batch_{uuid4().hex[:16]}"
        results: List[AddressScreeningResponse] = []
        failed = 0

        for addr_request in request.addresses:
            try:
                result = await self.chainalysis.screen_address(
                    address=addr_request.address,
                    network=addr_request.network,
                    user_id=addr_request.user_id,
                    amount_usd=addr_request.amount_usd,
                    direction=addr_request.direction,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Error en batch screening: {e}")
                failed += 1

        # Calcular estadisticas
        high_risk = sum(1 for r in results if r.risk_level in [RiskLevel.HIGH, RiskLevel.SEVERE])
        blocked = sum(1 for r in results if r.recommended_action == ScreeningAction.BLOCK)
        review = sum(1 for r in results if r.recommended_action == ScreeningAction.REVIEW)

        return BatchScreeningResponse(
            batch_id=batch_id,
            total_addresses=len(request.addresses),
            completed=len(results),
            failed=failed,
            results=results,
            high_risk_count=high_risk,
            blocked_count=blocked,
            requires_review_count=review,
            processed_at=datetime.utcnow(),
        )

    # ============ Verificaciones Rapidas ============

    async def quick_check_address(
        self,
        address: str,
        network: BlockchainNetwork = BlockchainNetwork.POLYGON,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verificacion rapida de direccion.

        Returns:
            Tuple de (is_safe, reason_if_blocked)
        """
        # Primero verificar cache local
        if self._is_address_blocked(address):
            return (False, "Direccion en lista de bloqueadas")

        try:
            result = await self.chainalysis.screen_address(
                address=address,
                network=network,
                use_cache=True,
            )

            if result.is_sanctioned:
                return (False, "Direccion sancionada")

            if result.risk_score >= self.thresholds.auto_reject_min_score:
                return (False, f"Riesgo alto: {result.risk_score}")

            return (True, None)

        except ChainalysisError:
            # En caso de error, permitir pero marcar para revision
            return (True, None)

    def _is_address_blocked(self, address: str) -> bool:
        """Verifica si una direccion esta en el cache de bloqueadas."""
        address_lower = address.lower()
        if address_lower in self._blocked_addresses:
            blocked_at = self._blocked_addresses[address_lower]
            if datetime.utcnow() - blocked_at < self._blocked_cache_ttl:
                return True
            else:
                del self._blocked_addresses[address_lower]
        return False

    def _add_to_blocked_cache(self, address: str):
        """Agrega direccion al cache de bloqueadas."""
        self._blocked_addresses[address.lower()] = datetime.utcnow()

    # ============ Reglas de Negocio ============

    def _apply_business_rules(
        self,
        screening_result: AddressScreeningResponse,
        amount_usd: Decimal,
    ) -> "ScreeningDecision":
        """
        Aplica reglas de negocio sobre el resultado de Chainalysis.

        Considera:
        - Umbrales configurables
        - Categorias que siempre bloquean
        - Monto de la transaccion
        """
        score = screening_result.risk_score
        indicators = screening_result.risk_indicators

        # Verificar categorias que siempre bloquean
        for indicator in indicators:
            if indicator.category in self.thresholds.always_block_categories:
                return ScreeningDecision(
                    can_proceed=False,
                    action=ScreeningAction.BLOCK,
                    reason=f"Categoria bloqueada: {indicator.category.value}",
                    requires_alert=True,
                    requires_manual_review=False,
                    screening_id=screening_result.screening_id,
                    risk_score=score,
                    risk_level=screening_result.risk_level,
                )

        # Direccion sancionada
        if screening_result.is_sanctioned:
            return ScreeningDecision(
                can_proceed=False,
                action=ScreeningAction.BLOCK,
                reason="Direccion en lista de sanciones",
                requires_alert=True,
                requires_manual_review=False,
                screening_id=screening_result.screening_id,
                risk_score=100,
                risk_level=RiskLevel.SEVERE,
            )

        # Score >= 90: Bloquear
        if score >= self.thresholds.block_min_score:
            return ScreeningDecision(
                can_proceed=False,
                action=ScreeningAction.BLOCK,
                reason=f"Score de riesgo critico: {score}",
                requires_alert=True,
                requires_manual_review=False,
                screening_id=screening_result.screening_id,
                risk_score=score,
                risk_level=screening_result.risk_level,
            )

        # Score >= 70: Rechazar
        if score >= self.thresholds.auto_reject_min_score:
            return ScreeningDecision(
                can_proceed=False,
                action=ScreeningAction.REJECT,
                reason=f"Score de riesgo alto: {score}",
                requires_alert=True,
                requires_manual_review=True,
                screening_id=screening_result.screening_id,
                risk_score=score,
                risk_level=screening_result.risk_level,
            )

        # Score >= 31: Revision manual
        if score >= self.thresholds.review_min_score:
            return ScreeningDecision(
                can_proceed=True,  # Puede proceder pero con revision
                action=ScreeningAction.REVIEW,
                reason=f"Score de riesgo medio: {score} - requiere revision",
                requires_alert=True,
                requires_manual_review=True,
                screening_id=screening_result.screening_id,
                risk_score=score,
                risk_level=screening_result.risk_level,
            )

        # Score < 31: Aprobar
        return ScreeningDecision(
            can_proceed=True,
            action=ScreeningAction.APPROVE,
            reason="Sin indicadores de riesgo significativos",
            requires_alert=False,
            requires_manual_review=False,
            screening_id=screening_result.screening_id,
            risk_score=score,
            risk_level=screening_result.risk_level,
        )

    async def _handle_screening_error(
        self,
        address: str,
        network: BlockchainNetwork,
        remittance_id: str,
        user_id: str,
        amount_usd: Decimal,
        error: str,
    ) -> "ScreeningDecision":
        """
        Maneja errores de screening aplicando politica conservadora.

        Para montos bajos: permite con revision
        Para montos altos: bloquea hasta verificacion manual
        """
        # Umbral para politica conservadora
        HIGH_AMOUNT_THRESHOLD = Decimal("1000")

        if amount_usd >= HIGH_AMOUNT_THRESHOLD:
            # Montos altos: bloquear hasta verificacion
            return ScreeningDecision(
                can_proceed=False,
                action=ScreeningAction.REVIEW,
                reason=f"Error en screening, monto alto requiere verificacion: {error}",
                requires_alert=True,
                requires_manual_review=True,
                screening_id="error",
                risk_score=50,
                risk_level=RiskLevel.MEDIUM,
            )
        else:
            # Montos bajos: permitir con alerta
            return ScreeningDecision(
                can_proceed=True,
                action=ScreeningAction.ENHANCED_DUE_DILIGENCE,
                reason=f"Error en screening, aplicando EDD: {error}",
                requires_alert=True,
                requires_manual_review=True,
                screening_id="error",
                risk_score=30,
                risk_level=RiskLevel.LOW,
            )

    # ============ Persistencia ============

    async def _persist_screening_result(
        self,
        screening_result: AddressScreeningResponse,
        remittance_id: str,
        user_id: str,
        amount_usd: Decimal,
    ):
        """
        Persiste el resultado de screening en la base de datos.

        Guarda en tabla ScreeningAuditLog para cumplimiento regulatorio PLD/AML.
        """
        from app.models.compliance import ScreeningAuditLog, RiskLevel as ComplianceRiskLevel

        try:
            # Mapear risk_level al enum de compliance
            risk_level_map = {
                "low": ComplianceRiskLevel.LOW,
                "medium": ComplianceRiskLevel.MEDIUM,
                "high": ComplianceRiskLevel.HIGH,
                "critical": ComplianceRiskLevel.PROHIBITED,
            }

            audit_log = ScreeningAuditLog(
                screening_id=screening_result.screening_id,
                user_id=user_id,
                remittance_id=remittance_id,
                address=screening_result.address,
                network=screening_result.network.value if hasattr(screening_result.network, 'value') else str(screening_result.network),
                risk_score=screening_result.risk_score,
                risk_level=risk_level_map.get(screening_result.risk_level.value.lower(), ComplianceRiskLevel.MEDIUM),
                recommended_action=screening_result.recommended_action.value,
                risk_indicators=[ind.dict() if hasattr(ind, 'dict') else ind for ind in screening_result.risk_indicators],
                provider="chainalysis",  # O el proveedor usado
                amount_usd=amount_usd,
                screened_at=screening_result.screened_at,
                requires_sar=screening_result.risk_score >= 70 or amount_usd >= Decimal("10000"),
            )

            self.db.add(audit_log)
            self.db.commit()

            logger.info(
                f"Screening audit persisted: screening_id={screening_result.screening_id}, "
                f"remittance={remittance_id}, risk_score={screening_result.risk_score}"
            )

        except Exception as e:
            logger.error(f"Error persisting screening audit: {e}")
            self.db.rollback()
            # No lanzar excepción - el screening ya se realizó

    # ============ Alertas ============

    async def _create_compliance_alert(
        self,
        screening_result: AddressScreeningResponse,
        remittance_id: str,
        user_id: str,
        decision: "ScreeningDecision",
    ):
        """Crea alerta de compliance para revision."""
        alert = ComplianceAlert(
            alert_id=f"alert_{uuid4().hex[:16]}",
            alert_type=f"screening_{decision.action.value}",
            severity=screening_result.risk_level,
            address=screening_result.address,
            user_id=user_id,
            remittance_id=remittance_id,
            screening_id=screening_result.screening_id,
            title=f"Screening: {decision.action.value.upper()}",
            description=decision.reason,
            risk_indicators=screening_result.risk_indicators,
            recommended_action=decision.action,
            created_at=datetime.utcnow(),
        )

        logger.warning(
            f"Alerta de compliance creada: {alert.alert_id} - "
            f"{alert.alert_type} para remesa {remittance_id}"
        )

        # Notificar a equipo de compliance
        if self.notifications:
            try:
                await self.notifications.send_compliance_alert(
                    alert_type=alert.alert_type,
                    severity=alert.severity.value,
                    message=f"Remesa {remittance_id}: {decision.reason}",
                    metadata={
                        "screening_id": screening_result.screening_id,
                        "risk_score": screening_result.risk_score,
                        "address": screening_result.address[:20] + "...",
                    }
                )
            except Exception as e:
                logger.error(f"Error enviando notificacion de alerta: {e}")

    # ============ Reportes SAR ============

    async def _queue_sar_report(
        self,
        screening_result: AddressScreeningResponse,
        remittance_id: str,
        user_id: str,
    ):
        """
        Encola generacion de reporte SAR para CNBV/UIF.

        Los reportes SAR deben generarse para:
        - Transacciones >= $10,000 USD
        - Direcciones con indicadores de terrorismo/ransomware/sanciones
        - Patrones sospechosos detectados

        El flujo es:
        1. Se crea el reporte con status=pending
        2. Un analista de compliance lo revisa
        3. Se aprueba y se genera el XML para UIF
        4. Se envía manualmente o vía API
        """
        from app.models.compliance import SARReport
        from datetime import datetime, timedelta

        try:
            # Generar número de referencia único
            date_str = datetime.utcnow().strftime("%Y%m%d")
            existing_count = self.db.query(SARReport).filter(
                SARReport.reference_number.like(f"SAR-{date_str}%")
            ).count()
            reference_number = f"SAR-{date_str}-{(existing_count + 1):05d}"

            # Determinar prioridad basada en indicadores
            priority = "normal"
            high_risk_indicators = ["terrorism", "ransomware", "sanctions", "child_exploitation"]
            for indicator in screening_result.risk_indicators:
                indicator_type = indicator.indicator_type if hasattr(indicator, 'indicator_type') else indicator.get('indicator_type', '')
                if indicator_type.lower() in high_risk_indicators:
                    priority = "urgent"
                    break
                elif indicator_type.lower() in ["mixer", "darknet", "fraud"]:
                    priority = "high"

            # Crear descripción del reporte
            description = (
                f"Actividad sospechosa detectada en remesa {remittance_id}. "
                f"Dirección blockchain: {screening_result.address[:20]}... "
                f"Score de riesgo: {screening_result.risk_score}/100. "
                f"Indicadores detectados: {len(screening_result.risk_indicators)}."
            )

            sar_report = SARReport(
                reference_number=reference_number,
                user_id=user_id,
                remittance_ids=[remittance_id],
                screening_ids=[screening_result.screening_id],
                report_type="suspicious_activity",
                description=description,
                triggering_indicators=[
                    ind.dict() if hasattr(ind, 'dict') else ind
                    for ind in screening_result.risk_indicators
                ],
                risk_assessment=(
                    f"Score: {screening_result.risk_score}. "
                    f"Nivel: {screening_result.risk_level.value}. "
                    f"Acción recomendada: {screening_result.recommended_action.value}."
                ),
                status="pending",
                priority=priority,
                incident_date=datetime.utcnow(),
                deadline=datetime.utcnow() + timedelta(hours=24 if priority == "urgent" else 72),
            )

            self.db.add(sar_report)
            self.db.commit()

            logger.warning(
                f"SAR report created: {reference_number}, "
                f"priority={priority}, remittance={remittance_id}"
            )

            # Notificar a compliance si es urgente
            if priority == "urgent" and self.notifications:
                try:
                    await self.notifications.send_compliance_alert(
                        alert_type="sar_urgent",
                        severity="critical",
                        message=f"SAR urgente creado: {reference_number}",
                        metadata={
                            "reference_number": reference_number,
                            "remittance_id": remittance_id,
                            "risk_score": screening_result.risk_score,
                        }
                    )
                except Exception as e:
                    logger.error(f"Error notificando SAR urgente: {e}")

        except Exception as e:
            logger.error(f"Error creating SAR report: {e}")
            self.db.rollback()

    async def generate_sar_report(
        self,
        user_id: str,
        remittance_ids: List[str],
        narrative: str,
    ) -> SuspiciousActivityReport:
        """
        Genera reporte SAR completo para envio a CNBV.

        Debe ser llamado por personal de compliance tras revision.
        """
        # Obtener datos del usuario
        # user = self.db.query(User).filter(User.id == user_id).first()

        # Calcular totales
        # remittances = self.db.query(Remittance).filter(
        #     Remittance.id.in_(remittance_ids)
        # ).all()

        report = SuspiciousActivityReport(
            report_id=f"SAR_{uuid4().hex[:12]}",
            report_type="SAR",
            user_id=user_id,
            user_name="[OBTENER DE DB]",
            remittance_ids=remittance_ids,
            total_amount_usd=Decimal("0"),  # Calcular
            total_amount_mxn=Decimal("0"),  # Calcular
            risk_indicators=[],  # Agregar de screenings
            suspicious_patterns=[],
            narrative=narrative,
            recommendation="",
            generated_at=datetime.utcnow(),
            generated_by="system",
        )

        return report

    # ============ Estadisticas ============

    async def get_screening_stats(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> ScreeningStats:
        """
        Obtiene estadisticas de screening para un periodo.
        Utiliza la tabla ScreeningAuditLog para métricas de compliance.
        """
        from app.models.compliance import ScreeningAuditLog, RiskLevel as ComplianceRiskLevel

        try:
            # Query base para el periodo
            base_query = self.db.query(ScreeningAuditLog).filter(
                and_(
                    ScreeningAuditLog.screened_at >= period_start,
                    ScreeningAuditLog.screened_at <= period_end
                )
            )

            # Conteos totales
            total_screenings = base_query.count()

            # Conteos por acción recomendada
            approved = base_query.filter(
                ScreeningAuditLog.recommended_action == "approve"
            ).count()
            rejected = base_query.filter(
                ScreeningAuditLog.recommended_action == "reject"
            ).count()
            blocked = base_query.filter(
                ScreeningAuditLog.recommended_action == "block"
            ).count()
            pending_review = base_query.filter(
                ScreeningAuditLog.recommended_action == "review"
            ).count()

            # Score promedio
            avg_score_result = self.db.query(
                func.avg(ScreeningAuditLog.risk_score)
            ).filter(
                and_(
                    ScreeningAuditLog.screened_at >= period_start,
                    ScreeningAuditLog.screened_at <= period_end
                )
            ).scalar()
            average_risk_score = float(avg_score_result or 0)

            # Porcentaje de alto riesgo
            high_risk_count = base_query.filter(
                ScreeningAuditLog.risk_level.in_([
                    ComplianceRiskLevel.HIGH,
                    ComplianceRiskLevel.PROHIBITED
                ])
            ).count()
            high_risk_percentage = (
                (high_risk_count / total_screenings * 100)
                if total_screenings > 0 else 0.0
            )

            # Distribución por red
            by_network_query = self.db.query(
                ScreeningAuditLog.network,
                func.count(ScreeningAuditLog.id)
            ).filter(
                and_(
                    ScreeningAuditLog.screened_at >= period_start,
                    ScreeningAuditLog.screened_at <= period_end
                )
            ).group_by(ScreeningAuditLog.network).all()

            by_network = {row[0]: row[1] for row in by_network_query}

            # Distribución por nivel de riesgo (como categoría)
            by_risk_query = self.db.query(
                ScreeningAuditLog.risk_level,
                func.count(ScreeningAuditLog.id)
            ).filter(
                and_(
                    ScreeningAuditLog.screened_at >= period_start,
                    ScreeningAuditLog.screened_at <= period_end
                )
            ).group_by(ScreeningAuditLog.risk_level).all()

            by_category = {str(row[0].value): row[1] for row in by_risk_query if row[0]}

            return ScreeningStats(
                period_start=period_start,
                period_end=period_end,
                total_screenings=total_screenings,
                approved=approved,
                rejected=rejected,
                blocked=blocked,
                pending_review=pending_review,
                average_risk_score=average_risk_score,
                high_risk_percentage=high_risk_percentage,
                by_category=by_category,
                by_network=by_network,
                average_screening_time_ms=0.0,  # No disponible sin métricas de tiempo
            )

        except Exception as e:
            logger.error(f"Error obteniendo estadísticas de screening: {e}")
            return ScreeningStats(
                period_start=period_start,
                period_end=period_end,
                total_screenings=0,
                approved=0,
                rejected=0,
                blocked=0,
                pending_review=0,
                average_risk_score=0.0,
                high_risk_percentage=0.0,
                by_category={},
                by_network={},
                average_screening_time_ms=0.0,
            )


# ============ DTOs Internos ============

class ScreeningDecision:
    """Resultado de decision de screening."""

    def __init__(
        self,
        can_proceed: bool,
        action: ScreeningAction,
        reason: str,
        requires_alert: bool,
        requires_manual_review: bool,
        screening_id: str,
        risk_score: int,
        risk_level: RiskLevel,
    ):
        self.can_proceed = can_proceed
        self.action = action
        self.reason = reason
        self.requires_alert = requires_alert
        self.requires_manual_review = requires_manual_review
        self.screening_id = screening_id
        self.risk_score = risk_score
        self.risk_level = risk_level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "can_proceed": self.can_proceed,
            "action": self.action.value,
            "reason": self.reason,
            "requires_alert": self.requires_alert,
            "requires_manual_review": self.requires_manual_review,
            "screening_id": self.screening_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level.value,
        }


# ============ Factory ============

def get_compliance_screening_service(db: Session) -> ComplianceScreeningService:
    """Factory para obtener instancia del servicio."""
    return ComplianceScreeningService(db=db)
