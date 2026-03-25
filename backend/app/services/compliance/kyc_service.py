"""
Servicio de Verificacion KYC (Know Your Customer).

Cumple con requisitos de la LFPIORPI y disposiciones de la CNBV.
Integra verificacion de:
- INE (Instituto Nacional Electoral)
- CURP (Clave Unica de Registro de Poblacion)
- Comprobante de domicilio
- Verificacion biometrica (selfie)

Niveles de verificacion:
- Nivel 1: INE + CURP = $15,000 MXN/mes
- Nivel 2: + Comprobante domicilio = $50,000 MXN/mes
- Nivel 3: + Ingresos + PEP check = Sin limite
"""

import hashlib
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.models.compliance import (
    KYCProfile,
    KYCDocument,
    KYCLevel,
    KYCStatus,
    DocumentType,
    DocumentStatus,
    RiskLevel,
)


@dataclass
class VerificationResult:
    """Resultado de verificacion."""
    success: bool
    confidence: float
    extracted_data: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class KYCService:
    """Servicio principal de verificacion KYC."""

    # Limites por nivel (MXN)
    LIMITS = {
        KYCLevel.LEVEL_0: {"daily": Decimal("0"), "monthly": Decimal("0")},
        KYCLevel.LEVEL_1: {"daily": Decimal("5000"), "monthly": Decimal("15000")},
        KYCLevel.LEVEL_2: {"daily": Decimal("20000"), "monthly": Decimal("50000")},
        KYCLevel.LEVEL_3: {"daily": Decimal("1000000"), "monthly": Decimal("10000000")},
    }

    # Documentos requeridos por nivel
    REQUIRED_DOCS = {
        KYCLevel.LEVEL_1: [DocumentType.INE_FRONT, DocumentType.INE_BACK, DocumentType.SELFIE],
        KYCLevel.LEVEL_2: [DocumentType.INE_FRONT, DocumentType.INE_BACK, DocumentType.SELFIE, DocumentType.PROOF_OF_ADDRESS],
        KYCLevel.LEVEL_3: [
            DocumentType.INE_FRONT, DocumentType.INE_BACK, DocumentType.SELFIE,
            DocumentType.PROOF_OF_ADDRESS, DocumentType.PROOF_OF_INCOME
        ],
    }

    def __init__(self, db: Session):
        self.db = db

    # ============ Profile Management ============

    def get_or_create_profile(self, user_id: uuid.UUID) -> KYCProfile:
        """Obtiene o crea perfil KYC para usuario."""
        profile = self.db.query(KYCProfile).filter(
            KYCProfile.user_id == user_id
        ).first()

        if not profile:
            profile = KYCProfile(
                user_id=user_id,
                kyc_level=KYCLevel.LEVEL_0,
                status=KYCStatus.PENDING,
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)

        return profile

    def get_profile(self, user_id: uuid.UUID) -> Optional[KYCProfile]:
        """Obtiene perfil KYC."""
        return self.db.query(KYCProfile).filter(
            KYCProfile.user_id == user_id
        ).first()

    def update_profile(
        self,
        user_id: uuid.UUID,
        data: Dict[str, Any]
    ) -> KYCProfile:
        """Actualiza datos del perfil KYC."""
        profile = self.get_or_create_profile(user_id)

        # Campos actualizables
        allowed_fields = [
            "first_name", "last_name", "middle_name", "date_of_birth",
            "nationality", "country_of_residence", "curp", "rfc",
            "street_address", "city", "state", "postal_code", "country",
            "occupation", "employer", "monthly_income_range", "source_of_funds",
        ]

        for field in allowed_fields:
            if field in data:
                setattr(profile, field, data[field])

        profile.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(profile)

        return profile

    # ============ Document Management ============

    def upload_document(
        self,
        user_id: uuid.UUID,
        document_type: DocumentType,
        file_path: str,
        file_content: bytes,
    ) -> KYCDocument:
        """Sube documento para verificacion."""
        profile = self.get_or_create_profile(user_id)

        # Calcular hash del archivo
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Verificar si ya existe documento del mismo tipo
        existing = self.db.query(KYCDocument).filter(
            KYCDocument.kyc_profile_id == profile.id,
            KYCDocument.document_type == document_type,
            KYCDocument.status != DocumentStatus.REJECTED,
        ).first()

        if existing:
            # Actualizar documento existente
            existing.file_path = file_path
            existing.file_hash = file_hash
            existing.file_size = len(file_content)
            existing.status = DocumentStatus.PENDING
            existing.uploaded_at = datetime.utcnow()
            self.db.commit()
            return existing

        # Crear nuevo documento
        document = KYCDocument(
            kyc_profile_id=profile.id,
            document_type=document_type,
            file_path=file_path,
            file_hash=file_hash,
            file_size=len(file_content),
            status=DocumentStatus.PENDING,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        # Actualizar estado del perfil
        profile.status = KYCStatus.IN_REVIEW
        self.db.commit()

        return document

    def get_documents(self, user_id: uuid.UUID) -> List[KYCDocument]:
        """Obtiene documentos del usuario."""
        profile = self.get_profile(user_id)
        if not profile:
            return []
        return profile.documents

    def get_missing_documents(
        self,
        user_id: uuid.UUID,
        target_level: KYCLevel
    ) -> List[DocumentType]:
        """Obtiene documentos faltantes para alcanzar nivel."""
        profile = self.get_profile(user_id)
        if not profile:
            return list(self.REQUIRED_DOCS.get(target_level, []))

        required = set(self.REQUIRED_DOCS.get(target_level, []))
        verified = set()

        for doc in profile.documents:
            if doc.status == DocumentStatus.VERIFIED:
                verified.add(doc.document_type)

        return list(required - verified)

    # ============ Verification ============

    def verify_curp(self, curp: str) -> VerificationResult:
        """
        Verifica formato y validez de CURP.
        En produccion: integrar con RENAPO.
        """
        errors = []
        warnings = []
        extracted_data = {}

        # Validar formato CURP (18 caracteres)
        curp_pattern = r'^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d$'

        if not re.match(curp_pattern, curp.upper()):
            errors.append("Formato de CURP invalido")
            return VerificationResult(
                success=False,
                confidence=0.0,
                extracted_data={},
                errors=errors,
                warnings=warnings,
            )

        curp = curp.upper()

        # Extraer datos del CURP
        extracted_data = {
            "apellido_paterno": curp[0:2],
            "apellido_materno": curp[2],
            "nombre": curp[3],
            "fecha_nacimiento": f"19{curp[4:6]}-{curp[6:8]}-{curp[8:10]}",
            "sexo": "Masculino" if curp[10] == "H" else "Femenino",
            "estado_nacimiento": curp[11:13],
            "curp_completo": curp,
        }

        # Validar digito verificador (simplificado)
        # En produccion: algoritmo completo de verificacion

        return VerificationResult(
            success=True,
            confidence=0.95,
            extracted_data=extracted_data,
            errors=errors,
            warnings=warnings,
        )

    def verify_ine(self, ine_data: Dict[str, Any]) -> VerificationResult:
        """
        Verifica datos de INE.
        En produccion: integrar con servicio de OCR e INE.
        """
        errors = []
        warnings = []

        required_fields = ["clave_elector", "nombre", "apellidos", "fecha_nacimiento"]
        for field in required_fields:
            if field not in ine_data:
                errors.append(f"Campo requerido faltante: {field}")

        if errors:
            return VerificationResult(
                success=False,
                confidence=0.0,
                extracted_data={},
                errors=errors,
                warnings=warnings,
            )

        # Validar clave de elector (18 caracteres)
        clave = ine_data.get("clave_elector", "")
        if len(clave) != 18:
            errors.append("Clave de elector debe tener 18 caracteres")

        # Validar vigencia
        vigencia = ine_data.get("vigencia")
        if vigencia:
            try:
                vig_date = datetime.strptime(vigencia, "%Y")
                if vig_date < datetime.now():
                    errors.append("INE vencida")
            except ValueError:
                warnings.append("No se pudo validar vigencia")

        return VerificationResult(
            success=len(errors) == 0,
            confidence=0.90 if len(errors) == 0 else 0.0,
            extracted_data=ine_data,
            errors=errors,
            warnings=warnings,
        )

    def verify_document(
        self,
        document_id: uuid.UUID,
        verifier_id: uuid.UUID,
        approved: bool,
        rejection_reason: Optional[str] = None,
        extracted_data: Optional[Dict[str, Any]] = None,
    ) -> KYCDocument:
        """Verifica/rechaza documento manualmente."""
        document = self.db.query(KYCDocument).filter(
            KYCDocument.id == document_id
        ).first()

        if not document:
            raise ValueError("Documento no encontrado")

        document.status = DocumentStatus.VERIFIED if approved else DocumentStatus.REJECTED
        document.verified_by = verifier_id
        document.verified_at = datetime.utcnow()
        document.rejection_reason = rejection_reason
        document.extracted_data = extracted_data

        self.db.commit()
        self.db.refresh(document)

        # Verificar si se puede avanzar de nivel
        self._check_level_upgrade(document.kyc_profile_id)

        return document

    def _check_level_upgrade(self, profile_id: uuid.UUID):
        """Verifica si el perfil puede subir de nivel."""
        profile = self.db.query(KYCProfile).filter(
            KYCProfile.id == profile_id
        ).first()

        if not profile:
            return

        verified_docs = set()
        for doc in profile.documents:
            if doc.status == DocumentStatus.VERIFIED:
                verified_docs.add(doc.document_type)

        # Determinar nivel maximo alcanzable
        new_level = KYCLevel.LEVEL_0

        for level in [KYCLevel.LEVEL_3, KYCLevel.LEVEL_2, KYCLevel.LEVEL_1]:
            required = set(self.REQUIRED_DOCS.get(level, []))
            if required.issubset(verified_docs):
                new_level = level
                break

        if new_level != profile.kyc_level:
            profile.kyc_level = new_level
            limits = self.LIMITS[new_level]
            profile.daily_limit = limits["daily"]
            profile.monthly_limit = limits["monthly"]

            if new_level.value >= KYCLevel.LEVEL_1.value:
                profile.status = KYCStatus.APPROVED
            else:
                profile.status = KYCStatus.PENDING

            self.db.commit()

    # ============ Risk Assessment ============

    def calculate_risk_score(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Calcula score de riesgo del cliente."""
        profile = self.get_profile(user_id)
        if not profile:
            return {"score": 100, "level": RiskLevel.HIGH, "factors": []}

        factors = []
        score = 50  # Base score

        # Factor: Nivel KYC
        if profile.kyc_level == KYCLevel.LEVEL_3:
            score -= 20
            factors.append({"factor": "KYC Completo", "impact": -20})
        elif profile.kyc_level == KYCLevel.LEVEL_2:
            score -= 10
            factors.append({"factor": "KYC Intermedio", "impact": -10})
        elif profile.kyc_level == KYCLevel.LEVEL_0:
            score += 30
            factors.append({"factor": "Sin KYC", "impact": +30})

        # Factor: PEP
        if profile.is_pep:
            score += 25
            factors.append({"factor": "PEP", "impact": +25})

        # Factor: Pais de alto riesgo
        high_risk_countries = ["AF", "IR", "KP", "SY", "YE", "VE", "CU"]
        if profile.country_of_residence in high_risk_countries:
            score += 30
            factors.append({"factor": "Pais alto riesgo", "impact": +30})

        # Factor: Verificaciones negativas
        if profile.ofac_clear is False:
            score += 50
            factors.append({"factor": "OFAC Match", "impact": +50})

        if profile.adverse_media_clear is False:
            score += 20
            factors.append({"factor": "Media adversa", "impact": +20})

        # Normalizar score
        score = max(0, min(100, score))

        # Determinar nivel de riesgo
        if score >= 70:
            level = RiskLevel.HIGH
        elif score >= 50:
            level = RiskLevel.MEDIUM
        else:
            level = RiskLevel.LOW

        # Actualizar perfil
        profile.risk_score = score
        profile.risk_level = level
        self.db.commit()

        return {
            "score": score,
            "level": level.value,
            "factors": factors,
        }

    # ============ PEP & Sanctions Check ============

    def check_pep_status(self, profile_id: uuid.UUID) -> Dict[str, Any]:
        """
        Verifica si el usuario es PEP.
        En produccion: integrar con bases de datos de PEPs.
        """
        profile = self.db.query(KYCProfile).filter(
            KYCProfile.id == profile_id
        ).first()

        if not profile:
            return {"checked": False, "error": "Perfil no encontrado"}

        # Simulacion - en produccion integrar con proveedor real
        # Ejemplo: World-Check, Dow Jones, etc.

        profile.pep_checked = True
        profile.pep_check_date = datetime.utcnow()
        self.db.commit()

        return {
            "checked": True,
            "is_pep": profile.is_pep,
            "pep_position": profile.pep_position,
            "check_date": profile.pep_check_date.isoformat(),
        }

    def check_sanctions(self, profile_id: uuid.UUID) -> Dict[str, Any]:
        """
        Verifica contra listas de sanciones (OFAC, ONU, etc).
        En produccion: integrar con proveedores de screening.
        """
        profile = self.db.query(KYCProfile).filter(
            KYCProfile.id == profile_id
        ).first()

        if not profile:
            return {"checked": False, "error": "Perfil no encontrado"}

        # Simulacion - en produccion integrar con:
        # - OFAC SDN List
        # - UN Consolidated Sanctions
        # - EU Sanctions
        # - Mexico UIF lists

        profile.ofac_checked = True
        profile.ofac_check_date = datetime.utcnow()
        profile.ofac_clear = True  # Simulado como limpio

        self.db.commit()

        return {
            "checked": True,
            "ofac_clear": profile.ofac_clear,
            "check_date": profile.ofac_check_date.isoformat(),
            "lists_checked": ["OFAC_SDN", "UN_CONSOLIDATED", "EU_SANCTIONS"],
        }

    # ============ Limits & Compliance ============

    def check_transaction_allowed(
        self,
        user_id: uuid.UUID,
        amount: Decimal,
        currency: str = "MXN"
    ) -> Dict[str, Any]:
        """Verifica si transaccion esta dentro de limites KYC."""
        profile = self.get_profile(user_id)

        if not profile or profile.status != KYCStatus.APPROVED:
            return {
                "allowed": False,
                "reason": "KYC no aprobado",
                "required_level": KYCLevel.LEVEL_1.value,
            }

        # Verificar limite diario (simplificado)
        if amount > profile.daily_limit:
            return {
                "allowed": False,
                "reason": f"Excede limite diario de {profile.daily_limit} MXN",
                "current_limit": float(profile.daily_limit),
                "required_level": self._get_required_level(amount).value,
            }

        # Verificar limite mensual
        new_monthly = profile.current_month_volume + amount
        if new_monthly > profile.monthly_limit:
            return {
                "allowed": False,
                "reason": f"Excede limite mensual de {profile.monthly_limit} MXN",
                "current_volume": float(profile.current_month_volume),
                "current_limit": float(profile.monthly_limit),
                "required_level": self._get_required_level(amount).value,
            }

        return {
            "allowed": True,
            "remaining_daily": float(profile.daily_limit - amount),
            "remaining_monthly": float(profile.monthly_limit - new_monthly),
        }

    def _get_required_level(self, amount: Decimal) -> KYCLevel:
        """Determina nivel KYC requerido para monto."""
        for level in [KYCLevel.LEVEL_1, KYCLevel.LEVEL_2, KYCLevel.LEVEL_3]:
            if amount <= self.LIMITS[level]["monthly"]:
                return level
        return KYCLevel.LEVEL_3

    def record_transaction_volume(
        self,
        user_id: uuid.UUID,
        amount: Decimal
    ):
        """Registra volumen de transaccion."""
        profile = self.get_profile(user_id)
        if profile:
            profile.current_month_volume += amount
            profile.total_volume += amount
            self.db.commit()

    def reset_monthly_volumes(self):
        """Resetea volumenes mensuales (ejecutar primer dia del mes)."""
        self.db.query(KYCProfile).update({
            KYCProfile.current_month_volume: Decimal("0")
        })
        self.db.commit()

    # ============ Reporting ============

    def get_kyc_statistics(self) -> Dict[str, Any]:
        """Obtiene estadisticas de KYC."""
        from sqlalchemy import func

        total = self.db.query(KYCProfile).count()

        by_level = {}
        for level in KYCLevel:
            count = self.db.query(KYCProfile).filter(
                KYCProfile.kyc_level == level
            ).count()
            by_level[level.value] = count

        by_status = {}
        for status in KYCStatus:
            count = self.db.query(KYCProfile).filter(
                KYCProfile.status == status
            ).count()
            by_status[status.value] = count

        pending_documents = self.db.query(KYCDocument).filter(
            KYCDocument.status == DocumentStatus.PENDING
        ).count()

        # Usuarios de alto riesgo
        high_risk_users = self.db.query(KYCProfile).filter(
            KYCProfile.risk_level == RiskLevel.HIGH
        ).count()

        # PEPs identificados
        pep_count = self.db.query(KYCProfile).filter(
            KYCProfile.is_pep == True
        ).count()

        # Score promedio de riesgo
        avg_score = self.db.query(func.avg(KYCProfile.risk_score)).scalar() or 50

        # Perfiles pendientes de verificacion
        pending_verification = self.db.query(KYCProfile).filter(
            KYCProfile.status.in_([KYCStatus.PENDING, KYCStatus.IN_REVIEW])
        ).count()

        return {
            "total_profiles": total,
            "by_level": by_level,
            "by_status": by_status,
            "pending_documents": pending_documents,
            "pending_verification": pending_verification,
            "high_risk_users": high_risk_users,
            "pep_count": pep_count,
            "avg_risk_score": float(avg_score),
        }
