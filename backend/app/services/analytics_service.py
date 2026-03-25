"""
Servicio de Analytics para FinCore.

Proporciona metricas, KPIs y datos agregados para dashboards.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
import random


class TimeRange(Enum):
    """Rangos de tiempo para analytics."""
    DAY = "1d"
    WEEK = "7d"
    MONTH = "30d"
    QUARTER = "90d"
    YEAR = "365d"
    ALL = "all"


class MetricTrend(Enum):
    """Tendencia de una metrica."""
    UP = "up"
    DOWN = "down"
    STABLE = "stable"


@dataclass
class MetricValue:
    """Valor de una metrica con metadata."""
    value: Decimal
    previous_value: Optional[Decimal] = None
    change_percent: Optional[Decimal] = None
    trend: MetricTrend = MetricTrend.STABLE
    formatted: str = ""

    def __post_init__(self):
        if self.previous_value and self.previous_value != 0:
            self.change_percent = ((self.value - self.previous_value) / self.previous_value) * 100
            if self.change_percent > Decimal("1"):
                self.trend = MetricTrend.UP
            elif self.change_percent < Decimal("-1"):
                self.trend = MetricTrend.DOWN


@dataclass
class TimeSeriesPoint:
    """Punto en una serie de tiempo."""
    timestamp: datetime
    value: Decimal
    label: str = ""


@dataclass
class ChartData:
    """Datos para graficos."""
    labels: list[str]
    datasets: list[dict]
    total: Optional[Decimal] = None


@dataclass
class PlatformMetrics:
    """Metricas generales de la plataforma."""
    total_invested: MetricValue
    total_investors: MetricValue
    active_projects: MetricValue
    pending_dividends: MetricValue
    avg_roi: MetricValue
    total_transactions: MetricValue


@dataclass
class ProjectMetrics:
    """Metricas de proyectos."""
    total_projects: int
    by_status: dict[str, int]
    by_sector: dict[str, int]
    funding_progress: list[dict]
    top_performers: list[dict]


@dataclass
class InvestorMetrics:
    """Metricas de inversionistas."""
    total_investors: int
    new_this_month: int
    by_tier: dict[str, int]
    by_country: dict[str, int]
    avg_investment: Decimal
    retention_rate: Decimal


@dataclass
class TransactionMetrics:
    """Metricas de transacciones."""
    total_volume: Decimal
    total_count: int
    by_type: dict[str, int]
    by_network: dict[str, int]
    avg_gas_cost: Decimal
    success_rate: Decimal


class AnalyticsService:
    """
    Servicio principal de analytics.

    Proporciona metricas agregadas, series de tiempo
    y datos para visualizaciones.
    """

    def __init__(self):
        """Inicializa el servicio."""
        self._cache: dict = {}
        self._cache_ttl = timedelta(minutes=5)

    def get_platform_overview(self, time_range: TimeRange = TimeRange.MONTH) -> PlatformMetrics:
        """
        Obtiene metricas generales de la plataforma.

        Args:
            time_range: Rango de tiempo para calcular cambios

        Returns:
            PlatformMetrics con todas las metricas principales
        """
        # En produccion, estos datos vendrian de la DB
        # Por ahora, generamos datos de ejemplo realistas

        total_invested = MetricValue(
            value=Decimal("45750000.00"),
            previous_value=Decimal("42300000.00"),
            formatted="$45.75M MXN"
        )

        total_investors = MetricValue(
            value=Decimal("1247"),
            previous_value=Decimal("1180"),
            formatted="1,247"
        )

        active_projects = MetricValue(
            value=Decimal("12"),
            previous_value=Decimal("10"),
            formatted="12"
        )

        pending_dividends = MetricValue(
            value=Decimal("2340000.00"),
            previous_value=Decimal("1890000.00"),
            formatted="$2.34M MXN"
        )

        avg_roi = MetricValue(
            value=Decimal("14.5"),
            previous_value=Decimal("13.8"),
            formatted="14.5%"
        )

        total_transactions = MetricValue(
            value=Decimal("3456"),
            previous_value=Decimal("3120"),
            formatted="3,456"
        )

        return PlatformMetrics(
            total_invested=total_invested,
            total_investors=total_investors,
            active_projects=active_projects,
            pending_dividends=pending_dividends,
            avg_roi=avg_roi,
            total_transactions=total_transactions,
        )

    def get_investment_timeline(
        self,
        time_range: TimeRange = TimeRange.MONTH,
        granularity: str = "day"
    ) -> list[dict]:
        """
        Obtiene serie de tiempo de inversiones.

        Args:
            time_range: Rango de tiempo
            granularity: Granularidad (hour, day, week, month)

        Returns:
            Lista de puntos con fecha y monto
        """
        days = self._get_days_for_range(time_range)
        data = []
        base_date = datetime.utcnow()

        # Generar datos simulados con tendencia alcista
        base_value = 500000
        for i in range(days, 0, -1):
            date = base_date - timedelta(days=i)
            # Agregar variacion realista
            variation = random.uniform(0.8, 1.3)
            trend_factor = 1 + (days - i) * 0.002  # Tendencia alcista suave
            value = base_value * variation * trend_factor

            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "label": date.strftime("%d %b"),
                "investments": round(value, 2),
                "dividends": round(value * 0.12, 2),
            })

        return data

    def get_investments_by_sector(self) -> list[dict]:
        """
        Obtiene distribucion de inversiones por sector.

        Returns:
            Lista con sector, monto y porcentaje
        """
        sectors = [
            {"sector": "Energias Renovables", "amount": 15500000, "color": "#22c55e"},
            {"sector": "Tecnologia", "amount": 12300000, "color": "#3b82f6"},
            {"sector": "Bienes Raices", "amount": 8750000, "color": "#f59e0b"},
            {"sector": "Agroindustria", "amount": 5200000, "color": "#84cc16"},
            {"sector": "Infraestructura", "amount": 4000000, "color": "#6366f1"},
        ]

        total = sum(s["amount"] for s in sectors)

        for sector in sectors:
            sector["percentage"] = round((sector["amount"] / total) * 100, 1)
            sector["formatted"] = f"${sector['amount']/1000000:.2f}M"

        return sectors

    def get_project_performance(self, limit: int = 10) -> list[dict]:
        """
        Obtiene rendimiento de proyectos.

        Args:
            limit: Numero maximo de proyectos

        Returns:
            Lista de proyectos con metricas de rendimiento
        """
        projects = [
            {
                "id": "proj-001",
                "name": "Solar Chihuahua I",
                "sector": "Energias Renovables",
                "invested": 8500000,
                "roi": 16.5,
                "status": "active",
                "progress": 78,
            },
            {
                "id": "proj-002",
                "name": "Fintech Gateway",
                "sector": "Tecnologia",
                "invested": 5200000,
                "roi": 22.3,
                "status": "active",
                "progress": 92,
            },
            {
                "id": "proj-003",
                "name": "Torre Reforma 500",
                "sector": "Bienes Raices",
                "invested": 12000000,
                "roi": 11.8,
                "status": "active",
                "progress": 45,
            },
            {
                "id": "proj-004",
                "name": "Agave Premium",
                "sector": "Agroindustria",
                "invested": 3800000,
                "roi": 18.2,
                "status": "active",
                "progress": 65,
            },
            {
                "id": "proj-005",
                "name": "Data Center MX",
                "sector": "Tecnologia",
                "invested": 7100000,
                "roi": 14.7,
                "status": "funding",
                "progress": 35,
            },
        ]

        return sorted(projects, key=lambda x: x["roi"], reverse=True)[:limit]

    def get_investor_distribution(self) -> dict:
        """
        Obtiene distribucion de inversionistas.

        Returns:
            Diccionario con diferentes distribuciones
        """
        return {
            "by_tier": [
                {"tier": "Bronce", "count": 650, "min_investment": 10000, "color": "#cd7f32"},
                {"tier": "Plata", "count": 380, "min_investment": 100000, "color": "#c0c0c0"},
                {"tier": "Oro", "count": 165, "min_investment": 500000, "color": "#ffd700"},
                {"tier": "Platino", "count": 52, "min_investment": 2000000, "color": "#e5e4e2"},
            ],
            "by_country": [
                {"country": "Mexico", "code": "MX", "count": 980, "percentage": 78.6},
                {"country": "Estados Unidos", "code": "US", "count": 156, "percentage": 12.5},
                {"country": "Espana", "code": "ES", "count": 65, "percentage": 5.2},
                {"country": "Otros", "code": "XX", "count": 46, "percentage": 3.7},
            ],
            "by_age_group": [
                {"group": "25-34", "count": 312, "percentage": 25},
                {"group": "35-44", "count": 436, "percentage": 35},
                {"group": "45-54", "count": 324, "percentage": 26},
                {"group": "55+", "count": 175, "percentage": 14},
            ],
        }

    def get_transaction_stats(self, time_range: TimeRange = TimeRange.MONTH) -> dict:
        """
        Obtiene estadisticas de transacciones.

        Args:
            time_range: Rango de tiempo

        Returns:
            Estadisticas de transacciones
        """
        return {
            "summary": {
                "total_volume": 45750000,
                "total_count": 3456,
                "avg_value": 13238,
                "success_rate": 99.2,
            },
            "by_type": [
                {"type": "investment", "count": 1523, "volume": 32500000, "color": "#22c55e"},
                {"type": "dividend", "count": 1245, "volume": 8900000, "color": "#3b82f6"},
                {"type": "withdrawal", "count": 456, "volume": 3200000, "color": "#f59e0b"},
                {"type": "fee", "count": 232, "volume": 1150000, "color": "#6b7280"},
            ],
            "by_network": [
                {"network": "Polygon", "count": 2890, "percentage": 83.6, "color": "#8247e5"},
                {"network": "Ethereum", "count": 456, "percentage": 13.2, "color": "#627eea"},
                {"network": "Arbitrum", "count": 110, "percentage": 3.2, "color": "#28a0f0"},
            ],
            "hourly_distribution": self._get_hourly_distribution(),
        }

    def get_security_metrics(self) -> dict:
        """
        Obtiene metricas de seguridad.

        Returns:
            Metricas de seguridad y auditoria
        """
        return {
            "audits": {
                "total": 45,
                "passed": 42,
                "failed": 3,
                "avg_score": 87.5,
            },
            "alerts": {
                "total": 156,
                "critical": 2,
                "high": 8,
                "medium": 45,
                "low": 101,
            },
            "incidents": {
                "total": 5,
                "resolved": 4,
                "active": 1,
                "mttr_hours": 2.3,
            },
            "compliance": {
                "kyc_verified": 1189,
                "kyc_pending": 58,
                "aml_flags": 3,
                "score": 95.4,
            },
        }

    def get_revenue_metrics(self, time_range: TimeRange = TimeRange.MONTH) -> dict:
        """
        Obtiene metricas de ingresos de la plataforma.

        Args:
            time_range: Rango de tiempo

        Returns:
            Metricas de ingresos
        """
        return {
            "total_revenue": 4575000,
            "management_fees": 2287500,
            "performance_fees": 1830000,
            "transaction_fees": 457500,
            "monthly_trend": self._get_monthly_revenue_trend(),
            "revenue_by_project": [
                {"project": "Solar Chihuahua I", "revenue": 1250000},
                {"project": "Fintech Gateway", "revenue": 980000},
                {"project": "Torre Reforma 500", "revenue": 875000},
                {"project": "Agave Premium", "revenue": 720000},
                {"project": "Data Center MX", "revenue": 750000},
            ],
        }

    def get_kpi_summary(self) -> dict:
        """
        Obtiene resumen de KPIs principales.

        Returns:
            KPIs con valores actuales y objetivos
        """
        return {
            "aum": {  # Assets Under Management
                "current": 45750000,
                "target": 50000000,
                "progress": 91.5,
                "trend": "up",
            },
            "investor_growth": {
                "current": 1247,
                "target": 1500,
                "progress": 83.1,
                "trend": "up",
            },
            "avg_ticket": {
                "current": 36680,
                "target": 40000,
                "progress": 91.7,
                "trend": "stable",
            },
            "nps": {  # Net Promoter Score
                "current": 72,
                "target": 80,
                "progress": 90,
                "trend": "up",
            },
            "default_rate": {
                "current": 0.8,
                "target": 2.0,
                "progress": 100,  # Bajo es mejor
                "trend": "down",
            },
        }

    def _get_days_for_range(self, time_range: TimeRange) -> int:
        """Convierte TimeRange a numero de dias."""
        mapping = {
            TimeRange.DAY: 1,
            TimeRange.WEEK: 7,
            TimeRange.MONTH: 30,
            TimeRange.QUARTER: 90,
            TimeRange.YEAR: 365,
            TimeRange.ALL: 730,
        }
        return mapping.get(time_range, 30)

    def _get_hourly_distribution(self) -> list[dict]:
        """Genera distribucion horaria de transacciones."""
        hours = []
        for h in range(24):
            # Simular patron realista (mas actividad en horario laboral)
            if 9 <= h <= 18:
                base = 150
            elif 6 <= h <= 8 or 19 <= h <= 22:
                base = 80
            else:
                base = 30

            hours.append({
                "hour": h,
                "label": f"{h:02d}:00",
                "count": base + random.randint(-20, 20),
            })

        return hours

    def _get_monthly_revenue_trend(self) -> list[dict]:
        """Genera tendencia de ingresos mensuales."""
        months = []
        base_date = datetime.utcnow()

        for i in range(12, 0, -1):
            date = base_date - timedelta(days=i * 30)
            base_revenue = 350000 + (12 - i) * 20000  # Tendencia creciente
            variation = random.uniform(0.9, 1.1)

            months.append({
                "month": date.strftime("%b %Y"),
                "revenue": round(base_revenue * variation),
                "management": round(base_revenue * variation * 0.5),
                "performance": round(base_revenue * variation * 0.4),
                "transaction": round(base_revenue * variation * 0.1),
            })

        return months
