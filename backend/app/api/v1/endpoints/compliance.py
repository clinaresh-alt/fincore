"""
API Endpoints para Compliance PLD/AML.

Expone funcionalidades de:
- Verificacion KYC (Know Your Customer)
- Monitoreo AML (Anti Money Laundering)
- Alertas y reportes UIF
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.compliance import (
    KYCLevel,
    KYCStatus,
    DocumentType,
    AlertSeverity,
    AlertStatus,
    AlertType,
    ReportType,
)
from app.services.compliance import (
    KYCService,
    AMLService,
    ReportingService,
    TransactionData,
)


router = APIRouter()


# ============ Schemas ============

class KYCProfileUpdate(BaseModel):
    """Datos para actualizar perfil KYC."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    nationality: Optional[str] = Field(None, max_length=3)
    curp: Optional[str] = Field(None, max_length=18)
    rfc: Optional[str] = Field(None, max_length=13)
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    occupation: Optional[str] = None
    employer: Optional[str] = None
    monthly_income_range: Optional[str] = None
    source_of_funds: Optional[str] = None


class KYCProfileResponse(BaseModel):
    """Response de perfil KYC."""
    id: str
    user_id: str
    kyc_level: str
    status: str
    risk_level: str
    risk_score: int
    first_name: Optional[str]
    last_name: Optional[str]
    curp: Optional[str]
    daily_limit: float
    monthly_limit: float
    current_month_volume: float
    is_pep: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Response de documento KYC."""
    id: str
    document_type: str
    status: str
    uploaded_at: datetime
    verified_at: Optional[datetime]
    rejection_reason: Optional[str]


class AlertResponse(BaseModel):
    """Response de alerta AML."""
    id: str
    user_id: str
    alert_type: str
    severity: str
    status: str
    title: str
    description: str
    amount: Optional[float]
    detected_at: datetime
    assigned_to: Optional[str]


class AlertUpdateRequest(BaseModel):
    """Request para actualizar alerta."""
    status: str
    notes: Optional[str] = None
    false_positive: Optional[bool] = None


class ReportResponse(BaseModel):
    """Response de reporte regulatorio."""
    id: str
    report_type: str
    reference_number: str
    period_start: datetime
    period_end: datetime
    status: str
    transactions_count: int
    total_amount: float
    created_at: datetime


class GenerateROVRequest(BaseModel):
    """Request para generar ROV."""
    period_start: datetime
    period_end: datetime


class GenerateROSRequest(BaseModel):
    """Request para generar ROS."""
    alert_ids: List[str]
    narrative: str


class TransactionCheckRequest(BaseModel):
    """Request para verificar transaccion."""
    amount: Decimal
    currency: str = "MXN"


# ============ KYC Endpoints ============

@router.get("/kyc/profile", response_model=KYCProfileResponse)
async def get_kyc_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene perfil KYC del usuario actual."""
    kyc = KYCService(db)
    profile = kyc.get_or_create_profile(current_user.id)

    return KYCProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        kyc_level=profile.kyc_level.value,
        status=profile.status.value,
        risk_level=profile.risk_level.value,
        risk_score=profile.risk_score,
        first_name=profile.first_name,
        last_name=profile.last_name,
        curp=profile.curp,
        daily_limit=float(profile.daily_limit),
        monthly_limit=float(profile.monthly_limit),
        current_month_volume=float(profile.current_month_volume),
        is_pep=profile.is_pep,
        created_at=profile.created_at,
    )


@router.put("/kyc/profile", response_model=KYCProfileResponse)
async def update_kyc_profile(
    data: KYCProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza perfil KYC del usuario."""
    kyc = KYCService(db)
    profile = kyc.update_profile(current_user.id, data.model_dump(exclude_none=True))

    return KYCProfileResponse(
        id=str(profile.id),
        user_id=str(profile.user_id),
        kyc_level=profile.kyc_level.value,
        status=profile.status.value,
        risk_level=profile.risk_level.value,
        risk_score=profile.risk_score,
        first_name=profile.first_name,
        last_name=profile.last_name,
        curp=profile.curp,
        daily_limit=float(profile.daily_limit),
        monthly_limit=float(profile.monthly_limit),
        current_month_volume=float(profile.current_month_volume),
        is_pep=profile.is_pep,
        created_at=profile.created_at,
    )


@router.post("/kyc/documents")
async def upload_kyc_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sube documento para verificacion KYC."""
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de documento invalido: {document_type}",
        )

    kyc = KYCService(db)
    file_content = await file.read()

    # En produccion: guardar archivo en S3/GCS con encriptacion
    file_path = f"/secure/kyc/{current_user.id}/{document_type}_{file.filename}"

    document = kyc.upload_document(
        user_id=current_user.id,
        document_type=doc_type,
        file_path=file_path,
        file_content=file_content,
    )

    return {
        "id": str(document.id),
        "document_type": document.document_type.value,
        "status": document.status.value,
        "uploaded_at": document.uploaded_at.isoformat(),
    }


@router.get("/kyc/documents", response_model=List[DocumentResponse])
async def list_kyc_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista documentos KYC del usuario."""
    kyc = KYCService(db)
    documents = kyc.get_documents(current_user.id)

    return [
        DocumentResponse(
            id=str(doc.id),
            document_type=doc.document_type.value,
            status=doc.status.value,
            uploaded_at=doc.uploaded_at,
            verified_at=doc.verified_at,
            rejection_reason=doc.rejection_reason,
        )
        for doc in documents
    ]


@router.get("/kyc/missing-documents")
async def get_missing_documents(
    target_level: str = "level_2",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene documentos faltantes para alcanzar nivel KYC."""
    try:
        level = KYCLevel(target_level)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nivel KYC invalido: {target_level}",
        )

    kyc = KYCService(db)
    missing = kyc.get_missing_documents(current_user.id, level)

    return {
        "target_level": target_level,
        "missing_documents": [d.value for d in missing],
    }


@router.post("/kyc/verify-curp")
async def verify_curp(
    curp: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifica CURP del usuario."""
    kyc = KYCService(db)
    result = kyc.verify_curp(curp)

    if result.success:
        # Actualizar CURP en perfil
        kyc.update_profile(current_user.id, {"curp": curp.upper()})

    return {
        "valid": result.success,
        "confidence": result.confidence,
        "extracted_data": result.extracted_data,
        "errors": result.errors,
        "warnings": result.warnings,
    }


@router.get("/kyc/risk-score")
async def get_risk_score(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calcula y obtiene risk score del usuario."""
    kyc = KYCService(db)
    return kyc.calculate_risk_score(current_user.id)


@router.post("/kyc/check-transaction")
async def check_transaction_allowed(
    data: TransactionCheckRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verifica si transaccion esta permitida por KYC."""
    kyc = KYCService(db)
    return kyc.check_transaction_allowed(current_user.id, data.amount, data.currency)


@router.get("/kyc/statistics")
async def get_kyc_statistics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene estadisticas de KYC (solo Admin)."""
    if current_user.rol != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden ver estadisticas",
        )

    kyc = KYCService(db)
    return kyc.get_kyc_statistics()


# ============ AML Endpoints ============

@router.get("/aml/alerts", response_model=List[AlertResponse])
async def list_aml_alerts(
    status_filter: Optional[str] = None,
    severity_filter: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista alertas AML (solo Admin/Analista)."""
    if current_user.rol not in ["Admin", "Analista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )

    aml = AMLService(db)

    status_enum = AlertStatus(status_filter) if status_filter else None
    severity_enum = AlertSeverity(severity_filter) if severity_filter else None

    alerts = aml.get_alerts(status=status_enum, severity=severity_enum, limit=limit)

    return [
        AlertResponse(
            id=str(a.id),
            user_id=str(a.user_id),
            alert_type=a.alert_type.value,
            severity=a.severity.value,
            status=a.status.value,
            title=a.title,
            description=a.description,
            amount=float(a.amount) if a.amount else None,
            detected_at=a.detected_at,
            assigned_to=str(a.assigned_to) if a.assigned_to else None,
        )
        for a in alerts
    ]


@router.get("/aml/alerts/user/{user_id}", response_model=List[AlertResponse])
async def get_user_alerts(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene alertas de un usuario especifico."""
    if current_user.rol not in ["Admin", "Analista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )

    aml = AMLService(db)
    alerts = aml.get_user_alerts(UUID(user_id))

    return [
        AlertResponse(
            id=str(a.id),
            user_id=str(a.user_id),
            alert_type=a.alert_type.value,
            severity=a.severity.value,
            status=a.status.value,
            title=a.title,
            description=a.description,
            amount=float(a.amount) if a.amount else None,
            detected_at=a.detected_at,
            assigned_to=str(a.assigned_to) if a.assigned_to else None,
        )
        for a in alerts
    ]


@router.put("/aml/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    data: AlertUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza estado de alerta."""
    if current_user.rol not in ["Admin", "Analista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )

    try:
        status_enum = AlertStatus(data.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado invalido: {data.status}",
        )

    aml = AMLService(db)
    alert = aml.update_alert_status(
        alert_id=UUID(alert_id),
        status=status_enum,
        investigator_id=current_user.id,
        notes=data.notes,
        false_positive=data.false_positive,
    )

    return {"status": "updated", "alert_id": str(alert.id)}


@router.post("/aml/alerts/{alert_id}/escalate")
async def escalate_alert(
    alert_id: str,
    notes: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Escala alerta para revision superior."""
    if current_user.rol not in ["Admin", "Analista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )

    aml = AMLService(db)
    alert = aml.escalate_alert(UUID(alert_id), current_user.id, notes)

    return {"status": "escalated", "alert_id": str(alert.id)}


@router.get("/aml/statistics")
async def get_aml_statistics(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene estadisticas AML."""
    if current_user.rol not in ["Admin", "Analista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )

    aml = AMLService(db)
    return aml.get_statistics(days)


# ============ Reports Endpoints ============

@router.get("/reports", response_model=List[ReportResponse])
async def list_reports(
    report_type: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista reportes regulatorios."""
    if current_user.rol not in ["Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores",
        )

    type_enum = ReportType(report_type) if report_type else None

    reports = ReportingService(db)
    result = reports.get_reports(report_type=type_enum, status=status_filter, limit=limit)

    return [
        ReportResponse(
            id=str(r.id),
            report_type=r.report_type.value,
            reference_number=r.reference_number,
            period_start=r.period_start,
            period_end=r.period_end,
            status=r.status,
            transactions_count=r.transactions_count,
            total_amount=float(r.total_amount),
            created_at=r.created_at,
        )
        for r in result
    ]


@router.post("/reports/rov", response_model=ReportResponse)
async def generate_rov_report(
    data: GenerateROVRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Genera Reporte de Operaciones con Activos Virtuales."""
    if current_user.rol not in ["Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores",
        )

    reports = ReportingService(db)
    report = reports.generate_rov(data.period_start, data.period_end, current_user.id)

    return ReportResponse(
        id=str(report.id),
        report_type=report.report_type.value,
        reference_number=report.reference_number,
        period_start=report.period_start,
        period_end=report.period_end,
        status=report.status,
        transactions_count=report.transactions_count,
        total_amount=float(report.total_amount),
        created_at=report.created_at,
    )


@router.post("/reports/ros", response_model=ReportResponse)
async def generate_ros_report(
    data: GenerateROSRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Genera Reporte de Operaciones Sospechosas."""
    if current_user.rol not in ["Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores",
        )

    reports = ReportingService(db)
    alert_uuids = [UUID(aid) for aid in data.alert_ids]
    report = reports.generate_ros(alert_uuids, current_user.id, data.narrative)

    return ReportResponse(
        id=str(report.id),
        report_type=report.report_type.value,
        reference_number=report.reference_number,
        period_start=report.period_start,
        period_end=report.period_end,
        status=report.status,
        transactions_count=report.transactions_count,
        total_amount=float(report.total_amount),
        created_at=report.created_at,
    )


@router.post("/reports/{report_id}/approve")
async def approve_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aprueba reporte para envio a UIF."""
    if current_user.rol != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores",
        )

    reports = ReportingService(db)
    report = reports.approve_report(UUID(report_id), current_user.id)

    return {"status": "approved", "report_id": str(report.id)}


@router.post("/reports/{report_id}/submit")
async def submit_report(
    report_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Envia reporte a UIF."""
    if current_user.rol != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores",
        )

    reports = ReportingService(db)
    report = reports.submit_report(UUID(report_id))

    return {
        "status": "submitted",
        "report_id": str(report.id),
        "submitted_at": report.submitted_at.isoformat(),
    }


@router.get("/reports/statistics")
async def get_reporting_statistics(
    year: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene estadisticas de reportes."""
    if current_user.rol != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores",
        )

    reports = ReportingService(db)
    return reports.get_reporting_statistics(year)


# ============ Dashboard ============

@router.get("/dashboard")
async def get_compliance_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dashboard consolidado de compliance."""
    if current_user.rol not in ["Admin", "Analista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado",
        )

    kyc = KYCService(db)
    aml = AMLService(db)
    reports = ReportingService(db)

    return {
        "kyc_statistics": kyc.get_kyc_statistics(),
        "aml_statistics": aml.get_statistics(30),
        "reporting_statistics": reports.get_reporting_statistics(),
    }
