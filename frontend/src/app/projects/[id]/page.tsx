"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { projectsAPI, investorAPI } from "@/lib/api-client";
import { Project, ProjectAnalytics, RiskAnalysis } from "@/types";
import {
  formatCurrency,
  formatPercentage,
  formatDate,
  getProjectStatusColor,
  getRiskLevelColor,
} from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Building2,
  ArrowLeft,
  TrendingUp,
  Clock,
  Shield,
  Target,
  Calendar,
  Users,
  CheckCircle2,
  AlertTriangle,
  DollarSign,
} from "lucide-react";

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [analytics, setAnalytics] = useState<ProjectAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [investAmount, setInvestAmount] = useState("");
  const [investing, setInvesting] = useState(false);
  const [investError, setInvestError] = useState("");
  const [investSuccess, setInvestSuccess] = useState(false);

  useEffect(() => {
    loadProject();
  }, [projectId]);

  const loadProject = async () => {
    try {
      const [projectData, analyticsData] = await Promise.all([
        projectsAPI.get(projectId),
        projectsAPI.getAnalytics(projectId).catch(() => null),
      ]);
      setProject(projectData);
      setAnalytics(analyticsData);
    } catch (error) {
      console.error("Error loading project:", error);
      // Mock data para demo
      setProject({
        id: projectId,
        nombre: "Plaza Comercial Reforma",
        descripcion:
          "Desarrollo de centro comercial premium de 45,000 m2 en Av. Paseo de la Reforma. El proyecto incluye 120 locales comerciales, 3 anclas departamentales, food court con 25 restaurantes, cine multiplex de 12 salas, y estacionamiento subterraneo para 2,000 vehiculos. Ubicacion estrategica en una de las avenidas mas importantes de CDMX.",
        sector: "Inmobiliario",
        monto_solicitado: 15000000,
        monto_financiado: 9000000,
        plazo_meses: 36,
        estado: "Financiando",
        tasa_rendimiento_anual: 0.18,
        created_at: "2024-01-15",
      });
      setAnalytics({
        project_id: projectId,
        nombre: "Plaza Comercial Reforma",
        estado: "Financiando",
        financials: {
          van: 4500000,
          tir: 0.22,
          roi: 0.54,
          risk_level: "AA",
        },
        cash_flow_series: [
          { period: "2024", amount: -15000000 },
          { period: "2025", amount: 3500000 },
          { period: "2026", amount: 5200000 },
          { period: "2027", amount: 6800000 },
          { period: "2028", amount: 7500000 },
        ],
        monto_solicitado: 15000000,
        monto_financiado: 9000000,
        porcentaje_financiado: 60,
        total_inversionistas: 42,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleInvest = async () => {
    const amount = parseFloat(investAmount);
    if (isNaN(amount) || amount < 10000) {
      setInvestError("El monto minimo de inversion es $10,000");
      return;
    }

    if (project && amount > project.monto_solicitado - project.monto_financiado) {
      setInvestError("El monto excede el remanente del proyecto");
      return;
    }

    setInvesting(true);
    setInvestError("");

    try {
      await investorAPI.invest({
        proyecto_id: projectId,
        monto: amount,
      });
      setInvestSuccess(true);
      setInvestAmount("");
      // Recargar datos del proyecto
      setTimeout(() => {
        loadProject();
        setInvestSuccess(false);
      }, 3000);
    } catch (error: any) {
      setInvestError(error.response?.data?.detail || "Error al procesar la inversion");
    } finally {
      setInvesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <Building2 className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
        <p className="text-muted-foreground">Proyecto no encontrado</p>
        <Button className="mt-4" asChild>
          <Link href="/projects">Ver Todos los Proyectos</Link>
        </Button>
      </div>
    );
  }

  const porcentajeFinanciado = (project.monto_financiado / project.monto_solicitado) * 100;
  const montoRemanente = project.monto_solicitado - project.monto_financiado;

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <Button variant="ghost" className="gap-2" asChild>
        <Link href="/projects">
          <ArrowLeft className="h-4 w-4" />
          Volver a Proyectos
        </Link>
      </Button>

      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span
              className={`px-3 py-1 rounded-full text-sm font-medium ${getProjectStatusColor(
                project.estado
              )}`}
            >
              {project.estado}
            </span>
            <span className="px-3 py-1 rounded-full text-sm font-medium bg-slate-100 text-slate-600">
              {project.sector}
            </span>
          </div>
          <h1 className="text-3xl font-bold text-slate-900">{project.nombre}</h1>
          <p className="text-muted-foreground mt-2 max-w-2xl">
            {project.descripcion}
          </p>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Project Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Financial KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <TrendingUp className="h-6 w-6 text-green-600 mx-auto mb-2" />
                <p className="text-2xl font-bold text-green-600">
                  {project.tasa_rendimiento_anual
                    ? formatPercentage(project.tasa_rendimiento_anual)
                    : "N/A"}
                </p>
                <p className="text-xs text-muted-foreground">Rendimiento Anual</p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-4 text-center">
                <Clock className="h-6 w-6 text-blue-600 mx-auto mb-2" />
                <p className="text-2xl font-bold">{project.plazo_meses}</p>
                <p className="text-xs text-muted-foreground">Meses de Plazo</p>
              </CardContent>
            </Card>

            {analytics && (
              <>
                <Card>
                  <CardContent className="p-4 text-center">
                    <Target className="h-6 w-6 text-purple-600 mx-auto mb-2" />
                    <p className="text-2xl font-bold">
                      {analytics.financials.tir
                        ? formatPercentage(analytics.financials.tir)
                        : "N/A"}
                    </p>
                    <p className="text-xs text-muted-foreground">TIR</p>
                  </CardContent>
                </Card>

                <Card>
                  <CardContent className="p-4 text-center">
                    <Shield className="h-6 w-6 text-amber-600 mx-auto mb-2" />
                    <span
                      className={`text-xl font-bold px-2 py-0.5 rounded ${getRiskLevelColor(
                        analytics.financials.risk_level
                      )}`}
                    >
                      {analytics.financials.risk_level}
                    </span>
                    <p className="text-xs text-muted-foreground mt-1">
                      Nivel Riesgo
                    </p>
                  </CardContent>
                </Card>
              </>
            )}
          </div>

          {/* Funding Progress */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Progreso de Financiamiento
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">
                  {analytics?.total_inversionistas || 0} inversionistas
                </span>
                <span className="font-medium">
                  {porcentajeFinanciado.toFixed(1)}% completado
                </span>
              </div>
              <div className="w-full h-4 bg-slate-200 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-primary to-primary/80 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(porcentajeFinanciado, 100)}%` }}
                />
              </div>
              <div className="grid grid-cols-3 gap-4 text-center pt-2">
                <div>
                  <p className="text-lg font-bold text-primary">
                    {formatCurrency(project.monto_financiado)}
                  </p>
                  <p className="text-xs text-muted-foreground">Financiado</p>
                </div>
                <div>
                  <p className="text-lg font-bold text-amber-600">
                    {formatCurrency(montoRemanente)}
                  </p>
                  <p className="text-xs text-muted-foreground">Remanente</p>
                </div>
                <div>
                  <p className="text-lg font-bold">
                    {formatCurrency(project.monto_solicitado)}
                  </p>
                  <p className="text-xs text-muted-foreground">Meta</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Cash Flow Projection */}
          {analytics && analytics.cash_flow_series.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-5 w-5" />
                  Flujo de Caja Proyectado
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {analytics.cash_flow_series.map((flow, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 rounded-lg bg-slate-50"
                    >
                      <span className="font-medium">{flow.period}</span>
                      <span
                        className={`font-bold ${
                          flow.amount >= 0 ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {flow.amount >= 0 ? "+" : ""}
                        {formatCurrency(flow.amount)}
                      </span>
                    </div>
                  ))}
                </div>
                <div className="mt-4 p-4 rounded-lg bg-primary/5 border border-primary/20">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground">
                      Valor Actual Neto (VAN)
                    </span>
                    <span className="text-xl font-bold text-primary">
                      {formatCurrency(analytics.financials.van)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right Column - Investment Card */}
        <div className="space-y-6">
          <Card className="sticky top-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Invertir en este Proyecto
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {project.estado === "Financiando" ? (
                <>
                  {investSuccess ? (
                    <div className="p-4 rounded-lg bg-green-50 border border-green-200 text-center">
                      <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto mb-2" />
                      <p className="font-semibold text-green-800">
                        Inversion Exitosa
                      </p>
                      <p className="text-sm text-green-600">
                        Tu inversion ha sido procesada correctamente
                      </p>
                    </div>
                  ) : (
                    <>
                      <div>
                        <label className="text-sm text-muted-foreground">
                          Monto a Invertir
                        </label>
                        <div className="relative mt-1">
                          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                            $
                          </span>
                          <Input
                            type="number"
                            placeholder="10,000"
                            value={investAmount}
                            onChange={(e) => {
                              setInvestAmount(e.target.value);
                              setInvestError("");
                            }}
                            className="pl-8"
                            min={10000}
                            step={1000}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Minimo: $10,000 MXN
                        </p>
                      </div>

                      {investError && (
                        <div className="p-3 rounded-lg bg-red-50 border border-red-200 flex items-start gap-2">
                          <AlertTriangle className="h-4 w-4 text-red-600 mt-0.5" />
                          <p className="text-sm text-red-600">{investError}</p>
                        </div>
                      )}

                      {investAmount && parseFloat(investAmount) >= 10000 && (
                        <div className="p-3 rounded-lg bg-slate-50 space-y-2">
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">
                              Rendimiento esperado anual
                            </span>
                            <span className="font-medium text-green-600">
                              +
                              {formatCurrency(
                                parseFloat(investAmount) *
                                  (project.tasa_rendimiento_anual || 0)
                              )}
                            </span>
                          </div>
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">
                              Rendimiento total ({project.plazo_meses / 12} anos)
                            </span>
                            <span className="font-medium text-green-600">
                              +
                              {formatCurrency(
                                parseFloat(investAmount) *
                                  (project.tasa_rendimiento_anual || 0) *
                                  (project.plazo_meses / 12)
                              )}
                            </span>
                          </div>
                        </div>
                      )}

                      <Button
                        className="w-full"
                        size="lg"
                        onClick={handleInvest}
                        disabled={investing || !investAmount}
                      >
                        {investing ? (
                          <div className="flex items-center gap-2">
                            <div className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                            Procesando...
                          </div>
                        ) : (
                          "Confirmar Inversion"
                        )}
                      </Button>
                    </>
                  )}
                </>
              ) : (
                <div className="text-center py-4">
                  <p className="text-muted-foreground">
                    Este proyecto no esta disponible para inversiones en este
                    momento.
                  </p>
                </div>
              )}

              {/* Project Info */}
              <div className="pt-4 border-t space-y-3">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Remanente</span>
                  <span className="font-medium">
                    {formatCurrency(montoRemanente)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Fecha publicacion</span>
                  <span className="font-medium">
                    {formatDate(project.created_at)}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Inversionistas</span>
                  <span className="font-medium">
                    {analytics?.total_inversionistas || 0}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Risk Warning */}
          <Card className="bg-amber-50 border-amber-200">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
                <div>
                  <p className="font-medium text-amber-800">Aviso de Riesgo</p>
                  <p className="text-sm text-amber-700 mt-1">
                    Las inversiones en proyectos conllevan riesgos. El capital
                    invertido no esta garantizado y los rendimientos pasados no
                    garantizan rendimientos futuros.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
