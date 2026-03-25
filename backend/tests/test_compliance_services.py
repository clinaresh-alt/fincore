"""
Tests para servicios de Compliance (KYC, AML).

Cobertura de dataclasses, constantes y validaciones basicas.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from datetime import datetime
import uuid

from app.models.compliance import (
    KYCLevel,
    KYCStatus,
    DocumentType,
    DocumentStatus,
    RiskLevel,
)


class TestKYCLevelEnum:
    """Tests para enum KYCLevel."""

    def test_kyc_levels_exist(self):
        """Test que existen todos los niveles KYC."""
        assert hasattr(KYCLevel, 'LEVEL_0')
        assert hasattr(KYCLevel, 'LEVEL_1')
        assert hasattr(KYCLevel, 'LEVEL_2')
        assert hasattr(KYCLevel, 'LEVEL_3')

    def test_kyc_level_values(self):
        """Test valores de niveles KYC."""
        assert KYCLevel.LEVEL_0.value == "level_0"
        assert KYCLevel.LEVEL_1.value == "level_1"
        assert KYCLevel.LEVEL_2.value == "level_2"
        assert KYCLevel.LEVEL_3.value == "level_3"


class TestKYCStatusEnum:
    """Tests para enum KYCStatus."""

    def test_kyc_status_exist(self):
        """Test que existen estados KYC."""
        assert hasattr(KYCStatus, 'PENDING')
        assert hasattr(KYCStatus, 'IN_REVIEW')
        assert hasattr(KYCStatus, 'APPROVED')
        assert hasattr(KYCStatus, 'REJECTED')
        assert hasattr(KYCStatus, 'EXPIRED')

    def test_kyc_status_values(self):
        """Test valores de estados KYC."""
        assert KYCStatus.PENDING.value == "pending"
        assert KYCStatus.APPROVED.value == "approved"
        assert KYCStatus.REJECTED.value == "rejected"


class TestDocumentTypeEnum:
    """Tests para enum DocumentType."""

    def test_document_types_exist(self):
        """Test que existen tipos de documento."""
        assert hasattr(DocumentType, 'INE_FRONT')
        assert hasattr(DocumentType, 'INE_BACK')
        assert hasattr(DocumentType, 'SELFIE')
        assert hasattr(DocumentType, 'PROOF_OF_ADDRESS')

    def test_ine_document_types(self):
        """Test tipos de documento INE."""
        assert DocumentType.INE_FRONT.value == "ine_front"
        assert DocumentType.INE_BACK.value == "ine_back"


class TestDocumentStatusEnum:
    """Tests para enum DocumentStatus."""

    def test_document_status_exist(self):
        """Test que existen estados de documento."""
        assert hasattr(DocumentStatus, 'PENDING')
        assert hasattr(DocumentStatus, 'VERIFIED')
        assert hasattr(DocumentStatus, 'REJECTED')

    def test_document_status_values(self):
        """Test valores de estados de documento."""
        assert DocumentStatus.PENDING.value == "pending"
        assert DocumentStatus.VERIFIED.value == "verified"
        assert DocumentStatus.REJECTED.value == "rejected"


class TestRiskLevelEnum:
    """Tests para enum RiskLevel."""

    def test_risk_levels_exist(self):
        """Test que existen niveles de riesgo."""
        assert hasattr(RiskLevel, 'LOW')
        assert hasattr(RiskLevel, 'MEDIUM')
        assert hasattr(RiskLevel, 'HIGH')

    def test_risk_level_values(self):
        """Test valores de niveles de riesgo."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"


class TestKYCServiceConstants:
    """Tests para constantes de KYCService."""

    def test_kyc_limits_defined(self):
        """Test que limites KYC estan definidos."""
        from app.services.compliance.kyc_service import KYCService

        assert KYCLevel.LEVEL_0 in KYCService.LIMITS
        assert KYCLevel.LEVEL_1 in KYCService.LIMITS
        assert KYCLevel.LEVEL_2 in KYCService.LIMITS
        assert KYCLevel.LEVEL_3 in KYCService.LIMITS

    def test_kyc_limits_increasing(self):
        """Test que limites aumentan con nivel."""
        from app.services.compliance.kyc_service import KYCService

        limit_1 = KYCService.LIMITS[KYCLevel.LEVEL_1]["monthly"]
        limit_2 = KYCService.LIMITS[KYCLevel.LEVEL_2]["monthly"]
        limit_3 = KYCService.LIMITS[KYCLevel.LEVEL_3]["monthly"]

        assert limit_2 > limit_1
        assert limit_3 > limit_2

    def test_required_docs_defined(self):
        """Test que documentos requeridos estan definidos."""
        from app.services.compliance.kyc_service import KYCService

        assert KYCLevel.LEVEL_1 in KYCService.REQUIRED_DOCS
        assert KYCLevel.LEVEL_2 in KYCService.REQUIRED_DOCS
        assert KYCLevel.LEVEL_3 in KYCService.REQUIRED_DOCS

    def test_required_docs_include_ine(self):
        """Test que todos los niveles requieren INE."""
        from app.services.compliance.kyc_service import KYCService

        for level, docs in KYCService.REQUIRED_DOCS.items():
            assert DocumentType.INE_FRONT in docs
            assert DocumentType.INE_BACK in docs


class TestKYCServiceVerificationResult:
    """Tests para dataclass VerificationResult."""

    def test_verification_result_creation(self):
        """Test creacion de VerificationResult."""
        from app.services.compliance.kyc_service import VerificationResult

        result = VerificationResult(
            success=True,
            confidence=0.95,
            extracted_data={"name": "Juan Perez"},
            errors=[],
            warnings=["Imagen borrosa"]
        )

        assert result.success is True
        assert result.confidence == 0.95
        assert "name" in result.extracted_data
        assert len(result.warnings) == 1

    def test_verification_result_failed(self):
        """Test VerificationResult fallido."""
        from app.services.compliance.kyc_service import VerificationResult

        result = VerificationResult(
            success=False,
            confidence=0.3,
            extracted_data={},
            errors=["Documento no legible", "Fecha expirada"],
            warnings=[]
        )

        assert result.success is False
        assert len(result.errors) == 2


class TestKYCServiceInit:
    """Tests para inicializacion de KYCService."""

    def test_init_with_db_session(self):
        """Test inicializacion con sesion de DB."""
        from app.services.compliance.kyc_service import KYCService

        mock_db = MagicMock()
        service = KYCService(db=mock_db)

        assert service.db == mock_db


class TestAMLServiceInit:
    """Tests para inicializacion de AMLService."""

    def test_init_with_db_session(self):
        """Test inicializacion con sesion de DB."""
        from app.services.compliance.aml_service import AMLService

        mock_db = MagicMock()
        service = AMLService(db=mock_db)

        assert service.db == mock_db


class TestReportingServiceInit:
    """Tests para inicializacion de ReportingService."""

    def test_reporting_service_init(self):
        """Test inicializacion de ReportingService."""
        from app.services.compliance.reporting_service import ReportingService

        mock_db = MagicMock()
        service = ReportingService(db=mock_db)

        assert service.db == mock_db
