"""
Tests para el servicio de Chainalysis y Compliance Screening.

Cubre:
- Cliente API de Chainalysis (mock)
- Logica de scoring de riesgo
- Reglas de negocio de compliance
- Integracion con flujo de remesas
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.services.chainalysis_service import (
    ChainalysisService,
    ChainalysisConfig,
    ChainalysisError,
    ChainalysisAPIError,
    ChainalysisRateLimitError,
)
from app.services.compliance_screening_service import (
    ComplianceScreeningService,
    AddressBlockedException,
    ScreeningDecision,
    get_compliance_screening_service,
)
from app.schemas.compliance_screening import (
    RiskLevel,
    RiskCategory,
    ScreeningStatus,
    ScreeningAction,
    BlockchainNetwork,
    AddressScreeningRequest,
    AddressScreeningResponse,
    RiskIndicator,
    ScreeningThresholds,
)


# ==================== FIXTURES ====================

@pytest.fixture
def chainalysis_config():
    """Configuracion de Chainalysis para tests."""
    return ChainalysisConfig(
        api_key="test_api_key",
        api_url="https://api.test.chainalysis.com/api",
        kyt_api_url="https://api.test.chainalysis.com/api/kyt/v2",
        sanctions_api_url="https://api.test.chainalysis.com/api/sanctions/v1",
        timeout_seconds=5,
    )


@pytest.fixture
def chainalysis_service(chainalysis_config):
    """Servicio de Chainalysis para tests."""
    return ChainalysisService(config=chainalysis_config)


@pytest.fixture
def compliance_service(mock_db_session):
    """Servicio de compliance para tests."""
    service = ComplianceScreeningService(
        db=mock_db_session,
        chainalysis_service=MagicMock(),
        thresholds=ScreeningThresholds(),
    )
    return service


@pytest.fixture
def sample_address():
    """Direccion de ejemplo para tests."""
    return "0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16"


@pytest.fixture
def sanctioned_address():
    """Direccion sancionada de ejemplo."""
    return "0xd90e2f925DA726b50C4Ed8D0Fb90Ad053324F31b"  # Tornado Cash


@pytest.fixture
def sample_screening_response(sample_address):
    """Respuesta de screening de ejemplo."""
    return AddressScreeningResponse(
        screening_id="scr_test123",
        address=sample_address,
        network=BlockchainNetwork.POLYGON,
        status=ScreeningStatus.COMPLETED,
        risk_score=15,
        risk_level=RiskLevel.LOW,
        risk_indicators=[],
        direct_exposure=[],
        indirect_exposure=[],
        recommended_action=ScreeningAction.APPROVE,
        action_reason="Sin indicadores de riesgo",
        screened_at=datetime.utcnow(),
        data_as_of=datetime.utcnow(),
        is_sanctioned=False,
        requires_sar=False,
        pep_match=False,
    )


@pytest.fixture
def high_risk_screening_response(sample_address):
    """Respuesta de screening de alto riesgo."""
    return AddressScreeningResponse(
        screening_id="scr_highrisk",
        address=sample_address,
        network=BlockchainNetwork.POLYGON,
        status=ScreeningStatus.COMPLETED,
        risk_score=85,
        risk_level=RiskLevel.HIGH,
        risk_indicators=[
            RiskIndicator(
                category=RiskCategory.MIXER,
                severity=80,
                description="Exposicion a Tornado Cash",
                source="chainalysis_kyt",
                confidence=0.9,
            ),
            RiskIndicator(
                category=RiskCategory.HIGH_RISK_EXCHANGE,
                severity=60,
                description="Transacciones con exchange sin KYC",
                source="chainalysis_exposure",
                confidence=0.8,
            ),
        ],
        direct_exposure=[],
        indirect_exposure=[],
        recommended_action=ScreeningAction.REJECT,
        action_reason="Score de riesgo alto",
        screened_at=datetime.utcnow(),
        data_as_of=datetime.utcnow(),
        is_sanctioned=False,
        requires_sar=True,
        pep_match=False,
    )


@pytest.fixture
def sanctioned_screening_response(sanctioned_address):
    """Respuesta de screening para direccion sancionada."""
    return AddressScreeningResponse(
        screening_id="scr_sanctioned",
        address=sanctioned_address,
        network=BlockchainNetwork.ETHEREUM,
        status=ScreeningStatus.COMPLETED,
        risk_score=100,
        risk_level=RiskLevel.SEVERE,
        risk_indicators=[
            RiskIndicator(
                category=RiskCategory.SANCTIONS,
                severity=100,
                description="Direccion en lista OFAC",
                source="chainalysis_sanctions",
                confidence=1.0,
            ),
        ],
        direct_exposure=[],
        indirect_exposure=[],
        recommended_action=ScreeningAction.BLOCK,
        action_reason="Direccion sancionada por OFAC",
        screened_at=datetime.utcnow(),
        data_as_of=datetime.utcnow(),
        is_sanctioned=True,
        requires_sar=True,
        pep_match=False,
    )


# ==================== TESTS: Chainalysis Service ====================

class TestChainalysisService:
    """Tests para el cliente de Chainalysis."""

    @pytest.mark.asyncio
    async def test_risk_score_calculation_no_indicators(self, chainalysis_service):
        """Score deberia ser 0 sin indicadores."""
        score = chainalysis_service._calculate_combined_risk_score(
            indicators=[],
            direct_exposure=[],
            indirect_exposure=[],
            amount_usd=None,
        )
        assert score == 0

    @pytest.mark.asyncio
    async def test_risk_score_calculation_with_indicators(self, chainalysis_service):
        """Score deberia reflejar severidad de indicadores."""
        indicators = [
            RiskIndicator(
                category=RiskCategory.MIXER,
                severity=80,
                description="Exposicion a mixer",
                source="test",
                confidence=1.0,
            ),
        ]

        score = chainalysis_service._calculate_combined_risk_score(
            indicators=indicators,
            direct_exposure=[],
            indirect_exposure=[],
            amount_usd=None,
        )

        # 80 * 1.0 * 0.5 (peso indicadores) = 40
        assert score == 40

    @pytest.mark.asyncio
    async def test_risk_score_high_amount_factor(self, chainalysis_service):
        """Montos altos deberian aumentar el score."""
        score_low = chainalysis_service._calculate_combined_risk_score(
            indicators=[],
            direct_exposure=[],
            indirect_exposure=[],
            amount_usd=Decimal("100"),
        )

        score_high = chainalysis_service._calculate_combined_risk_score(
            indicators=[],
            direct_exposure=[],
            indirect_exposure=[],
            amount_usd=Decimal("15000"),
        )

        assert score_high > score_low
        assert score_high == 20  # Factor por monto > 10000

    @pytest.mark.asyncio
    async def test_score_to_risk_level_severe(self, chainalysis_service):
        """Score >= 90 deberia ser SEVERE."""
        level = chainalysis_service._score_to_risk_level(95)
        assert level == RiskLevel.SEVERE

    @pytest.mark.asyncio
    async def test_score_to_risk_level_high(self, chainalysis_service):
        """Score 70-89 deberia ser HIGH."""
        level = chainalysis_service._score_to_risk_level(75)
        assert level == RiskLevel.HIGH

    @pytest.mark.asyncio
    async def test_score_to_risk_level_medium(self, chainalysis_service):
        """Score 40-69 deberia ser MEDIUM."""
        level = chainalysis_service._score_to_risk_level(50)
        assert level == RiskLevel.MEDIUM

    @pytest.mark.asyncio
    async def test_score_to_risk_level_low(self, chainalysis_service):
        """Score 10-39 deberia ser LOW."""
        level = chainalysis_service._score_to_risk_level(25)
        assert level == RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_score_to_risk_level_minimal(self, chainalysis_service):
        """Score < 10 deberia ser MINIMAL."""
        level = chainalysis_service._score_to_risk_level(5)
        assert level == RiskLevel.MINIMAL

    @pytest.mark.asyncio
    async def test_determine_action_sanctions_always_blocks(self, chainalysis_service):
        """Categoria SANCTIONS siempre deberia bloquear."""
        indicators = [
            RiskIndicator(
                category=RiskCategory.SANCTIONS,
                severity=100,
                description="OFAC",
                source="test",
                confidence=1.0,
            ),
        ]

        action, reason = chainalysis_service._determine_action(
            score=100,
            level=RiskLevel.SEVERE,
            indicators=indicators,
        )

        assert action == ScreeningAction.BLOCK
        assert "SANCTIONS" in reason.upper() or "critico" in reason.lower()

    @pytest.mark.asyncio
    async def test_determine_action_terrorism_always_blocks(self, chainalysis_service):
        """Categoria TERRORISM siempre deberia bloquear."""
        indicators = [
            RiskIndicator(
                category=RiskCategory.TERRORISM,
                severity=100,
                description="Financiamiento terrorismo",
                source="test",
                confidence=1.0,
            ),
        ]

        action, reason = chainalysis_service._determine_action(
            score=80,
            level=RiskLevel.HIGH,
            indicators=indicators,
        )

        assert action == ScreeningAction.BLOCK

    @pytest.mark.asyncio
    async def test_determine_action_approve_low_risk(self, chainalysis_service):
        """Score bajo sin indicadores criticos deberia aprobar."""
        action, reason = chainalysis_service._determine_action(
            score=10,
            level=RiskLevel.LOW,
            indicators=[],
        )

        assert action == ScreeningAction.APPROVE

    @pytest.mark.asyncio
    async def test_cache_key_generation(self, chainalysis_service, sample_address):
        """Cache key deberia ser consistente."""
        key1 = chainalysis_service._get_cache_key(sample_address, BlockchainNetwork.POLYGON)
        key2 = chainalysis_service._get_cache_key(sample_address, BlockchainNetwork.POLYGON)

        assert key1 == key2
        assert len(key1) == 64  # SHA256 hex

    @pytest.mark.asyncio
    async def test_cache_key_differs_by_network(self, chainalysis_service, sample_address):
        """Cache key deberia diferir por red."""
        key_polygon = chainalysis_service._get_cache_key(sample_address, BlockchainNetwork.POLYGON)
        key_ethereum = chainalysis_service._get_cache_key(sample_address, BlockchainNetwork.ETHEREUM)

        assert key_polygon != key_ethereum


# ==================== TESTS: Compliance Screening Service ====================

class TestComplianceScreeningService:
    """Tests para el orquestador de compliance screening."""

    @pytest.mark.asyncio
    async def test_apply_business_rules_approve(
        self, compliance_service, sample_screening_response
    ):
        """Score bajo deberia aprobar."""
        decision = compliance_service._apply_business_rules(
            screening_result=sample_screening_response,
            amount_usd=Decimal("100"),
        )

        assert decision.can_proceed is True
        assert decision.action == ScreeningAction.APPROVE
        assert decision.requires_alert is False

    @pytest.mark.asyncio
    async def test_apply_business_rules_reject_high_score(
        self, compliance_service, high_risk_screening_response
    ):
        """Score alto deberia rechazar."""
        decision = compliance_service._apply_business_rules(
            screening_result=high_risk_screening_response,
            amount_usd=Decimal("1000"),
        )

        assert decision.can_proceed is False
        assert decision.action == ScreeningAction.REJECT
        assert decision.requires_alert is True
        assert decision.requires_manual_review is True

    @pytest.mark.asyncio
    async def test_apply_business_rules_block_sanctioned(
        self, compliance_service, sanctioned_screening_response
    ):
        """Direccion sancionada deberia bloquear."""
        decision = compliance_service._apply_business_rules(
            screening_result=sanctioned_screening_response,
            amount_usd=Decimal("100"),
        )

        assert decision.can_proceed is False
        assert decision.action == ScreeningAction.BLOCK
        assert decision.requires_alert is True

    @pytest.mark.asyncio
    async def test_apply_business_rules_block_critical_category(
        self, compliance_service, sample_address
    ):
        """Categorias criticas siempre bloquean."""
        response = AddressScreeningResponse(
            screening_id="test",
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            status=ScreeningStatus.COMPLETED,
            risk_score=50,  # Score medio pero...
            risk_level=RiskLevel.MEDIUM,
            risk_indicators=[
                RiskIndicator(
                    category=RiskCategory.RANSOMWARE,  # ...categoria critica
                    severity=50,
                    description="Asociado con ransomware",
                    source="test",
                    confidence=0.9,
                ),
            ],
            direct_exposure=[],
            indirect_exposure=[],
            recommended_action=ScreeningAction.REVIEW,
            action_reason="Test",
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=False,
            requires_sar=False,
            pep_match=False,
        )

        decision = compliance_service._apply_business_rules(
            screening_result=response,
            amount_usd=Decimal("100"),
        )

        assert decision.can_proceed is False
        assert decision.action == ScreeningAction.BLOCK

    @pytest.mark.asyncio
    async def test_apply_business_rules_review_medium_score(
        self, compliance_service, sample_address
    ):
        """Score medio deberia requerir revision."""
        response = AddressScreeningResponse(
            screening_id="test",
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            status=ScreeningStatus.COMPLETED,
            risk_score=45,
            risk_level=RiskLevel.MEDIUM,
            risk_indicators=[],
            direct_exposure=[],
            indirect_exposure=[],
            recommended_action=ScreeningAction.REVIEW,
            action_reason="Test",
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=False,
            requires_sar=False,
            pep_match=False,
        )

        decision = compliance_service._apply_business_rules(
            screening_result=response,
            amount_usd=Decimal("100"),
        )

        assert decision.can_proceed is True  # Puede proceder pero...
        assert decision.action == ScreeningAction.REVIEW  # ...requiere revision
        assert decision.requires_manual_review is True

    def test_is_address_blocked_not_in_cache(self, compliance_service, sample_address):
        """Direccion no en cache deberia retornar False."""
        assert compliance_service._is_address_blocked(sample_address) is False

    def test_is_address_blocked_in_cache(self, compliance_service, sample_address):
        """Direccion en cache deberia retornar True."""
        compliance_service._add_to_blocked_cache(sample_address)
        assert compliance_service._is_address_blocked(sample_address) is True

    def test_blocked_cache_case_insensitive(self, compliance_service, sample_address):
        """Cache deberia ser case-insensitive."""
        compliance_service._add_to_blocked_cache(sample_address.lower())
        assert compliance_service._is_address_blocked(sample_address.upper()) is True

    @pytest.mark.asyncio
    async def test_quick_check_not_blocked(self, compliance_service, sample_address):
        """Quick check deberia retornar safe para direccion limpia."""
        # Mock chainalysis response
        compliance_service.chainalysis.screen_address = AsyncMock(
            return_value=AddressScreeningResponse(
                screening_id="test",
                address=sample_address,
                network=BlockchainNetwork.POLYGON,
                status=ScreeningStatus.COMPLETED,
                risk_score=10,
                risk_level=RiskLevel.LOW,
                risk_indicators=[],
                direct_exposure=[],
                indirect_exposure=[],
                recommended_action=ScreeningAction.APPROVE,
                action_reason="OK",
                screened_at=datetime.utcnow(),
                data_as_of=datetime.utcnow(),
                is_sanctioned=False,
                requires_sar=False,
                pep_match=False,
            )
        )

        is_safe, reason = await compliance_service.quick_check_address(
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
        )

        assert is_safe is True
        assert reason is None

    @pytest.mark.asyncio
    async def test_quick_check_blocked_sanctioned(self, compliance_service, sanctioned_address):
        """Quick check deberia bloquear direccion sancionada."""
        compliance_service.chainalysis.screen_address = AsyncMock(
            return_value=AddressScreeningResponse(
                screening_id="test",
                address=sanctioned_address,
                network=BlockchainNetwork.ETHEREUM,
                status=ScreeningStatus.COMPLETED,
                risk_score=100,
                risk_level=RiskLevel.SEVERE,
                risk_indicators=[],
                direct_exposure=[],
                indirect_exposure=[],
                recommended_action=ScreeningAction.BLOCK,
                action_reason="Sanctioned",
                screened_at=datetime.utcnow(),
                data_as_of=datetime.utcnow(),
                is_sanctioned=True,
                requires_sar=True,
                pep_match=False,
            )
        )

        is_safe, reason = await compliance_service.quick_check_address(
            address=sanctioned_address,
            network=BlockchainNetwork.ETHEREUM,
        )

        assert is_safe is False
        assert "sancionada" in reason.lower()

    @pytest.mark.asyncio
    async def test_screen_for_remittance_approved(
        self, compliance_service, sample_address, sample_screening_response
    ):
        """Screening exitoso deberia permitir proceder."""
        compliance_service.chainalysis.screen_address = AsyncMock(
            return_value=sample_screening_response
        )

        decision = await compliance_service.screen_address_for_remittance(
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            remittance_id="rem_123",
            user_id="user_456",
            amount_usd=Decimal("500"),
            direction="inbound",
        )

        assert decision.can_proceed is True
        assert decision.action == ScreeningAction.APPROVE

    @pytest.mark.asyncio
    async def test_screen_for_remittance_blocked_raises_exception(
        self, compliance_service, sanctioned_address, sanctioned_screening_response
    ):
        """Screening bloqueado deberia lanzar excepcion."""
        compliance_service.chainalysis.screen_address = AsyncMock(
            return_value=sanctioned_screening_response
        )

        with pytest.raises(AddressBlockedException) as exc_info:
            await compliance_service.screen_address_for_remittance(
                address=sanctioned_address,
                network=BlockchainNetwork.ETHEREUM,
                remittance_id="rem_123",
                user_id="user_456",
                amount_usd=Decimal("1000"),
                direction="inbound",
            )

        assert exc_info.value.address == sanctioned_address

    @pytest.mark.asyncio
    async def test_screen_for_remittance_adds_blocked_to_cache(
        self, compliance_service, sanctioned_address, sanctioned_screening_response
    ):
        """Direccion bloqueada deberia agregarse al cache."""
        compliance_service.chainalysis.screen_address = AsyncMock(
            return_value=sanctioned_screening_response
        )

        try:
            await compliance_service.screen_address_for_remittance(
                address=sanctioned_address,
                network=BlockchainNetwork.ETHEREUM,
                remittance_id="rem_123",
                user_id="user_456",
                amount_usd=Decimal("1000"),
                direction="inbound",
            )
        except AddressBlockedException:
            pass

        # Verificar que se agrego al cache
        assert compliance_service._is_address_blocked(sanctioned_address) is True


# ==================== TESTS: Screening Thresholds ====================

class TestScreeningThresholds:
    """Tests para configuracion de umbrales."""

    def test_default_thresholds(self):
        """Umbrales por defecto deberian ser razonables."""
        thresholds = ScreeningThresholds()

        assert thresholds.auto_approve_max_score == 30
        assert thresholds.review_min_score == 31
        assert thresholds.auto_reject_min_score == 70
        assert thresholds.block_min_score == 90

    def test_always_block_categories_includes_critical(self):
        """Categorias criticas siempre bloquean."""
        thresholds = ScreeningThresholds()

        assert RiskCategory.SANCTIONS in thresholds.always_block_categories
        assert RiskCategory.TERRORISM in thresholds.always_block_categories
        assert RiskCategory.CHILD_EXPLOITATION in thresholds.always_block_categories
        assert RiskCategory.RANSOMWARE in thresholds.always_block_categories

    def test_custom_thresholds(self):
        """Umbrales personalizados deberian aplicarse."""
        thresholds = ScreeningThresholds(
            auto_approve_max_score=20,
            auto_reject_min_score=60,
        )

        assert thresholds.auto_approve_max_score == 20
        assert thresholds.auto_reject_min_score == 60


# ==================== TESTS: ScreeningDecision ====================

class TestScreeningDecision:
    """Tests para el objeto de decision de screening."""

    def test_decision_to_dict(self):
        """Conversion a dict deberia incluir todos los campos."""
        decision = ScreeningDecision(
            can_proceed=True,
            action=ScreeningAction.APPROVE,
            reason="Test",
            requires_alert=False,
            requires_manual_review=False,
            screening_id="scr_123",
            risk_score=15,
            risk_level=RiskLevel.LOW,
        )

        result = decision.to_dict()

        assert result["can_proceed"] is True
        assert result["action"] == "approve"
        assert result["risk_score"] == 15
        assert result["risk_level"] == "low"


# ==================== TESTS: Integration Scenarios ====================

class TestIntegrationScenarios:
    """Tests de escenarios de integracion."""

    @pytest.mark.asyncio
    async def test_full_flow_clean_address(
        self, compliance_service, sample_address
    ):
        """Flujo completo para direccion limpia."""
        # Setup mock
        compliance_service.chainalysis.screen_address = AsyncMock(
            return_value=AddressScreeningResponse(
                screening_id="scr_clean",
                address=sample_address,
                network=BlockchainNetwork.POLYGON,
                status=ScreeningStatus.COMPLETED,
                risk_score=5,
                risk_level=RiskLevel.MINIMAL,
                risk_indicators=[],
                direct_exposure=[],
                indirect_exposure=[],
                recommended_action=ScreeningAction.APPROVE,
                action_reason="Clean address",
                screened_at=datetime.utcnow(),
                data_as_of=datetime.utcnow(),
                is_sanctioned=False,
                requires_sar=False,
                pep_match=False,
            )
        )

        # Execute
        decision = await compliance_service.screen_address_for_remittance(
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            remittance_id="rem_test",
            user_id="user_test",
            amount_usd=Decimal("100"),
            direction="inbound",
        )

        # Verify
        assert decision.can_proceed is True
        assert decision.requires_alert is False
        assert decision.requires_manual_review is False

    @pytest.mark.asyncio
    async def test_full_flow_high_value_transaction(
        self, compliance_service, sample_address
    ):
        """Flujo para transaccion de alto valor."""
        compliance_service.chainalysis.screen_address = AsyncMock(
            return_value=AddressScreeningResponse(
                screening_id="scr_highvalue",
                address=sample_address,
                network=BlockchainNetwork.POLYGON,
                status=ScreeningStatus.COMPLETED,
                risk_score=25,
                risk_level=RiskLevel.LOW,
                risk_indicators=[],
                direct_exposure=[],
                indirect_exposure=[],
                recommended_action=ScreeningAction.APPROVE,
                action_reason="OK",
                screened_at=datetime.utcnow(),
                data_as_of=datetime.utcnow(),
                is_sanctioned=False,
                requires_sar=False,
                pep_match=False,
            )
        )

        decision = await compliance_service.screen_address_for_remittance(
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            remittance_id="rem_highvalue",
            user_id="user_test",
            amount_usd=Decimal("15000"),  # Alto valor
            direction="inbound",
        )

        assert decision.can_proceed is True
        # Transacciones altas siempre deberian poder proceder si el score es bajo

    @pytest.mark.asyncio
    async def test_chainalysis_error_conservative_policy(
        self, compliance_service, sample_address
    ):
        """Error en Chainalysis deberia aplicar politica conservadora."""
        compliance_service.chainalysis.screen_address = AsyncMock(
            side_effect=ChainalysisError("API unavailable")
        )

        # Para monto bajo, deberia permitir con revision
        decision = await compliance_service._handle_screening_error(
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            remittance_id="rem_error",
            user_id="user_test",
            amount_usd=Decimal("100"),
            error="API unavailable",
        )

        assert decision.can_proceed is True
        assert decision.requires_alert is True
        assert decision.requires_manual_review is True

    @pytest.mark.asyncio
    async def test_chainalysis_error_high_amount_blocks(
        self, compliance_service, sample_address
    ):
        """Error con monto alto deberia bloquear."""
        decision = await compliance_service._handle_screening_error(
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            remittance_id="rem_error_high",
            user_id="user_test",
            amount_usd=Decimal("5000"),  # Monto alto
            error="API unavailable",
        )

        assert decision.can_proceed is False
        assert decision.action == ScreeningAction.REVIEW


# ==================== TESTS: Edge Cases ====================

class TestEdgeCases:
    """Tests para casos edge."""

    def test_empty_address_validation(self):
        """Direccion vacia deberia fallar validacion."""
        with pytest.raises(ValueError):
            AddressScreeningRequest(
                address="",
                network=BlockchainNetwork.POLYGON,
            )

    def test_invalid_network(self):
        """Red invalida deberia fallar."""
        with pytest.raises(ValueError):
            AddressScreeningRequest(
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f8bF16",
                network="invalid_network",
            )

    @pytest.mark.asyncio
    async def test_score_boundary_29_approves(self, compliance_service, sample_address):
        """Score 29 deberia aprobar (< 30 threshold)."""
        response = AddressScreeningResponse(
            screening_id="test",
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            status=ScreeningStatus.COMPLETED,
            risk_score=29,
            risk_level=RiskLevel.LOW,
            risk_indicators=[],
            direct_exposure=[],
            indirect_exposure=[],
            recommended_action=ScreeningAction.APPROVE,
            action_reason="OK",
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=False,
            requires_sar=False,
            pep_match=False,
        )

        decision = compliance_service._apply_business_rules(response, Decimal("100"))
        assert decision.action == ScreeningAction.APPROVE

    @pytest.mark.asyncio
    async def test_score_boundary_31_reviews(self, compliance_service, sample_address):
        """Score 31 deberia requerir revision (>= 31 threshold)."""
        response = AddressScreeningResponse(
            screening_id="test",
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            status=ScreeningStatus.COMPLETED,
            risk_score=31,
            risk_level=RiskLevel.MEDIUM,
            risk_indicators=[],
            direct_exposure=[],
            indirect_exposure=[],
            recommended_action=ScreeningAction.REVIEW,
            action_reason="Medium risk",
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=False,
            requires_sar=False,
            pep_match=False,
        )

        decision = compliance_service._apply_business_rules(response, Decimal("100"))
        assert decision.action == ScreeningAction.REVIEW

    @pytest.mark.asyncio
    async def test_score_boundary_70_rejects(self, compliance_service, sample_address):
        """Score 70 deberia rechazar (>= 70 threshold)."""
        response = AddressScreeningResponse(
            screening_id="test",
            address=sample_address,
            network=BlockchainNetwork.POLYGON,
            status=ScreeningStatus.COMPLETED,
            risk_score=70,
            risk_level=RiskLevel.HIGH,
            risk_indicators=[],
            direct_exposure=[],
            indirect_exposure=[],
            recommended_action=ScreeningAction.REJECT,
            action_reason="High risk",
            screened_at=datetime.utcnow(),
            data_as_of=datetime.utcnow(),
            is_sanctioned=False,
            requires_sar=False,
            pep_match=False,
        )

        decision = compliance_service._apply_business_rules(response, Decimal("100"))
        assert decision.action == ScreeningAction.REJECT
        assert decision.can_proceed is False
