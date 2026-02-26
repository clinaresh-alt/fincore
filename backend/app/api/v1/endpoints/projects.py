"""
Endpoints de Proyectos y Evaluacion Financiera.
Motor de calculo de VAN, TIR, Credit Scoring.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user, get_current_user_optional, require_role
from app.models.user import User, UserRole
from app.models.project import (
    Project, ProjectStatus, FinancialEvaluation,
    RiskAnalysis, CashFlow, RiskLevel, SectorIndicators
)
from app.models.audit import AuditLog, AuditAction
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectEvaluate,
    EvaluationResponse, RiskAnalysisResponse, ProjectAnalyticsResponse,
    SectorIndicatorsCreate, SectorIndicatorsUpdate, SectorIndicatorsResponse
)
from app.services.financial_engine import FinancialEngine
from app.services.risk_engine import RiskEngine
from app.services.feasibility_analyzer import FeasibilityAnalyzer

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
    request: Request,
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    sector: Optional[str] = Query(None, description="Filtrar por sector"),
    skip: int = 0,
    limit: int = 50,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Lista proyectos disponibles.
    - Usuarios no autenticados: solo proyectos aprobados/financiando (publicos)
    - Inversionistas: solo proyectos aprobados/financiando
    - Admin/Analista: todos los proyectos
    """
    query = db.query(Project)

    # Filtro por rol (si no autenticado, trata como inversionista)
    if not current_user or current_user.rol == UserRole.INVERSIONISTA:
        query = query.filter(
            Project.estado.in_([
                ProjectStatus.APROBADO,
                ProjectStatus.FINANCIANDO,
                ProjectStatus.FINANCIADO
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


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ANALISTA])),
    db: Session = Depends(get_db)
):
    """
    Actualiza un proyecto existente.
    Solo Admin y Analista pueden editar proyectos.
    """
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Solo actualizar campos que fueron enviados (no None)
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:
            setattr(project, field, value)

    db.commit()
    db.refresh(project)

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_MODIFIED,
        resource_type="Project",
        resource_id=project.id,
        description=f"Proyecto actualizado: {project.nombre}",
        new_values=update_data
    )
    db.add(audit)
    db.commit()

    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Elimina un proyecto.
    Solo Admin puede eliminar proyectos.
    """
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Verificar que no tenga inversiones activas
    from app.models.investment import Investment
    investments = db.query(Investment).filter(Investment.proyecto_id == project_id).count()
    if investments > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar: el proyecto tiene {investments} inversiones asociadas"
        )

    project_name = project.nombre

    # Eliminar evaluaciones y flujos de caja relacionados
    db.query(FinancialEvaluation).filter(FinancialEvaluation.proyecto_id == project_id).delete()
    db.query(RiskAnalysis).filter(RiskAnalysis.proyecto_id == project_id).delete()
    db.query(CashFlow).filter(CashFlow.proyecto_id == project_id).delete()

    # Eliminar proyecto
    db.delete(project)
    db.commit()

    # Audit
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_DELETED,
        resource_type="Project",
        resource_id=project_id,
        description=f"Proyecto eliminado: {project_name}"
    )
    db.add(audit)
    db.commit()


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


@router.post("/analyze-feasibility")
async def analyze_feasibility_study(
    file: UploadFile = File(..., description="Archivo PDF del estudio de factibilidad"),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Analiza un estudio de factibilidad PDF con IA.
    Extrae automaticamente:
    - Datos basicos del proyecto
    - Configuracion financiera
    - Flujos de caja proyectados
    - Indicadores pre-calculados
    """
    # Validar tipo de archivo
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF"
        )

    # Validar tamano (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo excede el limite de 10MB"
        )

    try:
        analyzer = FeasibilityAnalyzer(db_session=db)

        # Verificar si hay API key configurada
        if not analyzer.client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key de Anthropic no configurada. Ve a Administracion > Configuracion del Sistema para configurarla."
            )

        extracted_data = await analyzer.analyze_pdf(content)

        # Obtener indicadores relevantes segun sector
        indicators = FeasibilityAnalyzer.get_indicators_for_project_type(extracted_data.sector)

        return {
            "success": True,
            "extracted_data": {
                "basic": {
                    "nombre": extracted_data.nombre,
                    "descripcion": extracted_data.descripcion,
                    "sector": extracted_data.sector,
                    "ubicacion": extracted_data.ubicacion,
                    "empresa_solicitante": extracted_data.empresa_solicitante
                },
                "financial_config": {
                    "inversion_inicial": float(extracted_data.inversion_inicial),
                    "tasa_descuento": float(extracted_data.tasa_descuento),
                    "plazo_meses": extracted_data.plazo_meses,
                    "tasa_rendimiento_esperado": float(extracted_data.tasa_rendimiento_esperado),
                    "tipo_periodo": extracted_data.tipo_periodo
                },
                "cash_flows": [
                    {
                        "periodo": f["periodo"],
                        "ingresos": float(f["ingresos"]),
                        "costos": float(f["costos"]),
                        "descripcion": f["descripcion"]
                    }
                    for f in extracted_data.flujos_caja
                ],
                "document_indicators": {
                    "van": float(extracted_data.van_documento) if extracted_data.van_documento else None,
                    "tir": float(extracted_data.tir_documento) if extracted_data.tir_documento else None,
                    "payback": extracted_data.payback_documento
                },
                "additional_data": extracted_data.datos_adicionales
            },
            "recommended_indicators": indicators,
            "all_indicators": FeasibilityAnalyzer.get_all_extended_indicators(),
            "extraction_confidence": extracted_data.confianza_extraccion,
            "extraction_notes": extracted_data.notas_extraccion
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analizando documento: {str(e)}"
        )


@router.get("/indicators/{sector}")
async def get_indicators_by_sector(
    sector: str,
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    Obtiene los indicadores financieros relevantes para un sector especifico.
    """
    indicators = FeasibilityAnalyzer.get_indicators_for_project_type(sector)
    all_indicators = FeasibilityAnalyzer.get_all_extended_indicators()

    return {
        "sector": sector,
        "indicators": [
            {"key": ind, "name": all_indicators.get(ind, ind)}
            for ind in indicators
        ],
        "all_available": all_indicators
    }


@router.get("/evaluations/list")
async def list_projects_with_evaluations(
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    sector: Optional[str] = Query(None, description="Filtrar por sector"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Lista proyectos con sus evaluaciones financieras completas.
    Incluye indicadores basicos y sectoriales.
    Para la pagina de evaluaciones.
    """
    query = db.query(Project)

    # Filtros opcionales
    if estado:
        query = query.filter(Project.estado == estado)
    if sector:
        query = query.filter(Project.sector == sector)

    total = query.count()
    projects = query.offset(skip).limit(limit).all()

    result = []
    for project in projects:
        # Obtener evaluacion financiera
        evaluation = db.query(FinancialEvaluation).filter(
            FinancialEvaluation.proyecto_id == project.id
        ).first()

        # Obtener analisis de riesgo
        risk = db.query(RiskAnalysis).filter(
            RiskAnalysis.proyecto_id == project.id
        ).first()

        # Obtener flujos de caja
        cash_flows = db.query(CashFlow).filter(
            CashFlow.proyecto_id == project.id
        ).order_by(CashFlow.periodo_nro).all()

        # Construir respuesta
        project_data = {
            "id": str(project.id),
            "nombre": project.nombre,
            "descripcion": project.descripcion,
            "sector": project.sector.value if hasattr(project.sector, 'value') else str(project.sector),
            "empresa_solicitante": project.empresa_solicitante,
            "monto_solicitado": float(project.monto_solicitado),
            "monto_financiado": float(project.monto_financiado or 0),
            "plazo_meses": project.plazo_meses,
            "tasa_rendimiento_anual": float(project.tasa_rendimiento_anual) if project.tasa_rendimiento_anual else None,
            "estado": project.estado.value if hasattr(project.estado, 'value') else str(project.estado),
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "tiene_evaluacion": evaluation is not None,
            "tiene_analisis_riesgo": risk is not None,
        }

        # Indicadores financieros basicos
        if evaluation:
            project_data["evaluacion"] = {
                "inversion_inicial": float(evaluation.inversion_inicial) if evaluation.inversion_inicial else None,
                "tasa_descuento": float(evaluation.tasa_descuento_aplicada) if evaluation.tasa_descuento_aplicada else None,
                "van": float(evaluation.van) if evaluation.van else None,
                "tir": float(evaluation.tir) if evaluation.tir else None,
                "roi": float(evaluation.roi) if evaluation.roi else None,
                "payback_period": float(evaluation.payback_period) if evaluation.payback_period else None,
                "indice_rentabilidad": float(evaluation.indice_rentabilidad) if evaluation.indice_rentabilidad else None,
                "van_optimista": float(evaluation.van_optimista) if evaluation.van_optimista else None,
                "van_pesimista": float(evaluation.van_pesimista) if evaluation.van_pesimista else None,
                "tir_optimista": float(evaluation.tir_optimista) if evaluation.tir_optimista else None,
                "tir_pesimista": float(evaluation.tir_pesimista) if evaluation.tir_pesimista else None,
                "fecha_evaluacion": evaluation.fecha_evaluacion.isoformat() if evaluation.fecha_evaluacion else None,
                "es_viable": (evaluation.van or 0) > 0,
            }
        else:
            project_data["evaluacion"] = None

        # Analisis de riesgo
        if risk:
            project_data["riesgo"] = {
                "score_crediticio": risk.score_crediticio,
                "nivel_riesgo": risk.nivel_riesgo.value if risk.nivel_riesgo else None,
                "probabilidad_default": float(risk.probabilidad_default) if risk.probabilidad_default else None,
                "probabilidad_exito": float(risk.probabilidad_exito) if risk.probabilidad_exito else None,
                "score_capacidad_pago": risk.score_capacidad_pago,
                "score_historial": risk.score_historial,
                "score_garantias": risk.score_garantias,
                "ratio_deuda_ingreso": float(risk.ratio_deuda_ingreso) if risk.ratio_deuda_ingreso else None,
                "loan_to_value": float(risk.loan_to_value) if risk.loan_to_value else None,
                "valor_garantias": float(risk.valor_garantias) if risk.valor_garantias else None,
            }
        else:
            project_data["riesgo"] = None

        # Flujos de caja
        if cash_flows:
            project_data["flujos_caja"] = [
                {
                    "periodo": cf.periodo_nro,
                    "ingresos": float(cf.monto_ingreso or 0),
                    "egresos": float(cf.monto_egreso or 0),
                    "flujo_neto": float(cf.flujo_neto),
                    "descripcion": cf.descripcion,
                }
                for cf in cash_flows
            ]
        else:
            project_data["flujos_caja"] = []

        # Indicadores sectoriales recomendados
        sector_str = project.sector.value.lower() if hasattr(project.sector, 'value') else str(project.sector).lower()
        project_data["indicadores_sectoriales"] = FeasibilityAnalyzer.get_indicators_for_project_type(sector_str)

        result.append(project_data)

    # Estadisticas generales
    all_projects = db.query(Project).all()
    stats = {
        "total": len(all_projects),
        "pendientes": len([p for p in all_projects if p.estado == ProjectStatus.EN_EVALUACION]),
        "aprobados": len([p for p in all_projects if p.estado == ProjectStatus.APROBADO]),
        "rechazados": len([p for p in all_projects if p.estado == ProjectStatus.RECHAZADO]),
        "financiando": len([p for p in all_projects if p.estado == ProjectStatus.FINANCIANDO]),
        "por_sector": {},
    }

    # Agrupar por sector
    for p in all_projects:
        sector_name = p.sector.value if hasattr(p.sector, 'value') else str(p.sector)
        if sector_name not in stats["por_sector"]:
            stats["por_sector"][sector_name] = 0
        stats["por_sector"][sector_name] += 1

    return {
        "projects": result,
        "total": total,
        "skip": skip,
        "limit": limit,
        "stats": stats,
        "all_indicators": FeasibilityAnalyzer.get_all_extended_indicators()
    }


# ===== ENDPOINTS INDICADORES DEL SECTOR =====

@router.get("/{project_id}/indicators", response_model=SectorIndicatorsResponse)
async def get_project_indicators(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtiene los indicadores del sector para un proyecto.
    """
    # Verificar que el proyecto existe
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Buscar indicadores
    indicators = db.query(SectorIndicators).filter(
        SectorIndicators.proyecto_id == project_id
    ).first()

    if not indicators:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay indicadores registrados para este proyecto"
        )

    return indicators


@router.post("/{project_id}/indicators", response_model=SectorIndicatorsResponse)
async def create_or_update_indicators(
    project_id: UUID,
    indicators_data: SectorIndicatorsUpdate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ANALISTA, UserRole.CLIENTE])),
    db: Session = Depends(get_db)
):
    """
    Crea o actualiza los indicadores del sector para un proyecto.
    """
    # Verificar que el proyecto existe
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Buscar indicadores existentes
    indicators = db.query(SectorIndicators).filter(
        SectorIndicators.proyecto_id == project_id
    ).first()

    if indicators:
        # Actualizar existentes
        update_data = indicators_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(indicators, key, value)
        indicators.updated_at = datetime.utcnow()
    else:
        # Crear nuevos
        indicators = SectorIndicators(
            proyecto_id=project_id,
            **indicators_data.model_dump(exclude_unset=True)
        )
        db.add(indicators)

    db.commit()
    db.refresh(indicators)

    # Registrar en auditoria
    audit = AuditLog(
        usuario_id=current_user.id,
        accion=AuditAction.PROJECT_MODIFIED,
        recurso_tipo="SectorIndicators",
        recurso_id=str(indicators.id),
        datos_nuevos={"proyecto_id": str(project_id)}
    )
    db.add(audit)
    db.commit()

    return indicators


@router.put("/{project_id}/indicators", response_model=SectorIndicatorsResponse)
async def update_indicators(
    project_id: UUID,
    indicators_data: SectorIndicatorsUpdate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.ANALISTA, UserRole.CLIENTE])),
    db: Session = Depends(get_db)
):
    """
    Actualiza los indicadores del sector para un proyecto.
    Solo actualiza los campos proporcionados.
    """
    # Verificar que el proyecto existe
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proyecto no encontrado"
        )

    # Buscar indicadores existentes
    indicators = db.query(SectorIndicators).filter(
        SectorIndicators.proyecto_id == project_id
    ).first()

    if not indicators:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay indicadores registrados para este proyecto. Use POST para crear."
        )

    # Actualizar solo campos proporcionados
    update_data = indicators_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(indicators, key, value)
    indicators.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(indicators)

    return indicators


@router.delete("/{project_id}/indicators", status_code=status.HTTP_204_NO_CONTENT)
async def delete_indicators(
    project_id: UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Elimina los indicadores del sector para un proyecto.
    Solo Admin puede eliminar.
    """
    indicators = db.query(SectorIndicators).filter(
        SectorIndicators.proyecto_id == project_id
    ).first()

    if not indicators:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay indicadores registrados para este proyecto"
        )

    db.delete(indicators)
    db.commit()

    return None
