"""
Endpoints del Portal del Inversionista.
Dashboard, Portfolio, KPIs.
"""
from datetime import datetime
from decimal import Decimal
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.project import Project, ProjectStatus
from app.models.investment import Investment, InvestmentStatus, InvestmentTransaction
from app.models.audit import AuditLog, AuditAction
from app.schemas.investment import (
    InvestmentCreate, InvestmentResponse, InvestmentDetailResponse,
    PortfolioResponse, PortfolioKPIs, DistribucionSector, ProximoPago
)

router = APIRouter(prefix="/investor", tags=["Portal Inversionista"])


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: User = Depends(require_role([UserRole.INVERSIONISTA, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Obtiene el portfolio completo del inversionista.
    Incluye KPIs, distribucion y proximos pagos.
    """
    # Obtener inversiones del usuario
    inversiones = db.query(Investment).filter(
        Investment.inversionista_id == current_user.id
    ).all()

    # Calcular KPIs
    total_invertido = sum(i.monto_invertido for i in inversiones) or Decimal("0")
    rendimiento_total = sum(i.monto_rendimiento_acumulado for i in inversiones) or Decimal("0")

    rendimiento_porcentual = Decimal("0")
    if total_invertido > 0:
        rendimiento_porcentual = (rendimiento_total / total_invertido).quantize(Decimal("0.0001"))

    # Contar proyectos por estado
    activos = sum(1 for i in inversiones if i.estado in [
        InvestmentStatus.ACTIVA, InvestmentStatus.EN_RENDIMIENTO
    ])
    completados = sum(1 for i in inversiones if i.estado == InvestmentStatus.LIQUIDADA)

    # Calcular proyectos en default: contar inversiones en proyectos con estado DEFAULT
    proyecto_ids = [i.proyecto_id for i in inversiones]
    proyectos_default = db.query(Project.id).filter(
        Project.id.in_(proyecto_ids),
        Project.estado == ProjectStatus.DEFAULT
    ).all()
    defaults = len(proyectos_default)

    # MOIC (Multiple on Invested Capital)
    moic = Decimal("1.0")
    if total_invertido > 0:
        total_recibido = sum(i.monto_total_recibido for i in inversiones) or Decimal("0")
        moic = ((total_recibido + total_invertido) / total_invertido).quantize(Decimal("0.01"))

    # Calcular TIR ponderada de la cartera
    # TIR simplificada basada en rendimiento anualizado ponderado
    tir_cartera = None
    if total_invertido > 0 and inversiones:
        tir_sum = Decimal("0")
        for inv in inversiones:
            if inv.monto_invertido and inv.monto_invertido > 0:
                # Calcular tiempo en años desde la inversión
                tiempo_dias = (datetime.utcnow() - inv.fecha_inversion).days if inv.fecha_inversion else 365
                tiempo_anios = max(Decimal(str(tiempo_dias)) / Decimal("365"), Decimal("0.1"))

                # Rendimiento de esta inversión
                rend = inv.monto_rendimiento_acumulado or Decimal("0")
                tir_inv = (rend / inv.monto_invertido) / tiempo_anios

                # Ponderar por monto invertido
                peso = inv.monto_invertido / total_invertido
                tir_sum += tir_inv * peso

        tir_cartera = tir_sum.quantize(Decimal("0.0001"))

    kpis = PortfolioKPIs(
        total_invertido=total_invertido,
        rendimiento_total=rendimiento_total,
        rendimiento_porcentual=rendimiento_porcentual,
        tir_cartera=tir_cartera,
        moic=moic,
        proyectos_activos=activos,
        proyectos_completados=completados,
        proyectos_en_default=defaults
    )

    # Distribucion por sector
    distribucion = []
    sectores = {}
    for inv in inversiones:
        proyecto = db.query(Project).filter(Project.id == inv.proyecto_id).first()
        if proyecto:
            sector = proyecto.sector or "Otro"
            if sector not in sectores:
                sectores[sector] = {"monto": Decimal("0"), "cantidad": 0}
            sectores[sector]["monto"] += inv.monto_invertido
            sectores[sector]["cantidad"] += 1

    for sector, datos in sectores.items():
        porcentaje = Decimal("0")
        if total_invertido > 0:
            porcentaje = (datos["monto"] / total_invertido).quantize(Decimal("0.01"))
        distribucion.append(DistribucionSector(
            sector=sector,
            monto=datos["monto"],
            porcentaje=porcentaje,
            cantidad_proyectos=datos["cantidad"]
        ))

    # Inversiones response
    inversiones_response = []
    for inv in inversiones:
        proyecto = db.query(Project).filter(Project.id == inv.proyecto_id).first()
        inversiones_response.append(InvestmentResponse(
            id=inv.id,
            proyecto_id=inv.proyecto_id,
            proyecto_nombre=proyecto.nombre if proyecto else None,
            monto_invertido=inv.monto_invertido,
            monto_rendimiento_acumulado=inv.monto_rendimiento_acumulado,
            monto_total_recibido=inv.monto_total_recibido,
            porcentaje_participacion=inv.porcentaje_participacion,
            estado=inv.estado.value,
            fecha_inversion=inv.fecha_inversion,
            fecha_vencimiento=inv.fecha_vencimiento
        ))

    # Proximos pagos (simplificado)
    proximos_pagos = []

    # Calcular rendimiento histórico (últimos 12 meses)
    rendimiento_historico = []
    if inversiones:
        from datetime import timedelta
        from calendar import monthrange

        # Obtener todas las transacciones de rendimiento del usuario
        inversion_ids = [i.id for i in inversiones]
        transacciones = db.query(
            func.date_trunc('month', InvestmentTransaction.fecha).label('mes'),
            func.sum(InvestmentTransaction.monto).label('total')
        ).filter(
            InvestmentTransaction.inversion_id.in_(inversion_ids),
            InvestmentTransaction.tipo == "Rendimiento",
            InvestmentTransaction.fecha >= datetime.utcnow() - timedelta(days=365)
        ).group_by(
            func.date_trunc('month', InvestmentTransaction.fecha)
        ).order_by('mes').all()

        for tx in transacciones:
            if tx.mes and tx.total:
                rendimiento_historico.append({
                    "mes": tx.mes.strftime("%Y-%m"),
                    "rendimiento": float(tx.total)
                })

    return PortfolioResponse(
        kpis=kpis,
        distribucion_sectores=distribucion,
        inversiones=inversiones_response,
        proximos_pagos=proximos_pagos,
        rendimiento_historico=rendimiento_historico
    )


@router.post("/invest", response_model=InvestmentResponse, status_code=status.HTTP_201_CREATED)
async def create_investment(
    investment_data: InvestmentCreate,
    current_user: User = Depends(require_role([UserRole.INVERSIONISTA, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Crea una nueva inversion en un proyecto.
    Requiere que el proyecto este en estado Aprobado o Financiando.
    """
    # Verificar proyecto
    proyecto = db.query(Project).filter(Project.id == investment_data.proyecto_id).first()

    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    if proyecto.estado not in [ProjectStatus.APROBADO, ProjectStatus.FINANCIANDO]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El proyecto no esta disponible para inversion"
        )

    # Verificar monto minimo
    if investment_data.monto < proyecto.monto_minimo_inversion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto minimo de inversion: {proyecto.monto_minimo_inversion}"
        )

    # Verificar que no exceda el monto faltante
    monto_faltante = proyecto.monto_solicitado - proyecto.monto_financiado
    if investment_data.monto > monto_faltante:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monto excede lo disponible. Maximo: {monto_faltante}"
        )

    # Calcular porcentaje de participacion
    porcentaje = (investment_data.monto / proyecto.monto_solicitado).quantize(Decimal("0.0001"))

    # Crear inversion
    inversion = Investment(
        inversionista_id=current_user.id,
        proyecto_id=proyecto.id,
        monto_invertido=investment_data.monto,
        porcentaje_participacion=porcentaje,
        estado=InvestmentStatus.PENDIENTE,
        metodo_pago=investment_data.metodo_pago
    )

    db.add(inversion)

    # Actualizar monto financiado del proyecto
    proyecto.monto_financiado += investment_data.monto
    if proyecto.monto_financiado >= proyecto.monto_solicitado:
        proyecto.estado = ProjectStatus.FINANCIADO

    db.commit()
    db.refresh(inversion)

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.INVESTMENT_CREATED,
        resource_type="Investment",
        resource_id=inversion.id,
        new_values={
            "proyecto_id": str(proyecto.id),
            "monto": float(investment_data.monto)
        }
    )
    db.add(audit)
    db.commit()

    return InvestmentResponse(
        id=inversion.id,
        proyecto_id=inversion.proyecto_id,
        proyecto_nombre=proyecto.nombre,
        monto_invertido=inversion.monto_invertido,
        monto_rendimiento_acumulado=inversion.monto_rendimiento_acumulado,
        monto_total_recibido=inversion.monto_total_recibido,
        porcentaje_participacion=inversion.porcentaje_participacion,
        estado=inversion.estado.value,
        fecha_inversion=inversion.fecha_inversion,
        fecha_vencimiento=inversion.fecha_vencimiento
    )


@router.get("/investments", response_model=List[InvestmentResponse])
async def list_investments(
    current_user: User = Depends(require_role([UserRole.INVERSIONISTA, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Lista todas las inversiones del usuario."""
    inversiones = db.query(Investment).filter(
        Investment.inversionista_id == current_user.id
    ).all()

    result = []
    for inv in inversiones:
        proyecto = db.query(Project).filter(Project.id == inv.proyecto_id).first()
        result.append(InvestmentResponse(
            id=inv.id,
            proyecto_id=inv.proyecto_id,
            proyecto_nombre=proyecto.nombre if proyecto else None,
            monto_invertido=inv.monto_invertido,
            monto_rendimiento_acumulado=inv.monto_rendimiento_acumulado,
            monto_total_recibido=inv.monto_total_recibido,
            porcentaje_participacion=inv.porcentaje_participacion,
            estado=inv.estado.value,
            fecha_inversion=inv.fecha_inversion,
            fecha_vencimiento=inv.fecha_vencimiento
        ))

    return result


@router.get("/investments/{investment_id}", response_model=InvestmentDetailResponse)
async def get_investment_detail(
    investment_id: UUID,
    current_user: User = Depends(require_role([UserRole.INVERSIONISTA, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Obtiene detalle de una inversion con transacciones."""
    inversion = db.query(Investment).filter(
        Investment.id == investment_id,
        Investment.inversionista_id == current_user.id
    ).first()

    if not inversion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inversion no encontrada"
        )

    proyecto = db.query(Project).filter(Project.id == inversion.proyecto_id).first()

    transacciones = db.query(InvestmentTransaction).filter(
        InvestmentTransaction.inversion_id == inversion.id
    ).order_by(InvestmentTransaction.fecha_transaccion.desc()).all()

    rendimiento_porcentual = Decimal("0")
    if inversion.monto_invertido > 0:
        rendimiento_porcentual = (
            inversion.monto_rendimiento_acumulado / inversion.monto_invertido
        ).quantize(Decimal("0.0001"))

    return InvestmentDetailResponse(
        inversion=InvestmentResponse(
            id=inversion.id,
            proyecto_id=inversion.proyecto_id,
            proyecto_nombre=proyecto.nombre if proyecto else None,
            monto_invertido=inversion.monto_invertido,
            monto_rendimiento_acumulado=inversion.monto_rendimiento_acumulado,
            monto_total_recibido=inversion.monto_total_recibido,
            porcentaje_participacion=inversion.porcentaje_participacion,
            estado=inversion.estado.value,
            fecha_inversion=inversion.fecha_inversion,
            fecha_vencimiento=inversion.fecha_vencimiento
        ),
        proyecto={
            "id": str(proyecto.id) if proyecto else None,
            "nombre": proyecto.nombre if proyecto else None,
            "sector": proyecto.sector if proyecto else None,
            "estado": proyecto.estado.value if proyecto else None
        },
        transacciones=[
            {
                "id": str(t.id),
                "tipo": t.tipo.value,
                "monto": float(t.monto),
                "concepto": t.concepto,
                "fecha_transaccion": t.fecha_transaccion.isoformat()
            }
            for t in transacciones
        ],
        rendimiento_porcentual=rendimiento_porcentual
    )
