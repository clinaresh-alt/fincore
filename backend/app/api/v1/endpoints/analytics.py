"""
API Endpoints para Analytics y Dashboard.

Expone metricas, KPIs y datos para visualizaciones.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.analytics_service import AnalyticsService, TimeRange


router = APIRouter()

# Instancia del servicio
_analytics_service: Optional[AnalyticsService] = None


def get_analytics_service() -> AnalyticsService:
    """Obtiene instancia del servicio de analytics."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service


# ============ Schemas ============


class MetricResponse(BaseModel):
    """Respuesta de metrica individual."""
    value: float
    previous_value: Optional[float] = None
    change_percent: Optional[float] = None
    trend: str = "stable"
    formatted: str = ""


class PlatformOverviewResponse(BaseModel):
    """Respuesta del overview de plataforma."""
    total_invested: MetricResponse
    total_investors: MetricResponse
    active_projects: MetricResponse
    pending_dividends: MetricResponse
    avg_roi: MetricResponse
    total_transactions: MetricResponse


class TimeSeriesDataResponse(BaseModel):
    """Respuesta de serie de tiempo."""
    data: list[dict]
    period: str
    granularity: str


# ============ Endpoints ============


@router.get("/overview")
async def get_platform_overview(
    time_range: str = Query(default="30d", regex="^(1d|7d|30d|90d|365d|all)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene metricas generales de la plataforma.

    Incluye: inversiones totales, inversionistas, proyectos activos,
    dividendos pendientes, ROI promedio y transacciones.
    """
    analytics = get_analytics_service()
    tr = TimeRange(time_range)
    metrics = analytics.get_platform_overview(tr)

    return {
        "total_invested": {
            "value": float(metrics.total_invested.value),
            "previous_value": float(metrics.total_invested.previous_value) if metrics.total_invested.previous_value else None,
            "change_percent": float(metrics.total_invested.change_percent) if metrics.total_invested.change_percent else None,
            "trend": metrics.total_invested.trend.value,
            "formatted": metrics.total_invested.formatted,
        },
        "total_investors": {
            "value": float(metrics.total_investors.value),
            "previous_value": float(metrics.total_investors.previous_value) if metrics.total_investors.previous_value else None,
            "change_percent": float(metrics.total_investors.change_percent) if metrics.total_investors.change_percent else None,
            "trend": metrics.total_investors.trend.value,
            "formatted": metrics.total_investors.formatted,
        },
        "active_projects": {
            "value": float(metrics.active_projects.value),
            "previous_value": float(metrics.active_projects.previous_value) if metrics.active_projects.previous_value else None,
            "change_percent": float(metrics.active_projects.change_percent) if metrics.active_projects.change_percent else None,
            "trend": metrics.active_projects.trend.value,
            "formatted": metrics.active_projects.formatted,
        },
        "pending_dividends": {
            "value": float(metrics.pending_dividends.value),
            "previous_value": float(metrics.pending_dividends.previous_value) if metrics.pending_dividends.previous_value else None,
            "change_percent": float(metrics.pending_dividends.change_percent) if metrics.pending_dividends.change_percent else None,
            "trend": metrics.pending_dividends.trend.value,
            "formatted": metrics.pending_dividends.formatted,
        },
        "avg_roi": {
            "value": float(metrics.avg_roi.value),
            "previous_value": float(metrics.avg_roi.previous_value) if metrics.avg_roi.previous_value else None,
            "change_percent": float(metrics.avg_roi.change_percent) if metrics.avg_roi.change_percent else None,
            "trend": metrics.avg_roi.trend.value,
            "formatted": metrics.avg_roi.formatted,
        },
        "total_transactions": {
            "value": float(metrics.total_transactions.value),
            "previous_value": float(metrics.total_transactions.previous_value) if metrics.total_transactions.previous_value else None,
            "change_percent": float(metrics.total_transactions.change_percent) if metrics.total_transactions.change_percent else None,
            "trend": metrics.total_transactions.trend.value,
            "formatted": metrics.total_transactions.formatted,
        },
    }


@router.get("/investments/timeline")
async def get_investment_timeline(
    time_range: str = Query(default="30d", regex="^(1d|7d|30d|90d|365d|all)$"),
    granularity: str = Query(default="day", regex="^(hour|day|week|month)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene serie de tiempo de inversiones.

    Usado para graficos de linea/area mostrando tendencia de inversiones.
    """
    analytics = get_analytics_service()
    tr = TimeRange(time_range)
    data = analytics.get_investment_timeline(tr, granularity)

    return {
        "data": data,
        "period": time_range,
        "granularity": granularity,
    }


@router.get("/investments/by-sector")
async def get_investments_by_sector(
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene distribucion de inversiones por sector.

    Usado para graficos de pie/donut.
    """
    analytics = get_analytics_service()
    return {
        "sectors": analytics.get_investments_by_sector(),
    }


@router.get("/projects/performance")
async def get_project_performance(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene rendimiento de proyectos.

    Lista proyectos ordenados por ROI con metricas de progreso.
    """
    analytics = get_analytics_service()
    return {
        "projects": analytics.get_project_performance(limit),
    }


@router.get("/investors/distribution")
async def get_investor_distribution(
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene distribucion de inversionistas.

    Incluye distribuciones por tier, pais y grupo de edad.
    """
    analytics = get_analytics_service()
    return analytics.get_investor_distribution()


@router.get("/transactions/stats")
async def get_transaction_stats(
    time_range: str = Query(default="30d", regex="^(1d|7d|30d|90d|365d|all)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene estadisticas de transacciones.

    Incluye volumenes, conteos y distribuciones.
    """
    analytics = get_analytics_service()
    tr = TimeRange(time_range)
    return analytics.get_transaction_stats(tr)


@router.get("/security")
async def get_security_metrics(
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene metricas de seguridad.

    Incluye auditorias, alertas, incidentes y compliance.
    """
    analytics = get_analytics_service()
    return analytics.get_security_metrics()


@router.get("/revenue")
async def get_revenue_metrics(
    time_range: str = Query(default="30d", regex="^(1d|7d|30d|90d|365d|all)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene metricas de ingresos de la plataforma.

    Solo accesible para administradores.
    """
    # TODO: Verificar rol Admin
    analytics = get_analytics_service()
    tr = TimeRange(time_range)
    return analytics.get_revenue_metrics(tr)


@router.get("/kpis")
async def get_kpi_summary(
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene resumen de KPIs principales.

    Incluye valores actuales, objetivos y progreso.
    """
    analytics = get_analytics_service()
    return analytics.get_kpi_summary()


@router.get("/dashboard")
async def get_dashboard_data(
    time_range: str = Query(default="30d", regex="^(1d|7d|30d|90d|365d|all)$"),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene todos los datos del dashboard en una sola llamada.

    Optimizado para cargar el dashboard completo.
    """
    analytics = get_analytics_service()
    tr = TimeRange(time_range)

    # Obtener todas las metricas necesarias
    overview = analytics.get_platform_overview(tr)
    timeline = analytics.get_investment_timeline(tr)
    sectors = analytics.get_investments_by_sector()
    projects = analytics.get_project_performance(5)
    investors = analytics.get_investor_distribution()
    transactions = analytics.get_transaction_stats(tr)
    kpis = analytics.get_kpi_summary()

    return {
        "overview": {
            "total_invested": {
                "value": float(overview.total_invested.value),
                "change_percent": float(overview.total_invested.change_percent) if overview.total_invested.change_percent else None,
                "trend": overview.total_invested.trend.value,
                "formatted": overview.total_invested.formatted,
            },
            "total_investors": {
                "value": float(overview.total_investors.value),
                "change_percent": float(overview.total_investors.change_percent) if overview.total_investors.change_percent else None,
                "trend": overview.total_investors.trend.value,
                "formatted": overview.total_investors.formatted,
            },
            "active_projects": {
                "value": float(overview.active_projects.value),
                "change_percent": float(overview.active_projects.change_percent) if overview.active_projects.change_percent else None,
                "trend": overview.active_projects.trend.value,
                "formatted": overview.active_projects.formatted,
            },
            "avg_roi": {
                "value": float(overview.avg_roi.value),
                "change_percent": float(overview.avg_roi.change_percent) if overview.avg_roi.change_percent else None,
                "trend": overview.avg_roi.trend.value,
                "formatted": overview.avg_roi.formatted,
            },
        },
        "timeline": timeline,
        "sectors": sectors,
        "top_projects": projects,
        "investors": investors,
        "transactions": transactions,
        "kpis": kpis,
        "time_range": time_range,
    }
