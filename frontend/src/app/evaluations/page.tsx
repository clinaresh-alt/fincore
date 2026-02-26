"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";
import {
  Briefcase,
  Search,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  BarChart3,
  Shield,
  DollarSign,
  Calendar,
  Building2,
  Target,
  Percent,
  ArrowUpRight,
  ArrowDownRight,
  Loader2,
  FileText,
  ChevronDown,
  ChevronUp,
  Activity,
  PieChart,
  Info,
  Calculator,
  Settings,
} from "lucide-react";
import { SectorMetricsForm } from "@/components/sector-metrics-form";
import { formatCurrency, formatPercentage, getRiskLevelColor } from "@/lib/utils";

interface Evaluation {
  inversion_inicial: number | null;
  tasa_descuento: number | null;
  van: number | null;
  tir: number | null;
  roi: number | null;
  payback_period: number | null;
  indice_rentabilidad: number | null;
  van_optimista: number | null;
  van_pesimista: number | null;
  tir_optimista: number | null;
  tir_pesimista: number | null;
  fecha_evaluacion: string | null;
  es_viable: boolean;
}

interface RiskAnalysis {
  score_crediticio: number | null;
  nivel_riesgo: string | null;
  probabilidad_default: number | null;
  probabilidad_exito: number | null;
  score_capacidad_pago: number | null;
  score_historial: number | null;
  score_garantias: number | null;
  ratio_deuda_ingreso: number | null;
  loan_to_value: number | null;
  valor_garantias: number | null;
}

interface CashFlow {
  periodo: number;
  ingresos: number;
  egresos: number;
  flujo_neto: number;
  descripcion: string | null;
}

interface Project {
  id: string;
  nombre: string;
  descripcion: string | null;
  sector: string;
  empresa_solicitante: string | null;
  monto_solicitado: number;
  monto_financiado: number;
  plazo_meses: number;
  tasa_rendimiento_anual: number | null;
  estado: string;
  created_at: string | null;
  tiene_evaluacion: boolean;
  tiene_analisis_riesgo: boolean;
  evaluacion: Evaluation | null;
  riesgo: RiskAnalysis | null;
  flujos_caja: CashFlow[];
  indicadores_sectoriales: string[];
}

interface Stats {
  total: number;
  pendientes: number;
  aprobados: number;
  rechazados: number;
  financiando: number;
  por_sector: Record<string, number>;
}

interface AllIndicators {
  [key: string]: string;
}

const statusConfig: Record<string, { color: string; icon: React.ElementType; label: string }> = {
  "En Evaluacion": { color: "bg-yellow-100 text-yellow-800", icon: Clock, label: "En Evaluacion" },
  "Aprobado": { color: "bg-green-100 text-green-800", icon: CheckCircle2, label: "Aprobado" },
  "Rechazado": { color: "bg-red-100 text-red-800", icon: XCircle, label: "Rechazado" },
  "Financiando": { color: "bg-blue-100 text-blue-800", icon: TrendingUp, label: "Financiando" },
  "Financiado": { color: "bg-purple-100 text-purple-800", icon: CheckCircle2, label: "Financiado" },
  "En Ejecucion": { color: "bg-indigo-100 text-indigo-800", icon: Activity, label: "En Ejecucion" },
  "Completado": { color: "bg-emerald-100 text-emerald-800", icon: CheckCircle2, label: "Completado" },
  "Default": { color: "bg-red-200 text-red-900", icon: AlertTriangle, label: "Default" },
};

const riskLevelConfig: Record<string, { color: string; label: string; description: string }> = {
  "AAA": { color: "bg-emerald-100 text-emerald-800", label: "AAA", description: "Riesgo Minimo" },
  "AA": { color: "bg-green-100 text-green-800", label: "AA", description: "Bajo Riesgo" },
  "A": { color: "bg-lime-100 text-lime-800", label: "A", description: "Riesgo Moderado-Bajo" },
  "B": { color: "bg-yellow-100 text-yellow-800", label: "B", description: "Riesgo Moderado" },
  "C": { color: "bg-red-100 text-red-800", label: "C", description: "Alto Riesgo" },
};

export default function EvaluationsPage() {
  const [search, setSearch] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [allIndicators, setAllIndicators] = useState<AllIndicators>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedProject, setExpandedProject] = useState<string | null>(null);
  const [sectorFilter, setSectorFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  useEffect(() => {
    loadProjects();
  }, [sectorFilter, statusFilter]);

  const loadProjects = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (sectorFilter) params.append("sector", sectorFilter);
      if (statusFilter) params.append("estado", statusFilter);

      const response = await apiClient.get(`/projects/evaluations/list?${params.toString()}`);
      setProjects(response.data.projects || []);
      setStats(response.data.stats || null);
      setAllIndicators(response.data.all_indicators || {});
    } catch (err: any) {
      console.error("Error loading projects:", err);
      setError(err.response?.data?.detail || "Error cargando proyectos");
    } finally {
      setLoading(false);
    }
  };

  const filteredProjects = projects.filter((p) =>
    p.nombre.toLowerCase().includes(search.toLowerCase()) ||
    (p.empresa_solicitante?.toLowerCase().includes(search.toLowerCase()) ?? false)
  );

  const toggleProjectExpand = (projectId: string) => {
    setExpandedProject(expandedProject === projectId ? null : projectId);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-3 text-muted-foreground">Cargando evaluaciones...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="p-4 rounded-lg bg-red-50 border border-red-200">
          <div className="flex items-center gap-2">
            <XCircle className="h-5 w-5 text-red-600" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
          <Button variant="outline" className="mt-4" onClick={loadProjects}>
            Reintentar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-900">Evaluaciones de Proyectos</h1>
        <p className="text-muted-foreground mt-1">
          Panel completo de evaluacion financiera con indicadores basicos y sectoriales
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-slate-100 flex items-center justify-center">
                <Briefcase className="h-5 w-5 text-slate-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats?.total || 0}</p>
                <p className="text-xs text-muted-foreground">Total Proyectos</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-yellow-100 flex items-center justify-center">
                <Clock className="h-5 w-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats?.pendientes || 0}</p>
                <p className="text-xs text-muted-foreground">En Evaluacion</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats?.aprobados || 0}</p>
                <p className="text-xs text-muted-foreground">Aprobados</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                <TrendingUp className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats?.financiando || 0}</p>
                <p className="text-xs text-muted-foreground">Financiando</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-red-100 flex items-center justify-center">
                <XCircle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-2xl font-bold">{stats?.rechazados || 0}</p>
                <p className="text-xs text-muted-foreground">Rechazados</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4 items-center">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Buscar proyectos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-10"
          />
        </div>

        <select
          value={sectorFilter}
          onChange={(e) => setSectorFilter(e.target.value)}
          className="h-10 px-3 rounded-md border border-input bg-background text-sm"
        >
          <option value="">Todos los sectores</option>
          {stats?.por_sector && Object.keys(stats.por_sector).map((sector) => (
            <option key={sector} value={sector}>{sector} ({stats.por_sector[sector]})</option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 px-3 rounded-md border border-input bg-background text-sm"
        >
          <option value="">Todos los estados</option>
          <option value="En Evaluacion">En Evaluacion</option>
          <option value="Aprobado">Aprobado</option>
          <option value="Rechazado">Rechazado</option>
          <option value="Financiando">Financiando</option>
        </select>

        <Button variant="outline" onClick={loadProjects}>
          Actualizar
        </Button>
      </div>

      {/* Projects List */}
      <div className="space-y-4">
        {filteredProjects.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-semibold mb-2">No hay proyectos</h3>
              <p className="text-muted-foreground">
                No se encontraron proyectos con los filtros seleccionados
              </p>
            </CardContent>
          </Card>
        ) : (
          filteredProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              allIndicators={allIndicators}
              isExpanded={expandedProject === project.id}
              onToggle={() => toggleProjectExpand(project.id)}
              onRefresh={loadProjects}
            />
          ))
        )}
      </div>
    </div>
  );
}

function ProjectCard({
  project,
  allIndicators,
  isExpanded,
  onToggle,
  onRefresh,
}: {
  project: Project;
  allIndicators: AllIndicators;
  isExpanded: boolean;
  onToggle: () => void;
  onRefresh: () => void;
}) {
  const [showSectorForm, setShowSectorForm] = useState(false);
  const StatusIcon = statusConfig[project.estado]?.icon || Clock;
  const statusStyle = statusConfig[project.estado] || statusConfig["En Evaluacion"];

  return (
    <Card className="overflow-hidden">
      {/* Header Row - Always Visible */}
      <div
        className="p-4 cursor-pointer hover:bg-slate-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h3 className="font-semibold text-lg">{project.nombre}</h3>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex items-center gap-1 ${statusStyle.color}`}>
                <StatusIcon className="h-3 w-3" />
                {statusStyle.label}
              </span>
              {project.riesgo?.nivel_riesgo && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  riskLevelConfig[project.riesgo.nivel_riesgo]?.color || "bg-gray-100 text-gray-800"
                }`}>
                  {project.riesgo.nivel_riesgo}
                </span>
              )}
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                {project.sector}
              </span>
            </div>
            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
              {project.empresa_solicitante && (
                <>
                  <span className="flex items-center gap-1">
                    <Building2 className="h-3 w-3" />
                    {project.empresa_solicitante}
                  </span>
                  <span>|</span>
                </>
              )}
              <span className="flex items-center gap-1">
                <DollarSign className="h-3 w-3" />
                {formatCurrency(project.monto_solicitado)}
              </span>
              <span>|</span>
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {project.plazo_meses} meses
              </span>
            </div>
          </div>

          {/* Quick Indicators */}
          {project.evaluacion && (
            <div className="hidden md:grid grid-cols-4 gap-6 text-center mx-4">
              <div>
                <p className={`font-semibold ${(project.evaluacion.van || 0) >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {project.evaluacion.van !== null ? formatCurrency(project.evaluacion.van) : "N/A"}
                </p>
                <p className="text-xs text-muted-foreground">VAN</p>
              </div>
              <div>
                <p className="font-semibold">
                  {project.evaluacion.tir !== null ? formatPercentage(project.evaluacion.tir) : "N/A"}
                </p>
                <p className="text-xs text-muted-foreground">TIR</p>
              </div>
              <div>
                <p className="font-semibold">
                  {project.evaluacion.roi !== null ? formatPercentage(project.evaluacion.roi) : "N/A"}
                </p>
                <p className="text-xs text-muted-foreground">ROI</p>
              </div>
              <div>
                <p className="font-semibold">
                  {project.evaluacion.payback_period !== null ? `${project.evaluacion.payback_period.toFixed(1)} meses` : "N/A"}
                </p>
                <p className="text-xs text-muted-foreground">Payback</p>
              </div>
            </div>
          )}

          <div className="flex items-center gap-2">
            {isExpanded ? (
              <ChevronUp className="h-5 w-5 text-muted-foreground" />
            ) : (
              <ChevronDown className="h-5 w-5 text-muted-foreground" />
            )}
          </div>
        </div>
      </div>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="border-t bg-slate-50/50 p-6 space-y-6">
          {/* Description */}
          {project.descripcion && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-2">Descripcion</h4>
              <p className="text-sm">{project.descripcion}</p>
            </div>
          )}

          {/* Evaluation Section */}
          {project.evaluacion ? (
            <>
              {/* Financial Indicators */}
              <div>
                <h4 className="text-sm font-semibold flex items-center gap-2 mb-4">
                  <BarChart3 className="h-4 w-4" />
                  Indicadores Financieros Basicos
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <IndicatorCard
                    label="VAN"
                    value={project.evaluacion.van}
                    format="currency"
                    description="Valor Actual Neto"
                    positive={(project.evaluacion.van || 0) >= 0}
                  />
                  <IndicatorCard
                    label="TIR"
                    value={project.evaluacion.tir}
                    format="percentage"
                    description="Tasa Interna de Retorno"
                  />
                  <IndicatorCard
                    label="ROI"
                    value={project.evaluacion.roi}
                    format="percentage"
                    description="Retorno sobre Inversion"
                  />
                  <IndicatorCard
                    label="Payback"
                    value={project.evaluacion.payback_period}
                    format="months"
                    description="Periodo de Recuperacion"
                  />
                  <IndicatorCard
                    label="IR"
                    value={project.evaluacion.indice_rentabilidad}
                    format="number"
                    description="Indice de Rentabilidad"
                  />
                </div>
              </div>

              {/* Scenario Analysis */}
              {(project.evaluacion.van_optimista || project.evaluacion.van_pesimista) && (
                <div>
                  <h4 className="text-sm font-semibold flex items-center gap-2 mb-4">
                    <Activity className="h-4 w-4" />
                    Analisis de Escenarios
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card className="bg-red-50 border-red-200">
                      <CardContent className="p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <TrendingDown className="h-4 w-4 text-red-600" />
                          <span className="text-sm font-medium text-red-700">Pesimista</span>
                        </div>
                        <p className="text-lg font-bold text-red-700">
                          {project.evaluacion.van_pesimista !== null ? formatCurrency(project.evaluacion.van_pesimista) : "N/A"}
                        </p>
                        {project.evaluacion.tir_pesimista && (
                          <p className="text-sm text-red-600">TIR: {formatPercentage(project.evaluacion.tir_pesimista)}</p>
                        )}
                      </CardContent>
                    </Card>

                    <Card className="bg-slate-50 border-slate-200">
                      <CardContent className="p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Target className="h-4 w-4 text-slate-600" />
                          <span className="text-sm font-medium text-slate-700">Base</span>
                        </div>
                        <p className="text-lg font-bold text-slate-700">
                          {project.evaluacion.van !== null ? formatCurrency(project.evaluacion.van) : "N/A"}
                        </p>
                        {project.evaluacion.tir && (
                          <p className="text-sm text-slate-600">TIR: {formatPercentage(project.evaluacion.tir)}</p>
                        )}
                      </CardContent>
                    </Card>

                    <Card className="bg-green-50 border-green-200">
                      <CardContent className="p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <TrendingUp className="h-4 w-4 text-green-600" />
                          <span className="text-sm font-medium text-green-700">Optimista</span>
                        </div>
                        <p className="text-lg font-bold text-green-700">
                          {project.evaluacion.van_optimista !== null ? formatCurrency(project.evaluacion.van_optimista) : "N/A"}
                        </p>
                        {project.evaluacion.tir_optimista && (
                          <p className="text-sm text-green-600">TIR: {formatPercentage(project.evaluacion.tir_optimista)}</p>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-8 bg-yellow-50 rounded-lg border border-yellow-200">
              <AlertTriangle className="h-8 w-8 mx-auto text-yellow-600 mb-2" />
              <p className="text-sm font-medium text-yellow-800">Sin evaluacion financiera</p>
              <p className="text-xs text-yellow-600 mt-1">Este proyecto no ha sido evaluado aun</p>
            </div>
          )}

          {/* Risk Analysis */}
          {project.riesgo && (
            <div>
              <h4 className="text-sm font-semibold flex items-center gap-2 mb-4">
                <Shield className="h-4 w-4" />
                Analisis de Riesgo Crediticio
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <Card className="bg-white">
                  <CardContent className="p-4 text-center">
                    <div className={`inline-flex items-center justify-center h-12 w-12 rounded-full mb-2 ${
                      riskLevelConfig[project.riesgo.nivel_riesgo || ""]?.color || "bg-gray-100"
                    }`}>
                      <span className="font-bold">{project.riesgo.nivel_riesgo || "?"}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">Nivel de Riesgo</p>
                    <p className="text-xs font-medium mt-1">
                      {riskLevelConfig[project.riesgo.nivel_riesgo || ""]?.description || "Sin clasificar"}
                    </p>
                  </CardContent>
                </Card>

                <IndicatorCard
                  label="Score"
                  value={project.riesgo.score_crediticio}
                  format="score"
                  description="Score Crediticio (0-1000)"
                />
                <IndicatorCard
                  label="P. Exito"
                  value={project.riesgo.probabilidad_exito}
                  format="percentage"
                  description="Probabilidad de Exito"
                  positive={true}
                />
                <IndicatorCard
                  label="P. Default"
                  value={project.riesgo.probabilidad_default}
                  format="percentage"
                  description="Probabilidad de Default"
                  positive={false}
                />
                <IndicatorCard
                  label="LTV"
                  value={project.riesgo.loan_to_value}
                  format="percentage"
                  description="Loan to Value"
                />
              </div>

              {/* Score Components */}
              <div className="mt-4 grid grid-cols-3 gap-4">
                <div className="bg-white rounded-lg border p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">Capacidad de Pago</span>
                    <span className="text-sm font-medium">{project.riesgo.score_capacidad_pago || 0}/1000</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${(project.riesgo.score_capacidad_pago || 0) / 10}%` }}
                    />
                  </div>
                </div>
                <div className="bg-white rounded-lg border p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">Historial</span>
                    <span className="text-sm font-medium">{project.riesgo.score_historial || 0}/1000</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-green-500 rounded-full"
                      style={{ width: `${(project.riesgo.score_historial || 0) / 10}%` }}
                    />
                  </div>
                </div>
                <div className="bg-white rounded-lg border p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">Garantias</span>
                    <span className="text-sm font-medium">{project.riesgo.score_garantias || 0}/1000</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-500 rounded-full"
                      style={{ width: `${(project.riesgo.score_garantias || 0) / 10}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sector-specific Indicators */}
          {project.indicadores_sectoriales && project.indicadores_sectoriales.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-semibold flex items-center gap-2">
                  <PieChart className="h-4 w-4" />
                  Indicadores Sectoriales - {project.sector}
                </h4>
                <Button
                  variant={showSectorForm ? "default" : "outline"}
                  size="sm"
                  onClick={(e) => {
                    e.stopPropagation();
                    setShowSectorForm(!showSectorForm);
                  }}
                >
                  <Calculator className="h-4 w-4 mr-2" />
                  {showSectorForm ? "Ocultar Formulario" : "Calcular Indicadores"}
                </Button>
              </div>

              {/* Sector Metrics Form */}
              {showSectorForm && (
                <div className="mb-6 p-4 border rounded-lg bg-white">
                  <SectorMetricsForm
                    projectId={project.id}
                    sector={project.sector}
                    projectName={project.nombre}
                    onSaved={onRefresh}
                  />
                </div>
              )}

              {/* Available indicators list */}
              {!showSectorForm && (
                <div className="bg-white rounded-lg border p-4">
                  <div className="flex flex-wrap gap-2">
                    {project.indicadores_sectoriales.map((indicator) => (
                      <div
                        key={indicator}
                        className="px-3 py-1.5 bg-slate-100 rounded-full text-xs font-medium flex items-center gap-1"
                        title={allIndicators[indicator] || indicator}
                      >
                        <Info className="h-3 w-3 text-muted-foreground" />
                        {allIndicators[indicator] || indicator}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground mt-3">
                    Haz clic en "Calcular Indicadores" para ingresar datos y obtener metricas calculadas
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Cash Flows */}
          {project.flujos_caja && project.flujos_caja.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold flex items-center gap-2 mb-4">
                <DollarSign className="h-4 w-4" />
                Flujos de Caja Proyectados
              </h4>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-3 font-medium text-muted-foreground">Periodo</th>
                      <th className="text-right py-2 px-3 font-medium text-muted-foreground">Ingresos</th>
                      <th className="text-right py-2 px-3 font-medium text-muted-foreground">Egresos</th>
                      <th className="text-right py-2 px-3 font-medium text-muted-foreground">Flujo Neto</th>
                      <th className="text-left py-2 px-3 font-medium text-muted-foreground">Descripcion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {project.flujos_caja.map((cf) => (
                      <tr key={cf.periodo} className="border-b last:border-b-0">
                        <td className="py-2 px-3">Periodo {cf.periodo}</td>
                        <td className="py-2 px-3 text-right text-green-600">{formatCurrency(cf.ingresos)}</td>
                        <td className="py-2 px-3 text-right text-red-600">{formatCurrency(cf.egresos)}</td>
                        <td className={`py-2 px-3 text-right font-medium ${cf.flujo_neto >= 0 ? "text-green-600" : "text-red-600"}`}>
                          {formatCurrency(cf.flujo_neto)}
                        </td>
                        <td className="py-2 px-3 text-muted-foreground">{cf.descripcion || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Viability Badge */}
          {project.evaluacion && (
            <div className={`flex items-center gap-3 p-4 rounded-lg ${
              project.evaluacion.es_viable ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"
            }`}>
              {project.evaluacion.es_viable ? (
                <>
                  <CheckCircle2 className="h-6 w-6 text-green-600" />
                  <div>
                    <p className="font-medium text-green-800">Proyecto Viable</p>
                    <p className="text-sm text-green-600">VAN positivo y TIR superior a la tasa de descuento</p>
                  </div>
                </>
              ) : (
                <>
                  <XCircle className="h-6 w-6 text-red-600" />
                  <div>
                    <p className="font-medium text-red-800">Proyecto No Viable</p>
                    <p className="text-sm text-red-600">El VAN es negativo o la TIR es inferior a la tasa de descuento</p>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function IndicatorCard({
  label,
  value,
  format,
  description,
  positive,
}: {
  label: string;
  value: number | null;
  format: "currency" | "percentage" | "number" | "months" | "score";
  description?: string;
  positive?: boolean;
}) {
  const formatValue = () => {
    if (value === null || value === undefined) return "N/A";
    switch (format) {
      case "currency":
        return formatCurrency(value);
      case "percentage":
        return formatPercentage(value);
      case "months":
        return `${value.toFixed(1)} meses`;
      case "score":
        return value.toString();
      default:
        return value.toFixed(2);
    }
  };

  const getColorClass = () => {
    if (positive === undefined) return "text-slate-900";
    if (format === "percentage" && positive === false && value !== null) {
      return value > 0.1 ? "text-red-600" : "text-green-600";
    }
    return positive ? "text-green-600" : "text-red-600";
  };

  return (
    <Card className="bg-white">
      <CardContent className="p-4 text-center">
        <p className={`text-lg font-bold ${value !== null && format === "currency" ? (value >= 0 ? "text-green-600" : "text-red-600") : getColorClass()}`}>
          {formatValue()}
        </p>
        <p className="text-sm font-medium">{label}</p>
        {description && (
          <p className="text-xs text-muted-foreground mt-1">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}
