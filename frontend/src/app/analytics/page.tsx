"use client";

import { useState, useEffect } from "react";
import {
  DollarSign,
  Users,
  FolderKanban,
  Percent,
  Activity,
  Shield,
  Download,
  Calendar,
} from "lucide-react";
import { MetricCard } from "@/components/analytics/metric-card";
import {
  ChartContainer,
  InvestmentTimelineChart,
  SectorDistributionChart,
  ProjectPerformanceChart,
  TransactionDistributionChart,
  KPIProgress,
  InvestorTierChart,
} from "@/components/analytics/charts";
import { PageHeader } from "@/components/page-header";

// Datos de ejemplo (en produccion vendrian del API)
const mockDashboardData = {
  overview: {
    total_invested: {
      value: 45750000,
      change_percent: 8.15,
      trend: "up",
      formatted: "$45.75M MXN",
    },
    total_investors: {
      value: 1247,
      change_percent: 5.68,
      trend: "up",
      formatted: "1,247",
    },
    active_projects: {
      value: 12,
      change_percent: 20.0,
      trend: "up",
      formatted: "12",
    },
    avg_roi: {
      value: 14.5,
      change_percent: 5.07,
      trend: "up",
      formatted: "14.5%",
    },
  },
  timeline: Array.from({ length: 30 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (30 - i));
    const baseValue = 500000 + i * 15000;
    return {
      date: date.toISOString().split("T")[0],
      label: date.toLocaleDateString("es-MX", { day: "2-digit", month: "short" }),
      investments: baseValue + Math.random() * 100000,
      dividends: baseValue * 0.12 + Math.random() * 10000,
    };
  }),
  sectors: [
    { sector: "Energias Renovables", amount: 15500000, percentage: 33.9, color: "#22c55e" },
    { sector: "Tecnologia", amount: 12300000, percentage: 26.9, color: "#3b82f6" },
    { sector: "Bienes Raices", amount: 8750000, percentage: 19.1, color: "#f59e0b" },
    { sector: "Agroindustria", amount: 5200000, percentage: 11.4, color: "#84cc16" },
    { sector: "Infraestructura", amount: 4000000, percentage: 8.7, color: "#6366f1" },
  ],
  top_projects: [
    { name: "Fintech Gateway", roi: 22.3, invested: 5200000, progress: 92, sector: "Tecnologia" },
    { name: "Agave Premium", roi: 18.2, invested: 3800000, progress: 65, sector: "Agroindustria" },
    { name: "Solar Chihuahua I", roi: 16.5, invested: 8500000, progress: 78, sector: "Energia" },
    { name: "Data Center MX", roi: 14.7, invested: 7100000, progress: 35, sector: "Tecnologia" },
    { name: "Torre Reforma 500", roi: 11.8, invested: 12000000, progress: 45, sector: "Inmobiliario" },
  ],
  investors: {
    by_tier: [
      { tier: "Bronce", count: 650, min_investment: 10000, color: "#cd7f32" },
      { tier: "Plata", count: 380, min_investment: 100000, color: "#c0c0c0" },
      { tier: "Oro", count: 165, min_investment: 500000, color: "#ffd700" },
      { tier: "Platino", count: 52, min_investment: 2000000, color: "#e5e4e2" },
    ],
  },
  transactions: {
    by_type: [
      { type: "investment", count: 1523, volume: 32500000, color: "#22c55e" },
      { type: "dividend", count: 1245, volume: 8900000, color: "#3b82f6" },
      { type: "withdrawal", count: 456, volume: 3200000, color: "#f59e0b" },
      { type: "fee", count: 232, volume: 1150000, color: "#6b7280" },
    ],
  },
  kpis: {
    aum: { current: 45750000, target: 50000000, progress: 91.5, trend: "up" },
    investor_growth: { current: 1247, target: 1500, progress: 83.1, trend: "up" },
    avg_ticket: { current: 36680, target: 40000, progress: 91.7, trend: "stable" },
    nps: { current: 72, target: 80, progress: 90, trend: "up" },
    default_rate: { current: 0.8, target: 2.0, progress: 100, trend: "down" },
  },
};

type TimeRange = "7d" | "30d" | "90d" | "365d";

export default function AnalyticsPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>("30d");
  const [isLoading, setIsLoading] = useState(true);
  const [data, setData] = useState(mockDashboardData);

  useEffect(() => {
    // Simular carga de datos
    const loadData = async () => {
      setIsLoading(true);
      // En produccion: await fetch(`/api/v1/analytics/dashboard?time_range=${timeRange}`)
      await new Promise((resolve) => setTimeout(resolve, 500));
      setData(mockDashboardData);
      setIsLoading(false);
    };

    loadData();
  }, [timeRange]);

  const timeRangeOptions: { value: TimeRange; label: string }[] = [
    { value: "7d", label: "7 dias" },
    { value: "30d", label: "30 dias" },
    { value: "90d", label: "90 dias" },
    { value: "365d", label: "1 ano" },
  ];

  if (isLoading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-200 border-t-blue-600" />
          <p className="text-gray-500">Cargando analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader
          title="Analytics Dashboard"
          description="Metricas y KPIs de la plataforma en tiempo real"
        />

        <div className="flex items-center gap-3">
          {/* Time Range Selector */}
          <div className="flex rounded-lg border bg-white p-1">
            {timeRangeOptions.map((option) => (
              <button
                key={option.value}
                onClick={() => setTimeRange(option.value)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  timeRange === option.value
                    ? "bg-blue-600 text-white"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          {/* Export Button */}
          <button className="flex items-center gap-2 rounded-lg border bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            <Download className="h-4 w-4" />
            Exportar
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Invertido"
          value={data.overview.total_invested.formatted}
          change={data.overview.total_invested.change_percent}
          trend={data.overview.total_invested.trend as "up" | "down" | "stable"}
          icon={<DollarSign className="h-5 w-5" />}
          description="vs mes anterior"
        />
        <MetricCard
          title="Inversionistas"
          value={data.overview.total_investors.formatted}
          change={data.overview.total_investors.change_percent}
          trend={data.overview.total_investors.trend as "up" | "down" | "stable"}
          icon={<Users className="h-5 w-5" />}
          description="vs mes anterior"
        />
        <MetricCard
          title="Proyectos Activos"
          value={data.overview.active_projects.formatted}
          change={data.overview.active_projects.change_percent}
          trend={data.overview.active_projects.trend as "up" | "down" | "stable"}
          icon={<FolderKanban className="h-5 w-5" />}
          description="vs mes anterior"
        />
        <MetricCard
          title="ROI Promedio"
          value={data.overview.avg_roi.formatted}
          change={data.overview.avg_roi.change_percent}
          trend={data.overview.avg_roi.trend as "up" | "down" | "stable"}
          icon={<Percent className="h-5 w-5" />}
          description="anualizado"
        />
      </div>

      {/* Main Charts Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Investment Timeline - Takes 2 columns */}
        <ChartContainer
          title="Tendencia de Inversiones"
          subtitle="Inversiones y dividendos en el tiempo"
          className="lg:col-span-2"
        >
          <InvestmentTimelineChart data={data.timeline} />
        </ChartContainer>

        {/* Sector Distribution */}
        <ChartContainer
          title="Distribucion por Sector"
          subtitle="Asignacion de capital por industria"
        >
          <SectorDistributionChart data={data.sectors} />
        </ChartContainer>
      </div>

      {/* Second Row */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top Projects */}
        <ChartContainer
          title="Top Proyectos por ROI"
          subtitle="Proyectos con mejor rendimiento"
        >
          <ProjectPerformanceChart data={data.top_projects} />
        </ChartContainer>

        {/* Transaction Distribution */}
        <ChartContainer
          title="Volumen por Tipo de Transaccion"
          subtitle="Distribucion del volumen transaccional"
        >
          <TransactionDistributionChart data={data.transactions.by_type} />
        </ChartContainer>
      </div>

      {/* Third Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* KPIs */}
        <ChartContainer
          title="KPIs Principales"
          subtitle="Progreso hacia objetivos"
          className="lg:col-span-2"
        >
          <KPIProgress kpis={data.kpis} />
        </ChartContainer>

        {/* Investor Tiers */}
        <ChartContainer
          title="Inversionistas por Tier"
          subtitle="Distribucion de niveles"
        >
          <InvestorTierChart data={data.investors.by_tier} />
        </ChartContainer>
      </div>

      {/* Quick Stats Footer */}
      <div className="grid gap-4 rounded-xl border bg-gradient-to-r from-blue-50 to-indigo-50 p-6 sm:grid-cols-4">
        <div className="text-center">
          <p className="text-sm text-gray-600">Transacciones Hoy</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">127</p>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-600">Volumen 24h</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">$1.2M</p>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-600">Nuevos Inversionistas</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">8</p>
        </div>
        <div className="text-center">
          <p className="text-sm text-gray-600">Uptime</p>
          <p className="mt-1 text-2xl font-bold text-green-600">99.99%</p>
        </div>
      </div>
    </div>
  );
}
