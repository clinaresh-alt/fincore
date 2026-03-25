"""
Tests para AnalyticsService.

Cobertura de metricas, KPIs y datos de dashboard.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from app.services.analytics_service import (
    AnalyticsService,
    TimeRange,
    MetricTrend,
    MetricValue,
    TimeSeriesPoint,
    ChartData,
    PlatformMetrics,
)


class TestTimeRange:
    """Tests para enum TimeRange."""

    def test_time_range_values(self):
        """Verifica valores del enum TimeRange."""
        assert TimeRange.DAY.value == "1d"
        assert TimeRange.WEEK.value == "7d"
        assert TimeRange.MONTH.value == "30d"
        assert TimeRange.QUARTER.value == "90d"
        assert TimeRange.YEAR.value == "365d"
        assert TimeRange.ALL.value == "all"

    def test_time_range_from_string(self):
        """Verifica creacion desde string."""
        assert TimeRange("1d") == TimeRange.DAY
        assert TimeRange("30d") == TimeRange.MONTH


class TestMetricTrend:
    """Tests para enum MetricTrend."""

    def test_metric_trend_values(self):
        """Verifica valores del enum MetricTrend."""
        assert MetricTrend.UP.value == "up"
        assert MetricTrend.DOWN.value == "down"
        assert MetricTrend.STABLE.value == "stable"


class TestMetricValue:
    """Tests para dataclass MetricValue."""

    def test_metric_value_basic(self):
        """Test creacion basica de MetricValue."""
        metric = MetricValue(
            value=Decimal("100.00"),
            formatted="$100.00"
        )
        assert metric.value == Decimal("100.00")
        assert metric.formatted == "$100.00"
        assert metric.trend == MetricTrend.STABLE
        assert metric.previous_value is None
        assert metric.change_percent is None

    def test_metric_value_with_increase(self):
        """Test MetricValue con incremento."""
        metric = MetricValue(
            value=Decimal("120.00"),
            previous_value=Decimal("100.00"),
            formatted="$120.00"
        )
        assert metric.change_percent == Decimal("20")
        assert metric.trend == MetricTrend.UP

    def test_metric_value_with_decrease(self):
        """Test MetricValue con decremento."""
        metric = MetricValue(
            value=Decimal("80.00"),
            previous_value=Decimal("100.00"),
            formatted="$80.00"
        )
        assert metric.change_percent == Decimal("-20")
        assert metric.trend == MetricTrend.DOWN

    def test_metric_value_stable(self):
        """Test MetricValue estable (cambio < 1%)."""
        metric = MetricValue(
            value=Decimal("100.50"),
            previous_value=Decimal("100.00"),
            formatted="$100.50"
        )
        assert metric.trend == MetricTrend.STABLE

    def test_metric_value_zero_previous(self):
        """Test MetricValue con valor previo cero."""
        metric = MetricValue(
            value=Decimal("100.00"),
            previous_value=Decimal("0"),
            formatted="$100.00"
        )
        # Con previous_value=0, no se calcula change_percent
        assert metric.change_percent is None


class TestTimeSeriesPoint:
    """Tests para dataclass TimeSeriesPoint."""

    def test_time_series_point(self):
        """Test creacion de TimeSeriesPoint."""
        now = datetime.utcnow()
        point = TimeSeriesPoint(
            timestamp=now,
            value=Decimal("1000.00"),
            label="Jan 1"
        )
        assert point.timestamp == now
        assert point.value == Decimal("1000.00")
        assert point.label == "Jan 1"


class TestChartData:
    """Tests para dataclass ChartData."""

    def test_chart_data_basic(self):
        """Test creacion de ChartData."""
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[{"data": [100, 200, 300]}],
            total=Decimal("600")
        )
        assert len(chart.labels) == 3
        assert len(chart.datasets) == 1
        assert chart.total == Decimal("600")


class TestAnalyticsService:
    """Tests para AnalyticsService."""

    @pytest.fixture
    def analytics_service(self):
        """Crea instancia del servicio."""
        return AnalyticsService()

    def test_init(self, analytics_service):
        """Test inicializacion del servicio."""
        assert analytics_service._cache == {}
        assert analytics_service._cache_ttl == timedelta(minutes=5)

    def test_get_platform_overview(self, analytics_service):
        """Test obtener metricas de plataforma."""
        metrics = analytics_service.get_platform_overview()

        assert isinstance(metrics, PlatformMetrics)
        assert metrics.total_invested.value > 0
        assert metrics.total_investors.value > 0
        assert metrics.active_projects.value > 0
        assert metrics.pending_dividends.value > 0
        assert metrics.avg_roi.value > 0
        assert metrics.total_transactions.value > 0

    def test_get_platform_overview_with_time_range(self, analytics_service):
        """Test overview con diferentes rangos de tiempo."""
        for time_range in TimeRange:
            metrics = analytics_service.get_platform_overview(time_range)
            assert isinstance(metrics, PlatformMetrics)

    def test_get_investment_timeline(self, analytics_service):
        """Test obtener timeline de inversiones."""
        timeline = analytics_service.get_investment_timeline()

        assert isinstance(timeline, list)
        assert len(timeline) > 0

        first_point = timeline[0]
        assert "date" in first_point
        assert "label" in first_point
        assert "investments" in first_point
        assert "dividends" in first_point

    def test_get_investment_timeline_with_range(self, analytics_service):
        """Test timeline con diferentes rangos."""
        # Semana
        weekly = analytics_service.get_investment_timeline(TimeRange.WEEK)
        assert len(weekly) == 7

        # Mes
        monthly = analytics_service.get_investment_timeline(TimeRange.MONTH)
        assert len(monthly) == 30

    def test_get_investments_by_sector(self, analytics_service):
        """Test distribucion por sector."""
        sectors = analytics_service.get_investments_by_sector()

        assert isinstance(sectors, list)
        assert len(sectors) > 0

        # Verificar estructura
        for sector in sectors:
            assert "sector" in sector
            assert "amount" in sector
            assert "color" in sector
            assert "percentage" in sector
            assert "formatted" in sector

        # Verificar que porcentajes sumen ~100%
        total_percentage = sum(s["percentage"] for s in sectors)
        assert 99 <= total_percentage <= 101

    def test_get_project_performance(self, analytics_service):
        """Test rendimiento de proyectos."""
        projects = analytics_service.get_project_performance()

        assert isinstance(projects, list)
        assert len(projects) > 0

        for project in projects:
            assert "id" in project
            assert "name" in project
            assert "sector" in project
            assert "invested" in project
            assert "roi" in project
            assert "status" in project
            assert "progress" in project

        # Verificar ordenamiento por ROI descendente
        rois = [p["roi"] for p in projects]
        assert rois == sorted(rois, reverse=True)

    def test_get_project_performance_limit(self, analytics_service):
        """Test limite de proyectos."""
        projects_5 = analytics_service.get_project_performance(limit=5)
        projects_2 = analytics_service.get_project_performance(limit=2)

        assert len(projects_5) <= 5
        assert len(projects_2) <= 2

    def test_get_investor_distribution(self, analytics_service):
        """Test distribucion de inversionistas."""
        distribution = analytics_service.get_investor_distribution()

        assert "by_tier" in distribution
        assert "by_country" in distribution
        assert "by_age_group" in distribution

        # Verificar tiers
        tiers = distribution["by_tier"]
        assert len(tiers) > 0
        for tier in tiers:
            assert "tier" in tier
            assert "count" in tier
            assert "min_investment" in tier

        # Verificar paises
        countries = distribution["by_country"]
        assert len(countries) > 0
        total_pct = sum(c["percentage"] for c in countries)
        assert 99 <= total_pct <= 101

    def test_get_transaction_stats(self, analytics_service):
        """Test estadisticas de transacciones."""
        stats = analytics_service.get_transaction_stats()

        assert "summary" in stats
        assert "by_type" in stats
        assert "by_network" in stats
        assert "hourly_distribution" in stats

        # Verificar summary
        summary = stats["summary"]
        assert summary["total_volume"] > 0
        assert summary["total_count"] > 0
        assert 0 <= summary["success_rate"] <= 100

    def test_get_security_metrics(self, analytics_service):
        """Test metricas de seguridad."""
        security = analytics_service.get_security_metrics()

        assert "audits" in security
        assert "alerts" in security
        assert "incidents" in security
        assert "compliance" in security

        # Verificar audits
        audits = security["audits"]
        assert audits["total"] >= audits["passed"]
        assert audits["total"] >= audits["failed"]

        # Verificar compliance
        compliance = security["compliance"]
        assert 0 <= compliance["score"] <= 100

    def test_get_revenue_metrics(self, analytics_service):
        """Test metricas de ingresos."""
        revenue = analytics_service.get_revenue_metrics()

        assert "total_revenue" in revenue
        assert "management_fees" in revenue
        assert "performance_fees" in revenue
        assert "transaction_fees" in revenue
        assert "monthly_trend" in revenue
        assert "revenue_by_project" in revenue

        # Verificar que fees sumen total
        fees_sum = (
            revenue["management_fees"] +
            revenue["performance_fees"] +
            revenue["transaction_fees"]
        )
        assert fees_sum == revenue["total_revenue"]

    def test_get_kpi_summary(self, analytics_service):
        """Test resumen de KPIs."""
        kpis = analytics_service.get_kpi_summary()

        assert "aum" in kpis
        assert "investor_growth" in kpis
        assert "avg_ticket" in kpis
        assert "nps" in kpis
        assert "default_rate" in kpis

        # Verificar estructura de cada KPI
        for kpi_name, kpi in kpis.items():
            assert "current" in kpi
            assert "target" in kpi
            assert "progress" in kpi
            assert "trend" in kpi

    def test_get_days_for_range(self, analytics_service):
        """Test conversion de TimeRange a dias."""
        assert analytics_service._get_days_for_range(TimeRange.DAY) == 1
        assert analytics_service._get_days_for_range(TimeRange.WEEK) == 7
        assert analytics_service._get_days_for_range(TimeRange.MONTH) == 30
        assert analytics_service._get_days_for_range(TimeRange.QUARTER) == 90
        assert analytics_service._get_days_for_range(TimeRange.YEAR) == 365
        assert analytics_service._get_days_for_range(TimeRange.ALL) == 730

    def test_get_hourly_distribution(self, analytics_service):
        """Test distribucion horaria."""
        hourly = analytics_service._get_hourly_distribution()

        assert len(hourly) == 24

        for hour_data in hourly:
            assert "hour" in hour_data
            assert "label" in hour_data
            assert "count" in hour_data
            assert 0 <= hour_data["hour"] <= 23

    def test_get_monthly_revenue_trend(self, analytics_service):
        """Test tendencia mensual de ingresos."""
        monthly = analytics_service._get_monthly_revenue_trend()

        assert len(monthly) == 12

        for month_data in monthly:
            assert "month" in month_data
            assert "revenue" in month_data
            assert "management" in month_data
            assert "performance" in month_data
            assert "transaction" in month_data


class TestPlatformMetrics:
    """Tests para dataclass PlatformMetrics."""

    def test_platform_metrics_creation(self):
        """Test creacion de PlatformMetrics."""
        metrics = PlatformMetrics(
            total_invested=MetricValue(value=Decimal("1000000"), formatted="$1M"),
            total_investors=MetricValue(value=Decimal("500"), formatted="500"),
            active_projects=MetricValue(value=Decimal("10"), formatted="10"),
            pending_dividends=MetricValue(value=Decimal("50000"), formatted="$50K"),
            avg_roi=MetricValue(value=Decimal("12.5"), formatted="12.5%"),
            total_transactions=MetricValue(value=Decimal("1000"), formatted="1,000"),
        )

        assert metrics.total_invested.value == Decimal("1000000")
        assert metrics.total_investors.value == Decimal("500")
        assert metrics.active_projects.value == Decimal("10")
