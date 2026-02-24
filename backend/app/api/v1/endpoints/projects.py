"""
Endpoints de Proyectos y Evaluacion Financiera.
Motor de calculo de VAN, TIR, Credit Scoring.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.project import (
    Project, ProjectStatus, FinancialEvaluation,
    RiskAnalysis, CashFlow, RiskLevel
)
from app.models.audit import AuditLog, AuditAction
from app.schemas.project import (
    ProjectCreate, ProjectResponse, ProjectEvaluate,
    EvaluationResponse, RiskAnalysisResponse, ProjectAnalyticsResponse
)
from app.services.financial_engine import FinancialEngine
from app.services.risk_engine import RiskEngine

router = APIRouter(prefix="/projects", tags=["Proyectos"])


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo proyecto de inversion.
    Requiere rol de Cliente o Admin.
    """
    project = Project(
        nombre=project_data.nombre,
        descripcion=project_data.descripcion,
        sector=project_data.sector,
        monto_solicitado=project_data.monto_solicitado,
        plazo_meses=project_data.plazo_meses,
        tasa_rendimiento_anual=project_data.tasa_rendimiento_anual,
        empresa_solicitante=project_data.empresa_solicitante,
        solicitante_id=current_user.id,
        estado=ProjectStatus.EN_EVALUACION
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_CREATED,
        resource_type="Project",
        resource_id=project.id,
        description=f"Proyecto creado: {project.nombre}"
    )
    db.add(audit)
    db.commit()

    return project


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    sector: Optional[str] = Query(None, description="Filtrar por sector"),
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lista proyectos disponibles.
    Inversionistas ven solo proyectos aprobados/financiando.
    """
    query = db.query(Project)

    # Filtro por rol
    if current_user.rol == UserRole.INVERSIONISTA:
        query = query.filter(
            Project.estado.in_([
                ProjectStatus.APROBADO,
                ProjectStatus.FINANCIANDO
            ])
        )

    # Filtros opcionales
    if estado:
        query = query.filter(Project.estado == estado)
    if sector:
        query = query.filter(Project.sector == sector)

    return query.offset(skip).limit(limit).all()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene detalle de un proyecto."""
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    return project


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_project(
    eval_data: ProjectEvaluate,
    current_user: User = Depends(require_role([UserRole.ANALISTA, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Evalua financieramente un proyecto.
    Calcula VAN, TIR, ROI, Payback.
    Solo Analistas y Admins.
    """
    # Verificar proyecto existe
    project = db.query(Project).filter(Project.id == eval_data.proyecto_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Preparar flujos de caja
    flujos = [
        Decimal(str(f.monto_ingreso - f.monto_egreso))
        for f in eval_data.flujos_caja
    ]

    # Ejecutar motor financiero
    resultado = FinancialEngine.evaluar_proyecto(
        inversion_inicial=eval_data.inversion_inicial,
        flujos_caja=flujos,
        tasa_descuento=eval_data.tasa_descuento
    )

    # Analisis de sensibilidad
    sensibilidad = FinancialEngine.analisis_sensibilidad(
        inversion_inicial=eval_data.inversion_inicial,
        flujos_caja_base=flujos,
        tasa_descuento=eval_data.tasa_descuento
    )

    # Guardar evaluacion en BD
    existing_eval = db.query(FinancialEvaluation).filter(
        FinancialEvaluation.proyecto_id == project.id
    ).first()

    if existing_eval:
        # Actualizar existente
        existing_eval.inversion_inicial = eval_data.inversion_inicial
        existing_eval.tasa_descuento_aplicada = eval_data.tasa_descuento
        existing_eval.van = resultado.van
        existing_eval.tir = resultado.tir
        existing_eval.roi = resultado.roi
        existing_eval.payback_period = resultado.payback_period
        existing_eval.indice_rentabilidad = resultado.indice_rentabilidad
        existing_eval.van_pesimista = sensibilidad[0].van
        existing_eval.van_optimista = sensibilidad[2].van
        existing_eval.evaluado_por = current_user.id
        existing_eval.fecha_evaluacion = datetime.utcnow()
    else:
        # Crear nueva
        evaluation = FinancialEvaluation(
            proyecto_id=project.id,
            inversion_inicial=eval_data.inversion_inicial,
            tasa_descuento_aplicada=eval_data.tasa_descuento,
            van=resultado.van,
            tir=resultado.tir,
            roi=resultado.roi,
            payback_period=resultado.payback_period,
            indice_rentabilidad=resultado.indice_rentabilidad,
            van_pesimista=sensibilidad[0].van,
            van_optimista=sensibilidad[2].van,
            evaluado_por=current_user.id
        )
        db.add(evaluation)

    # Guardar flujos de caja
    db.query(CashFlow).filter(CashFlow.proyecto_id == project.id).delete()
    for f in eval_data.flujos_caja:
        cash_flow = CashFlow(
            proyecto_id=project.id,
            periodo_nro=f.periodo_nro,
            monto_ingreso=f.monto_ingreso,
            monto_egreso=f.monto_egreso,
            descripcion=f.descripcion
        )
        db.add(cash_flow)

    db.commit()

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_EVALUATED,
        resource_type="Project",
        resource_id=project.id,
        new_values={
            "van": float(resultado.van),
            "tir": float(resultado.tir) if resultado.tir else None,
            "es_viable": resultado.es_viable
        }
    )
    db.add(audit)
    db.commit()

    return EvaluationResponse(
        proyecto_id=project.id,
        inversion_inicial=eval_data.inversion_inicial,
        tasa_descuento=eval_data.tasa_descuento,
        van=resultado.van,
        tir=resultado.tir,
        roi=resultado.roi,
        payback_period=resultado.payback_period,
        indice_rentabilidad=resultado.indice_rentabilidad,
        escenarios=[
            {
                "escenario": s.escenario,
                "van": float(s.van),
                "tir": float(s.tir) if s.tir else None,
                "es_viable": s.es_viable
            }
            for s in sensibilidad
        ],
        es_viable=resultado.es_viable,
        mensaje=resultado.mensaje,
        fecha_evaluacion=datetime.utcnow()
    )


@router.post("/{project_id}/risk-analysis", response_model=RiskAnalysisResponse)
async def analyze_risk(
    project_id: UUID,
    eval_data: ProjectEvaluate,
    current_user: User = Depends(require_role([UserRole.ANALISTA, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Analiza riesgo crediticio del proyecto.
    Calcula Credit Score y probabilidad de default.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Valores por defecto si no se proporcionan
    ingresos = eval_data.ingresos_mensuales_solicitante or Decimal("100000")
    gastos = eval_data.gastos_fijos_solicitante or Decimal("30000")
    deuda = eval_data.deuda_actual_solicitante or Decimal("0")
    tasa = project.tasa_rendimiento_anual or Decimal("0.12")

    # Ejecutar motor de riesgos
    resultado = RiskEngine.analizar_riesgo_completo(
        ingresos_mensuales=ingresos,
        gastos_fijos=gastos,
        deuda_actual=deuda,
        monto_solicitado=project.monto_solicitado,
        plazo_meses=project.plazo_meses,
        tasa_interes_propuesta=tasa,
        meses_actividad=eval_data.meses_actividad or 24,
        pagos_puntuales=eval_data.pagos_puntuales or 12,
        pagos_atrasados=eval_data.pagos_atrasados or 0,
        defaults_previos=0,
        valor_garantias=eval_data.valor_garantias or Decimal("0"),
        tipo_garantia=eval_data.tipo_garantia or "ninguna"
    )

    # Guardar analisis
    existing_risk = db.query(RiskAnalysis).filter(
        RiskAnalysis.proyecto_id == project.id
    ).first()

    risk_data = {
        "score_crediticio": resultado.score.score_total,
        "nivel_riesgo": resultado.score.nivel_riesgo,
        "score_capacidad_pago": resultado.score.score_capacidad_pago,
        "score_historial": resultado.score.score_historial,
        "score_garantias": resultado.score.score_garantias,
        "probabilidad_default": resultado.probabilidad_default,
        "probabilidad_exito": resultado.probabilidad_exito,
        "ratio_deuda_ingreso": resultado.ratio_deuda_ingreso,
        "loan_to_value": resultado.loan_to_value,
        "garantias_ofrecidas": eval_data.tipo_garantia,
        "valor_garantias": eval_data.valor_garantias
    }

    if existing_risk:
        for key, value in risk_data.items():
            setattr(existing_risk, key, value)
    else:
        risk_analysis = RiskAnalysis(proyecto_id=project.id, **risk_data)
        db.add(risk_analysis)

    db.commit()

    return RiskAnalysisResponse(
        proyecto_id=project.id,
        score_total=resultado.score.score_total,
        score_capacidad_pago=resultado.score.score_capacidad_pago,
        score_historial=resultado.score.score_historial,
        score_garantias=resultado.score.score_garantias,
        nivel_riesgo=resultado.score.nivel_riesgo.value,
        accion_recomendada=resultado.score.accion.value,
        probabilidad_default=resultado.probabilidad_default,
        probabilidad_exito=resultado.probabilidad_exito,
        ratio_deuda_ingreso=resultado.ratio_deuda_ingreso,
        loan_to_value=resultado.loan_to_value,
        tasa_interes_sugerida=resultado.tasa_interes_sugerida,
        monto_maximo_aprobado=resultado.monto_maximo_aprobado,
        requiere_garantias_adicionales=resultado.requiere_garantias_adicionales,
        observaciones=resultado.observaciones
    )


@router.post("/{project_id}/approve")
async def approve_project(
    project_id: UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """Aprueba un proyecto para financiamiento."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    project.estado = ProjectStatus.APROBADO
    db.commit()

    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_APPROVED,
        resource_type="Project",
        resource_id=project.id
    )
    db.add(audit)
    db.commit()

    return {"message": "Proyecto aprobado", "estado": project.estado.value}


@router.post("/evaluate-complete")
async def evaluate_project_complete(
    eval_data: ProjectEvaluate,
    include_montecarlo: bool = Query(True, description="Incluir simulacion Monte Carlo"),
    current_user: User = Depends(require_role([UserRole.ANALISTA, UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Evaluacion financiera completa con analisis avanzado.
    Incluye: VAN, TIR, Sensibilidad, Tornado, Monte Carlo, Matriz Cruzada.
    """
    # Verificar proyecto
    project = db.query(Project).filter(Project.id == eval_data.proyecto_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Separar ingresos y costos
    flujos_ingresos = [Decimal(str(f.monto_ingreso)) for f in eval_data.flujos_caja]
    flujos_costos = [Decimal(str(f.monto_egreso)) for f in eval_data.flujos_caja]

    # Ejecutar evaluacion completa
    resultado = FinancialEngine.evaluacion_completa(
        inversion_inicial=eval_data.inversion_inicial,
        flujos_ingresos=flujos_ingresos,
        flujos_costos=flujos_costos,
        tasa_descuento=eval_data.tasa_descuento,
        incluir_montecarlo=include_montecarlo
    )

    # Guardar evaluacion
    existing_eval = db.query(FinancialEvaluation).filter(
        FinancialEvaluation.proyecto_id == project.id
    ).first()

    eval_data_db = {
        "inversion_inicial": eval_data.inversion_inicial,
        "tasa_descuento_aplicada": eval_data.tasa_descuento,
        "van": Decimal(str(resultado["evaluacion"]["van"])),
        "tir": Decimal(str(resultado["evaluacion"]["tir"])) if resultado["evaluacion"]["tir"] else None,
        "roi": Decimal(str(resultado["evaluacion"]["roi"])),
        "payback_period": Decimal(str(resultado["evaluacion"]["payback_period"])) if resultado["evaluacion"]["payback_period"] else None,
        "indice_rentabilidad": Decimal(str(resultado["evaluacion"]["indice_rentabilidad"])),
        "evaluado_por": current_user.id,
        "fecha_evaluacion": datetime.utcnow()
    }

    if existing_eval:
        for key, value in eval_data_db.items():
            setattr(existing_eval, key, value)
    else:
        evaluation = FinancialEvaluation(proyecto_id=project.id, **eval_data_db)
        db.add(evaluation)

    # Guardar flujos
    db.query(CashFlow).filter(CashFlow.proyecto_id == project.id).delete()
    for f in eval_data.flujos_caja:
        cf = CashFlow(
            proyecto_id=project.id,
            periodo_nro=f.periodo_nro,
            monto_ingreso=f.monto_ingreso,
            monto_egreso=f.monto_egreso,
            descripcion=f.descripcion
        )
        db.add(cf)

    db.commit()

    return resultado


@router.post("/sensitivity")
async def analyze_sensitivity(
    eval_data: ProjectEvaluate,
    variable: str = Query(..., description="Variable a estresar: ingresos, costos, tasa_descuento"),
    variacion: float = Query(0.10, description="Porcentaje de variacion"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analisis de sensibilidad en tiempo real.
    Para el slider del dashboard.
    """
    flujos_ingresos = [Decimal(str(f.monto_ingreso)) for f in eval_data.flujos_caja]
    flujos_costos = [Decimal(str(f.monto_egreso)) for f in eval_data.flujos_caja]

    # Generar rango de variaciones
    variaciones = [-variacion * 2, -variacion, 0, variacion, variacion * 2]

    resultado = FinancialEngine.analisis_sensibilidad_variable(
        inversion_inicial=eval_data.inversion_inicial,
        flujos_ingresos=flujos_ingresos,
        flujos_costos=flujos_costos,
        tasa_descuento=eval_data.tasa_descuento,
        variable=variable,
        variaciones=variaciones
    )

    return {
        "variable": variable,
        "variaciones": variaciones,
        "resultados": resultado
    }


@router.post("/tornado")
async def generate_tornado_data(
    eval_data: ProjectEvaluate,
    variacion: float = Query(0.10, description="Porcentaje de variacion"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Genera datos para grafico tornado.
    Muestra impacto de cada variable en el VAN.
    """
    flujos_ingresos = [Decimal(str(f.monto_ingreso)) for f in eval_data.flujos_caja]
    flujos_costos = [Decimal(str(f.monto_egreso)) for f in eval_data.flujos_caja]

    resultado = FinancialEngine.grafico_tornado_data(
        inversion_inicial=eval_data.inversion_inicial,
        flujos_ingresos=flujos_ingresos,
        flujos_costos=flujos_costos,
        tasa_descuento=eval_data.tasa_descuento,
        variacion=variacion
    )

    return {"tornado": resultado}


@router.post("/matriz-sensibilidad")
async def generate_sensitivity_matrix(
    eval_data: ProjectEvaluate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Genera matriz cruzada de sensibilidad.
    Tabla de doble entrada (ingresos vs tasa).
    """
    flujos_ingresos = [Decimal(str(f.monto_ingreso)) for f in eval_data.flujos_caja]
    flujos_costos = [Decimal(str(f.monto_egreso)) for f in eval_data.flujos_caja]

    resultado = FinancialEngine.matriz_sensibilidad_cruzada(
        inversion_inicial=eval_data.inversion_inicial,
        flujos_ingresos=flujos_ingresos,
        flujos_costos=flujos_costos,
        tasa_descuento=eval_data.tasa_descuento
    )

    return resultado


@router.post("/montecarlo")
async def run_montecarlo_simulation(
    eval_data: ProjectEvaluate,
    n_simulaciones: int = Query(500, ge=100, le=5000),
    volatilidad_ingresos: float = Query(0.15, ge=0, le=0.5),
    volatilidad_costos: float = Query(0.10, ge=0, le=0.5),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Ejecuta simulacion Monte Carlo.
    Distribucion de probabilidad del VAN.
    """
    flujos_ingresos = [Decimal(str(f.monto_ingreso)) for f in eval_data.flujos_caja]
    flujos_costos = [Decimal(str(f.monto_egreso)) for f in eval_data.flujos_caja]

    resultado = FinancialEngine.simulacion_montecarlo(
        inversion_inicial=eval_data.inversion_inicial,
        flujos_ingresos=flujos_ingresos,
        flujos_costos=flujos_costos,
        tasa_descuento=eval_data.tasa_descuento,
        n_simulaciones=n_simulaciones,
        volatilidad_ingresos=volatilidad_ingresos,
        volatilidad_costos=volatilidad_costos
    )

    return resultado


@router.get("/{project_id}/analytics", response_model=ProjectAnalyticsResponse)
async def get_project_analytics(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene analiticas completas del proyecto.
    Para el portal del inversionista.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")

    # Obtener evaluacion
    evaluation = db.query(FinancialEvaluation).filter(
        FinancialEvaluation.proyecto_id == project.id
    ).first()

    # Obtener riesgo
    risk = db.query(RiskAnalysis).filter(
        RiskAnalysis.proyecto_id == project.id
    ).first()

    # Obtener flujos
    cash_flows = db.query(CashFlow).filter(
        CashFlow.proyecto_id == project.id
    ).order_by(CashFlow.periodo_nro).all()

    # Contar inversionistas
    from app.models.investment import Investment
    total_investors = db.query(Investment).filter(
        Investment.proyecto_id == project.id
    ).count()

    financials = {}
    if evaluation:
        financials = {
            "van": float(evaluation.van) if evaluation.van else 0,
            "tir": float(evaluation.tir) if evaluation.tir else None,
            "roi": float(evaluation.roi) if evaluation.roi else 0,
            "risk_level": risk.nivel_riesgo.value if risk else "Sin evaluar"
        }

    cash_flow_series = [
        {
            "period": f"Periodo {cf.periodo_nro}",
            "amount": float(cf.flujo_neto)
        }
        for cf in cash_flows
    ]

    porcentaje = (
        (project.monto_financiado / project.monto_solicitado * 100)
        if project.monto_solicitado > 0 else Decimal("0")
    )

    return ProjectAnalyticsResponse(
        project_id=project.id,
        nombre=project.nombre,
        estado=project.estado.value,
        financials=financials,
        cash_flow_series=cash_flow_series,
        monto_solicitado=project.monto_solicitado,
        monto_financiado=project.monto_financiado,
        porcentaje_financiado=porcentaje,
        total_inversionistas=total_investors
    )
