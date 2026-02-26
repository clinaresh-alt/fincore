"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/auth-store";
import { investorAPI, projectsAPI } from "@/lib/api-client";
import { Portfolio, Project } from "@/types";
import { formatCurrency, formatPercentage, getProjectStatusColor } from "@/lib/utils";
import { KPICard } from "@/components/ui/kpi-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PortfolioChart } from "@/components/charts/portfolio-chart";
import { CashFlowChart } from "@/components/charts/cashflow-chart";
import {
  Wallet,
  TrendingUp,
  PieChart,
  Activity,
  ArrowRight,
  Building2,
} from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [portfolioData, projectsData] = await Promise.all([
        investorAPI.getPortfolio().catch(() => null),
        projectsAPI.list({ estado: "Financiando" }).catch(() => []),
      ]);
      setPortfolio(portfolioData);
      setProjects(projectsData);
    } catch (error) {
      console.error("Error loading dashboard:", error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  // Helper para convertir strings a numeros (API puede devolver strings)
  const toNumber = (val: string | number | null | undefined): number => {
    if (val === null || val === undefined) return 0;
    return typeof val === "string" ? parseFloat(val) || 0 : val;
  };

  // Normalizar datos del portfolio (API devuelve strings en algunos campos)
  const normalizePortfolio = (p: Portfolio | null): Portfolio => {
    if (!p) {
      // Sin datos de portfolio - mostrar valores vacios
      return {
        kpis: {
          total_invertido: 0,
          rendimiento_total: 0,
          rendimiento_porcentual: 0,
          tir_cartera: null,
          moic: 0,
          proyectos_activos: 0,
          proyectos_completados: 0,
          proyectos_en_default: 0,
        },
        distribucion_sectores: [],
        inversiones: [],
        proximos_pagos: [],
        rendimiento_historico: [],
      };
    }
    // Convertir strings a numeros en KPIs
    return {
      ...p,
      kpis: {
        total_invertido: toNumber(p.kpis.total_invertido),
        rendimiento_total: toNumber(p.kpis.rendimiento_total),
        rendimiento_porcentual: toNumber(p.kpis.rendimiento_porcentual),
        tir_cartera: p.kpis.tir_cartera ? toNumber(p.kpis.tir_cartera) : null,
        moic: toNumber(p.kpis.moic) || 1,
        proyectos_activos: toNumber(p.kpis.proyectos_activos),
        proyectos_completados: toNumber(p.kpis.proyectos_completados),
        proyectos_en_default: toNumber(p.kpis.proyectos_en_default),
      },
    };
  };

  const mockPortfolio = normalizePortfolio(portfolio);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">
            Bienvenido, {user?.email?.split("@")[0] || "Inversionista"}
          </h1>
          <p className="text-muted-foreground mt-1">
            Resumen de tu portafolio de inversiones
          </p>
        </div>
        <Button asChild>
          <Link href="/projects">
            <Building2 className="mr-2 h-4 w-4" />
            Ver Proyectos
          </Link>
        </Button>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="Total Invertido"
          value={formatCurrency(mockPortfolio.kpis.total_invertido)}
          icon={Wallet}
          trend={{ value: 12, isPositive: true }}
        />
        <KPICard
          title="Rendimiento Total"
          value={formatCurrency(mockPortfolio.kpis.rendimiento_total)}
          subtitle={formatPercentage(mockPortfolio.kpis.rendimiento_porcentual)}
          icon={TrendingUp}
          trend={{ value: 8.5, isPositive: true }}
        />
        <KPICard
          title="TIR de Cartera"
          value={mockPortfolio.kpis.tir_cartera ? formatPercentage(mockPortfolio.kpis.tir_cartera) : "N/A"}
          subtitle="Tasa Interna de Retorno"
          icon={Activity}
        />
        <KPICard
          title="MOIC"
          value={`${mockPortfolio.kpis.moic.toFixed(2)}x`}
          subtitle="Multiple on Invested Capital"
          icon={PieChart}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Distribucion por Sector */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Distribucion por Sector</CardTitle>
          </CardHeader>
          <CardContent>
            <PortfolioChart data={mockPortfolio.distribucion_sectores} />
          </CardContent>
        </Card>

        {/* Rendimiento Historico */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Rendimiento Mensual</CardTitle>
          </CardHeader>
          <CardContent>
            <CashFlowChart
              data={mockPortfolio.rendimiento_historico.map((r) => ({
                period: r.mes,
                amount: r.rendimiento,
              }))}
            />
          </CardContent>
        </Card>
      </div>

      {/* Proyectos Disponibles */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Proyectos en Financiamiento</CardTitle>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/projects">
              Ver todos
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </CardHeader>
        <CardContent>
          {projects.length > 0 ? (
            <div className="space-y-4">
              {projects.slice(0, 3).map((project) => (
                <div
                  key={project.id}
                  className="flex items-center justify-between p-4 rounded-lg border hover:bg-slate-50 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold">{project.nombre}</h3>
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${getProjectStatusColor(
                          project.estado
                        )}`}
                      >
                        {project.estado}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                      <span>{project.sector}</span>
                      <span>|</span>
                      <span>{project.plazo_meses} meses</span>
                      <span>|</span>
                      <span>
                        {project.tasa_rendimiento_anual
                          ? formatPercentage(project.tasa_rendimiento_anual)
                          : "N/A"}{" "}
                        anual
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">
                      {formatCurrency(project.monto_solicitado)}
                    </p>
                    <div className="w-32 h-2 bg-slate-200 rounded-full mt-2">
                      <div
                        className="h-full bg-primary rounded-full"
                        style={{
                          width: `${Math.min(
                            (project.monto_financiado / project.monto_solicitado) * 100,
                            100
                          )}%`,
                        }}
                      />
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatPercentage(
                        project.monto_financiado / project.monto_solicitado
                      )}{" "}
                      financiado
                    </p>
                  </div>
                  <Button variant="outline" size="sm" className="ml-4" asChild>
                    <Link href={`/projects/${project.id}`}>Invertir</Link>
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <Building2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No hay proyectos en financiamiento actualmente</p>
              <Button variant="outline" className="mt-4" asChild>
                <Link href="/projects">Explorar Proyectos</Link>
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Resumen Rapido */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-green-50 border-green-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                <TrendingUp className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-green-700">
                  {mockPortfolio.kpis.proyectos_activos}
                </p>
                <p className="text-sm text-green-600">Proyectos Activos</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-blue-50 border-blue-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center">
                <Activity className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-blue-700">
                  {mockPortfolio.kpis.proyectos_completados}
                </p>
                <p className="text-sm text-blue-600">Proyectos Completados</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-purple-50 border-purple-200">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="h-12 w-12 rounded-full bg-purple-100 flex items-center justify-center">
                <PieChart className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-2xl font-bold text-purple-700">
                  {mockPortfolio.distribucion_sectores.length}
                </p>
                <p className="text-sm text-purple-600">Sectores Diversificados</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
