"""
Endpoints de Gestion de Empresas/Entidades Solicitantes.
CRUD completo con gestion de documentos y verificacion KYC.
"""
import os
import uuid as uuid_lib
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.company import (
    Company, CompanyDocument, CompanyType, CompanySize,
    CompanyStatus, CompanyDocumentType
)
from app.models.project import Project
from app.models.audit import AuditLog, AuditAction
from app.schemas.company import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    CompanyListItem, CompanyListResponse, CompanyWithDocuments,
    CompanyDocumentCreate, CompanyDocumentUpdate, CompanyDocumentResponse,
    CompanyVerificationUpdate, CompanyTypesResponse, CompanyTypeOption
)

router = APIRouter(prefix="/companies", tags=["Empresas"])

# Directorio para almacenar documentos
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "uploads", "companies")


def ensure_upload_dir():
    """Asegura que el directorio de uploads exista."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# ENDPOINTS CRUD DE EMPRESAS
# ============================================================

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crea una nueva empresa/entidad solicitante.
    El usuario autenticado queda como propietario.
    """
    # Verificar que el RFC no exista
    existing = db.query(Company).filter(Company.rfc == company_data.rfc.upper()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una empresa registrada con el RFC {company_data.rfc}"
        )

    # Crear empresa
    company = Company(
        user_id=current_user.id,
        estado_verificacion=CompanyStatus.PENDIENTE,
        **company_data.model_dump(exclude={'datos_adicionales'})
    )

    if company_data.datos_adicionales:
        company.datos_adicionales = company_data.datos_adicionales

    db.add(company)
    db.commit()
    db.refresh(company)

    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.COMPANY_CREATED if hasattr(AuditAction, 'COMPANY_CREATED') else AuditAction.PROJECT_CREATED,
        resource_type="Company",
        resource_id=company.id,
        description=f"Empresa creada: {company.razon_social}"
    )
    db.add(audit)
    db.commit()

    return _company_to_response(company, db)


@router.get("/", response_model=CompanyListResponse)
async def list_companies(
    estado: Optional[str] = Query(None, description="Filtrar por estado de verificacion"),
    sector: Optional[str] = Query(None, description="Filtrar por sector"),
    search: Optional[str] = Query(None, description="Buscar por razon social o RFC"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista empresas del usuario actual.
    Admin/Analista pueden ver todas las empresas.
    """
    query = db.query(Company)

    # Filtro por rol
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        query = query.filter(Company.user_id == current_user.id)

    # Filtros opcionales
    if estado:
        query = query.filter(Company.estado_verificacion == estado)
    if sector:
        query = query.filter(Company.sector == sector)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Company.razon_social.ilike(search_term)) |
            (Company.nombre_comercial.ilike(search_term)) |
            (Company.rfc.ilike(search_term))
        )

    # Contar total
    total = query.count()

    # Paginacion
    offset = (page - 1) * page_size
    companies = query.order_by(Company.created_at.desc()).offset(offset).limit(page_size).all()

    # Calcular total de paginas
    total_pages = (total + page_size - 1) // page_size

    # Construir respuesta
    items = []
    for company in companies:
        # Contar proyectos asociados
        total_proyectos = db.query(Project).filter(Project.empresa_id == company.id).count()

        items.append(CompanyListItem(
            id=company.id,
            razon_social=company.razon_social,
            nombre_comercial=company.nombre_comercial,
            tipo_empresa=company.tipo_empresa.value if hasattr(company.tipo_empresa, 'value') else str(company.tipo_empresa),
            rfc=company.rfc,
            estado_verificacion=company.estado_verificacion.value if hasattr(company.estado_verificacion, 'value') else str(company.estado_verificacion),
            sector=company.sector,
            municipio=company.municipio,
            estado=company.estado,
            total_proyectos=total_proyectos,
            created_at=company.created_at
        ))

    return CompanyListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/types", response_model=CompanyTypesResponse)
async def get_company_types():
    """
    Obtiene los tipos y constantes disponibles para empresas.
    Util para poblar formularios.
    """
    return CompanyTypesResponse(
        tipos_empresa=[
            CompanyTypeOption(value=t.value, label=t.value)
            for t in CompanyType
        ],
        tamanos_empresa=[
            CompanyTypeOption(value=t.value, label=t.value)
            for t in CompanySize
        ],
        estados_verificacion=[
            CompanyTypeOption(value=t.value, label=t.value)
            for t in CompanyStatus
        ],
        tipos_documento=[
            CompanyTypeOption(value=t.value, label=t.value)
            for t in CompanyDocumentType
        ]
    )


@router.get("/{company_id}", response_model=CompanyWithDocuments)
async def get_company(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene detalle completo de una empresa con sus documentos.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar acceso
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta empresa"
            )

    return _company_to_response_with_documents(company, db)


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: UUID,
    company_data: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualiza datos de una empresa.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar acceso
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta empresa"
            )

    # Actualizar campos
    update_data = company_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(company, field, value)

    company.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(company)

    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_MODIFIED,
        resource_type="Company",
        resource_id=company.id,
        description=f"Empresa actualizada: {company.razon_social}",
        new_values=update_data
    )
    db.add(audit)
    db.commit()

    return _company_to_response(company, db)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Elimina una empresa y sus documentos.
    Solo Admin puede eliminar.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar que no tenga proyectos asociados
    projects_count = db.query(Project).filter(Project.empresa_id == company_id).count()
    if projects_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar: la empresa tiene {projects_count} proyectos asociados"
        )

    company_name = company.razon_social

    # Eliminar documentos fisicos
    documents = db.query(CompanyDocument).filter(CompanyDocument.empresa_id == company_id).all()
    for doc in documents:
        try:
            if os.path.exists(doc.ruta_archivo):
                os.remove(doc.ruta_archivo)
        except Exception:
            pass

    # Eliminar empresa (cascade elimina documentos en BD)
    db.delete(company)
    db.commit()

    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_DELETED,
        resource_type="Company",
        resource_id=company_id,
        description=f"Empresa eliminada: {company_name}"
    )
    db.add(audit)
    db.commit()


# ============================================================
# ENDPOINTS DE VERIFICACION
# ============================================================

@router.put("/{company_id}/verification", response_model=CompanyResponse)
async def update_company_verification(
    company_id: UUID,
    verification_data: CompanyVerificationUpdate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ANALISTA])),
    db: Session = Depends(get_db)
):
    """
    Actualiza el estado de verificacion de una empresa.
    Solo Admin y Analista.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Actualizar verificacion
    company.estado_verificacion = verification_data.estado_verificacion
    if verification_data.notas_verificacion:
        company.notas_verificacion = verification_data.notas_verificacion
    if verification_data.score_riesgo is not None:
        company.score_riesgo = verification_data.score_riesgo

    company.fecha_verificacion = datetime.utcnow()
    company.verificado_por = current_user.id

    db.commit()
    db.refresh(company)

    # Auditoria
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_APPROVED if verification_data.estado_verificacion in ["Verificada", "Activa"] else AuditAction.PROJECT_MODIFIED,
        resource_type="Company",
        resource_id=company.id,
        description=f"Verificacion actualizada: {company.razon_social} -> {verification_data.estado_verificacion}",
        new_values=verification_data.model_dump()
    )
    db.add(audit)
    db.commit()

    return _company_to_response(company, db)


# ============================================================
# ENDPOINTS DE DOCUMENTOS
# ============================================================

@router.get("/{company_id}/documents", response_model=List[CompanyDocumentResponse])
async def list_company_documents(
    company_id: UUID,
    tipo: Optional[str] = Query(None, description="Filtrar por tipo de documento"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista documentos de una empresa.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar acceso
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta empresa"
            )

    query = db.query(CompanyDocument).filter(CompanyDocument.empresa_id == company_id)

    if tipo:
        query = query.filter(CompanyDocument.tipo == tipo)

    documents = query.order_by(CompanyDocument.created_at.desc()).all()

    return documents


@router.post("/{company_id}/documents", response_model=CompanyDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_company_document(
    company_id: UUID,
    file: UploadFile = File(...),
    tipo: str = Form(..., description="Tipo de documento"),
    descripcion: Optional[str] = Form(None),
    fecha_emision: Optional[str] = Form(None),
    fecha_vencimiento: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sube un documento a una empresa.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar acceso
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta empresa"
            )

    # Validar tipo de archivo
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx', '.xls', '.xlsx'}
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de archivo no permitido. Extensiones validas: {', '.join(allowed_extensions)}"
        )

    # Validar tamano (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo excede el limite de 10MB"
        )

    # Crear directorio de la empresa
    ensure_upload_dir()
    company_dir = os.path.join(UPLOAD_DIR, str(company_id))
    os.makedirs(company_dir, exist_ok=True)

    # Generar nombre unico
    unique_filename = f"{uuid_lib.uuid4()}{file_ext}"
    file_path = os.path.join(company_dir, unique_filename)

    # Guardar archivo
    with open(file_path, "wb") as f:
        f.write(content)

    # Parsear fechas
    fecha_emision_parsed = None
    fecha_vencimiento_parsed = None
    if fecha_emision:
        try:
            fecha_emision_parsed = datetime.strptime(fecha_emision, "%Y-%m-%d").date()
        except ValueError:
            pass
    if fecha_vencimiento:
        try:
            fecha_vencimiento_parsed = datetime.strptime(fecha_vencimiento, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Crear registro en BD
    document = CompanyDocument(
        empresa_id=company_id,
        tipo=tipo,
        nombre_archivo=unique_filename,
        nombre_original=file.filename,
        extension=file_ext,
        mime_type=file.content_type or "application/octet-stream",
        tamano_bytes=len(content),
        ruta_archivo=file_path,
        descripcion=descripcion,
        fecha_emision=fecha_emision_parsed,
        fecha_vencimiento=fecha_vencimiento_parsed,
        estado="pendiente"
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


@router.get("/{company_id}/documents/{document_id}", response_model=CompanyDocumentResponse)
async def get_company_document(
    company_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene detalle de un documento.
    """
    document = db.query(CompanyDocument).filter(
        CompanyDocument.id == document_id,
        CompanyDocument.empresa_id == company_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    company = db.query(Company).filter(Company.id == company_id).first()

    # Verificar acceso
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este documento"
            )

    return document


@router.put("/{company_id}/documents/{document_id}", response_model=CompanyDocumentResponse)
async def update_company_document(
    company_id: UUID,
    document_id: UUID,
    document_data: CompanyDocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualiza metadata de un documento.
    """
    document = db.query(CompanyDocument).filter(
        CompanyDocument.id == document_id,
        CompanyDocument.empresa_id == company_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    company = db.query(Company).filter(Company.id == company_id).first()

    # Solo Admin/Analista pueden cambiar estado de revision
    if document_data.estado and current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo Admin y Analista pueden cambiar el estado de revision"
        )

    # Verificar acceso para otros campos
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este documento"
            )

    # Actualizar campos
    update_data = document_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(document, field, value)

    # Si se actualiza estado, registrar quien lo reviso
    if document_data.estado:
        document.revisado_por = current_user.id
        document.fecha_revision = datetime.utcnow()

    document.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(document)

    return document


@router.delete("/{company_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_document(
    company_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Elimina un documento de la empresa.
    """
    document = db.query(CompanyDocument).filter(
        CompanyDocument.id == document_id,
        CompanyDocument.empresa_id == company_id
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado"
        )

    company = db.query(Company).filter(Company.id == company_id).first()

    # Verificar acceso
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este documento"
            )

    # Eliminar archivo fisico
    try:
        if os.path.exists(document.ruta_archivo):
            os.remove(document.ruta_archivo)
    except Exception:
        pass

    # Eliminar registro
    db.delete(document)
    db.commit()


# ============================================================
# ENDPOINTS DE PROYECTOS ASOCIADOS
# ============================================================

@router.get("/{company_id}/projects")
async def list_company_projects(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista proyectos asociados a una empresa.
    """
    company = db.query(Company).filter(Company.id == company_id).first()

    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Empresa no encontrada"
        )

    # Verificar acceso
    if current_user.rol not in [UserRole.ADMIN, UserRole.ANALISTA]:
        if company.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a esta empresa"
            )

    projects = db.query(Project).filter(Project.empresa_id == company_id).all()

    return {
        "empresa_id": str(company_id),
        "razon_social": company.razon_social,
        "total_proyectos": len(projects),
        "proyectos": [
            {
                "id": str(p.id),
                "nombre": p.nombre,
                "sector": p.sector.value if hasattr(p.sector, 'value') else str(p.sector),
                "monto_solicitado": float(p.monto_solicitado),
                "estado": p.estado.value if hasattr(p.estado, 'value') else str(p.estado),
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in projects
        ]
    }


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _company_to_response(company: Company, db: Session) -> CompanyResponse:
    """Convierte modelo Company a CompanyResponse."""
    # Contar documentos y proyectos
    total_documentos = db.query(CompanyDocument).filter(
        CompanyDocument.empresa_id == company.id
    ).count()
    total_proyectos = db.query(Project).filter(
        Project.empresa_id == company.id
    ).count()

    return CompanyResponse(
        id=company.id,
        razon_social=company.razon_social,
        nombre_comercial=company.nombre_comercial,
        tipo_empresa=company.tipo_empresa.value if hasattr(company.tipo_empresa, 'value') else str(company.tipo_empresa),
        rfc=company.rfc,
        curp=company.curp,
        regimen_fiscal=company.regimen_fiscal,
        actividad_economica=company.actividad_economica,
        clave_actividad_sat=company.clave_actividad_sat,
        fecha_constitucion=company.fecha_constitucion,
        numero_escritura=company.numero_escritura,
        notaria=company.notaria,
        fecha_inscripcion_rpc=company.fecha_inscripcion_rpc,
        calle=company.calle,
        numero_exterior=company.numero_exterior,
        numero_interior=company.numero_interior,
        colonia=company.colonia,
        codigo_postal=company.codigo_postal,
        municipio=company.municipio,
        estado=company.estado,
        pais=company.pais or "Mexico",
        direccion_completa=company.direccion_completa,
        telefono_principal=company.telefono_principal,
        telefono_secundario=company.telefono_secundario,
        email_corporativo=company.email_corporativo,
        sitio_web=company.sitio_web,
        representante_nombre=company.representante_nombre,
        representante_cargo=company.representante_cargo,
        representante_email=company.representante_email,
        representante_telefono=company.representante_telefono,
        representante_rfc=company.representante_rfc,
        representante_curp=company.representante_curp,
        tamano_empresa=company.tamano_empresa.value if hasattr(company.tamano_empresa, 'value') and company.tamano_empresa else None,
        numero_empleados=company.numero_empleados,
        ingresos_anuales=company.ingresos_anuales,
        capital_social=company.capital_social,
        antiguedad_anos=company.antiguedad_anos,
        sector=company.sector,
        industria=company.industria,
        giro=company.giro,
        banco=company.banco,
        cuenta_clabe=company.cuenta_clabe,
        cuenta_numero=company.cuenta_numero,
        estado_verificacion=company.estado_verificacion.value if hasattr(company.estado_verificacion, 'value') else str(company.estado_verificacion),
        fecha_verificacion=company.fecha_verificacion,
        verificado_por=company.verificado_por,
        notas_verificacion=company.notas_verificacion,
        score_riesgo=company.score_riesgo,
        datos_adicionales=company.datos_adicionales,
        user_id=company.user_id,
        created_at=company.created_at,
        updated_at=company.updated_at,
        total_documentos=total_documentos,
        total_proyectos=total_proyectos
    )


def _company_to_response_with_documents(company: Company, db: Session) -> CompanyWithDocuments:
    """Convierte modelo Company a CompanyWithDocuments."""
    base_response = _company_to_response(company, db)

    # Obtener documentos
    documents = db.query(CompanyDocument).filter(
        CompanyDocument.empresa_id == company.id
    ).order_by(CompanyDocument.created_at.desc()).all()

    return CompanyWithDocuments(
        **base_response.model_dump(),
        documentos=[CompanyDocumentResponse.model_validate(doc) for doc in documents]
    )
