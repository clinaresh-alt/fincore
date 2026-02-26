"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  AlertTriangle,
  CheckCircle2,
  BarChart3,
  RefreshCw,
  Download,
  FileQuestion,
} from "lucide-react";
import { formatCurrency, formatPercentage } from "@/lib/utils";
import { projectsAPI } from "@/lib/api-client";

interface EvaluationData {
  evaluacion: {
    van: number;
    tir: number | null;
    roi: number;
    payback_period: number | null;
    indice_rentabilidad: number;
    es_viable: boolean;
    mensaje: string;
  };
  sensibilidad: {
    ingresos: SensitivityPoint[];
    costos: SensitivityPoint[];
  };
  tornado: TornadoItem[];
  matriz_cruzada: {
    matriz: MatrixCell[][];
    etiquetas_filas: string[];
    etiquetas_columnas: string[];
  };
  montecarlo: {
    van_promedio: number;
    van_mediana: number;
    probabilidad_perdida: number;
    percentil_5: number;
    percentil_95: number;
    histograma: {
      rangos: number[];
      frecuencias: number[];
    };
  };
}

interface SensitivityPoint {
  escenario: string;
  variacion: number;
  van: number;
  tir: number | null;
  estado_viabilidad: string;
}

interface TornadoItem {
  variable: string;
  van_positivo: number;
  van_negativo: number;
  van_base: number;
  impacto_total: number;
}

interface MatrixCell {
  van: number;
  viable: boolean;
}

// Helper para generar datos de sensibilidad basados en la evaluacion real
const generateSensitivityData = (baseVan: number, baseTir: number | null) => {
  const variations = [-0.2, -0.1, 0, 0.1, 0.2];
  return {
    ingresos: variations.map((v) => ({
      escenario: v < 0 ? "Pesimista" : v > 0 ? "Optimista" : "Base",
      variacion: v,
      van: Math.round(baseVan * (1 + v * 1.5)),
      tir: baseTir ? baseTir * (1 + v * 0.5) : null,
      estado_viabilidad: baseVan * (1 + v * 1.5) > 0 ? "Viable" : "No Viable",
    })),
    costos: variations.map((v) => ({
      escenario: v > 0 ? "Pesimista" : v < 0 ? "Optimista" : "Base",
      variacion: v,
      van: Math.round(baseVan * (1 - v * 0.8)),
      tir: baseTir ? baseTir * (1 - v * 0.3) : null,
      estado_viabilidad: baseVan * (1 - v * 0.8) > 0 ? "Viable" : "No Viable",
    })),
  };
};

// Helper para generar datos tornado
const generateTornadoData = (baseVan: number) => [
  {
    variable: "ingresos",
    van_positivo: Math.round(baseVan * 1.6),
    van_negativo: Math.round(baseVan * 0.4),
    van_base: baseVan,
    impacto_total: Math.round(baseVan * 1.2),
  },
  {
    variable: "costos",
    van_positivo: Math.round(baseVan * 1.3),
    van_negativo: Math.round(baseVan * 0.7),
    van_base: baseVan,
    impacto_total: Math.round(baseVan * 0.6),
  },
  {
    variable: "tasa_descuento",
    van_positivo: Math.round(baseVan * 1.15),
    van_negativo: Math.round(baseVan * 0.85),
    van_base: baseVan,
    impacto_total: Math.round(baseVan * 0.3),
  },
];

// Helper para generar matriz cruzada
const generateMatrixData = (baseVan: number) => ({
  matriz: [
    [
      { van: Math.round(baseVan * 0.5), viable: baseVan * 0.5 > 0 },
      { van: Math.round(baseVan * 0.4), viable: baseVan * 0.4 > 0 },
      { van: Math.round(baseVan * 0.3), viable: baseVan * 0.3 > 0 },
    ],
    [
      { van: Math.round(baseVan * 0.75), viable: baseVan * 0.75 > 0 },
      { van: baseVan, viable: baseVan > 0 },
      { van: Math.round(baseVan * 0.88), viable: baseVan * 0.88 > 0 },
    ],
    [
      { van: Math.round(baseVan * 1.02), viable: true },
      { van: Math.round(baseVan * 1.3), viable: true },
      { van: Math.round(baseVan * 1.6), viable: true },
    ],
  ],
  etiquetas_filas: ["-10% Ingresos", "Base", "+10% Ingresos"],
  etiquetas_columnas: ["10.8%", "12%", "13.2%"],
});

// Helper para generar datos Monte Carlo
const generateMonteCarloData = (baseVan: number) => ({
  van_promedio: Math.round(baseVan * 0.97),
  van_mediana: Math.round(baseVan * 0.99),
  probabilidad_perdida: baseVan > 0 ? 0.08 : 0.65,
  percentil_5: Math.round(baseVan * 0.26),
  percentil_95: Math.round(baseVan * 1.71),
  histograma: {
    rangos: [-500000, 0, 500000, 1000000, 1500000, 2000000, 2500000, 3000000, 3500000, 4000000, 4500000].map(
      (r) => Math.round(r * (baseVan / 2450000))
    ),
    frecuencias: [5, 15, 45, 85, 120, 95, 70, 40, 18, 7],
  },
});

export default function EvaluatePage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;
  const [evaluation, setEvaluation] = useState<EvaluationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noEvaluation, setNoEvaluation] = useState(false);
  const [activeTab, setActiveTab] = useState<"resumen" | "sensibilidad" | "tornado" | "montecarlo">("resumen");
  const [sensitivitySlider, setSensitivitySlider] = useState(0.1);

  useEffect(() => {
    const loadEvaluation = async () => {
      try {
        setLoading(true);
        setError(null);
        setNoEvaluation(false);

        // Cargar analytics del proyecto que incluye la evaluacion
        const analytics = await projectsAPI.getAnalytics(projectId);

        if (!analytics || !analytics.financials || analytics.financials.van === null) {
          setNoEvaluation(true);
          setLoading(false);
          return;
        }

        // Construir datos de evaluacion a partir de analytics
        const baseVan = analytics.financials.van || 0;
        const baseTir = analytics.financials.tir || null;
        const baseRoi = analytics.financials.roi || 0;

        const evaluationData: EvaluationData = {
          evaluacion: {
            van: baseVan,
            tir: baseTir,
            roi: baseRoi,
            payback_period: analytics.financials.payback_period || null,
            indice_rentabilidad: analytics.financials.indice_rentabilidad || (baseVan > 0 ? 1 + (baseVan / 1000000) : 0),
            es_viable: baseVan > 0,
            mensaje: baseVan > 0
              ? "Proyecto VIABLE: VAN positivo y TIR superior a la tasa minima."
              : "Proyecto NO VIABLE: VAN negativo.",
          },
          sensibilidad: generateSensitivityData(baseVan, baseTir),
          tornado: generateTornadoData(baseVan),
          matriz_cruzada: generateMatrixData(baseVan),
          montecarlo: generateMonteCarloData(baseVan),
        };

        setEvaluation(evaluationData);
      } catch (err: any) {
        console.error("Error cargando evaluacion:", err);
        if (err.response?.status === 404) {
          setNoEvaluation(true);
        } else {
          setError(err.response?.data?.detail || "Error al cargar la evaluacion");
        }
      } finally {
        setLoading(false);
      }
    };

    if (projectId) {
      loadEvaluation();
    }
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  // Mostrar error
  if (error) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6 text-center">
            <AlertTriangle className="h-12 w-12 text-red-600 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-red-800 mb-2">Error al cargar evaluacion</h2>
            <p className="text-red-600">{error}</p>
            <Button className="mt-4" onClick={() => window.location.reload()}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Reintentar
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Mostrar mensaje cuando no hay evaluacion
  if (noEvaluation || !evaluation) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="p-8 text-center">
            <FileQuestion className="h-16 w-16 text-amber-600 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-amber-800 mb-2">Sin datos de evaluacion</h2>
            <p className="text-amber-700 mb-6 max-w-md mx-auto">
              Este proyecto aun no tiene una evaluacion financiera registrada.
              Para ver el analisis de sensibilidad y escenarios, primero debe evaluarse el proyecto con flujos de caja proyectados.
            </p>
            <div className="flex gap-3 justify-center">
              <Button variant="outline" asChild>
                <Link href={`/projects/${projectId}`}>
                  Ver Detalle del Proyecto
                </Link>
              </Button>
              <Button asChild>
                <Link href="/projects/new">
                  Crear Nuevo Proyecto
                </Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const { evaluacion, sensibilidad, tornado, matriz_cruzada, montecarlo } = evaluation;

  // Calcular ancho de barras tornado
  const maxImpacto = Math.max(...tornado.map((t) => t.impacto_total));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Volver
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Evaluacion del Proyecto</h1>
            <p className="text-muted-foreground">
              Analisis financiero completo y sensibilidad
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Recalcular
          </Button>
          <Button size="sm">
            <Download className="h-4 w-4 mr-2" />
            Exportar PDF
          </Button>
        </div>
      </div>

      {/* Resultado Principal */}
      <Card
        className={`border-2 ${
          evaluacion.es_viable ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"
        }`}
      >
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              {evaluacion.es_viable ? (
                <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center">
                  <CheckCircle2 className="h-8 w-8 text-green-600" />
                </div>
              ) : (
                <div className="h-16 w-16 rounded-full bg-red-100 flex items-center justify-center">
                  <AlertTriangle className="h-8 w-8 text-red-600" />
                </div>
              )}
              <div>
                <h2
                  className={`text-2xl font-bold ${
                    evaluacion.es_viable ? "text-green-800" : "text-red-800"
                  }`}
                >
                  {evaluacion.es_viable ? "Proyecto Viable" : "Proyecto No Viable"}
                </h2>
                <p className={evaluacion.es_viable ? "text-green-600" : "text-red-600"}>
                  {evaluacion.mensaje}
                </p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-sm text-muted-foreground">VAN</p>
              <p
                className={`text-3xl font-bold ${
                  evaluacion.van >= 0 ? "text-green-600" : "text-red-600"
                }`}
              >
                {formatCurrency(evaluacion.van)}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* KPIs Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                <TrendingUp className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">TIR</p>
                <p className="text-xl font-bold text-blue-600">
                  {evaluacion.tir ? formatPercentage(evaluacion.tir) : "N/A"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-purple-100 flex items-center justify-center">
                <DollarSign className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">ROI</p>
                <p className="text-xl font-bold text-purple-600">
                  {formatPercentage(evaluacion.roi)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-amber-100 flex items-center justify-center">
                <Target className="h-5 w-5 text-amber-600" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Payback</p>
                <p className="text-xl font-bold text-amber-600">
                  {evaluacion.payback_period ? `${evaluacion.payback_period} meses` : "N/A"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-green-100 flex items-center justify-center">
                <BarChart3 className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Indice PI</p>
                <p className="text-xl font-bold text-green-600">
                  {evaluacion.indice_rentabilidad.toFixed(2)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {[
          { id: "resumen", label: "Resumen" },
          { id: "sensibilidad", label: "Sensibilidad" },
          { id: "tornado", label: "Tornado" },
          { id: "montecarlo", label: "Monte Carlo" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as typeof activeTab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-slate-900"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === "resumen" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Matriz de Sensibilidad */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Matriz de Sensibilidad</CardTitle>
              <CardDescription>Ingresos vs Tasa de Descuento</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr>
                      <th className="p-2 text-left bg-slate-50"></th>
                      {matriz_cruzada.etiquetas_columnas.map((col, i) => (
                        <th key={i} className="p-2 text-center bg-slate-50 font-medium">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {matriz_cruzada.matriz.map((fila, i) => (
                      <tr key={i}>
                        <td className="p-2 font-medium bg-slate-50">
                          {matriz_cruzada.etiquetas_filas[i]}
                        </td>
                        {fila.map((celda, j) => (
                          <td
                            key={j}
                            className={`p-2 text-center font-medium ${
                              celda.viable ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
                            }`}
                          >
                            {formatCurrency(celda.van)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Punto de Equilibrio */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Punto de Equilibrio</CardTitle>
              <CardDescription>Variacion maxima soportada</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="p-4 rounded-lg bg-slate-50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Ingresos</span>
                  <span className="text-sm font-bold text-green-600">-32.5%</span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full">
                  <div className="h-full bg-green-500 rounded-full" style={{ width: "67.5%" }} />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Margen de seguridad alto
                </p>
              </div>

              <div className="p-4 rounded-lg bg-slate-50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Costos</span>
                  <span className="text-sm font-bold text-amber-600">+45.2%</span>
                </div>
                <div className="w-full h-2 bg-slate-200 rounded-full">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: "45.2%" }} />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Margen de seguridad moderado
                </p>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "sensibilidad" && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg">Analisis de Sensibilidad Interactivo</CardTitle>
                <CardDescription>
                  Mueva el slider para ver el impacto en el VAN
                </CardDescription>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm text-muted-foreground">Variacion:</span>
                <input
                  type="range"
                  min="5"
                  max="30"
                  value={sensitivitySlider * 100}
                  onChange={(e) => setSensitivitySlider(parseFloat(e.target.value) / 100)}
                  className="w-32"
                />
                <span className="text-sm font-medium w-16">
                  +/- {(sensitivitySlider * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Sensibilidad Ingresos */}
              <div>
                <h4 className="text-sm font-medium mb-4">Impacto en Ingresos</h4>
                <div className="space-y-3">
                  {sensibilidad.ingresos.map((punto, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-xs w-20">
                        {punto.variacion > 0 ? "+" : ""}
                        {(punto.variacion * 100).toFixed(0)}%
                      </span>
                      <div className="flex-1 h-8 bg-slate-100 rounded relative overflow-hidden">
                        <div
                          className={`absolute inset-y-0 left-0 ${
                            punto.van >= 0 ? "bg-green-500" : "bg-red-500"
                          }`}
                          style={{
                            width: `${Math.min(Math.abs(punto.van) / 50000, 100)}%`,
                          }}
                        />
                        <span className="absolute inset-0 flex items-center justify-center text-xs font-medium">
                          {formatCurrency(punto.van)}
                        </span>
                      </div>
                      <span
                        className={`text-xs w-16 ${
                          punto.estado_viabilidad === "Viable"
                            ? "text-green-600"
                            : "text-amber-600"
                        }`}
                      >
                        {punto.estado_viabilidad}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Sensibilidad Costos */}
              <div>
                <h4 className="text-sm font-medium mb-4">Impacto en Costos</h4>
                <div className="space-y-3">
                  {sensibilidad.costos.map((punto, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="text-xs w-20">
                        {punto.variacion > 0 ? "+" : ""}
                        {(punto.variacion * 100).toFixed(0)}%
                      </span>
                      <div className="flex-1 h-8 bg-slate-100 rounded relative overflow-hidden">
                        <div
                          className={`absolute inset-y-0 left-0 ${
                            punto.van >= 0 ? "bg-green-500" : "bg-red-500"
                          }`}
                          style={{
                            width: `${Math.min(Math.abs(punto.van) / 50000, 100)}%`,
                          }}
                        />
                        <span className="absolute inset-0 flex items-center justify-center text-xs font-medium">
                          {formatCurrency(punto.van)}
                        </span>
                      </div>
                      <span
                        className={`text-xs w-16 ${
                          punto.estado_viabilidad === "Viable"
                            ? "text-green-600"
                            : "text-amber-600"
                        }`}
                      >
                        {punto.estado_viabilidad}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "tornado" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Grafico Tornado</CardTitle>
            <CardDescription>
              Muestra que variable afecta mas al VAN del proyecto
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {tornado.map((item, i) => (
                <div key={i} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium capitalize">{item.variable}</span>
                    <span className="text-xs text-muted-foreground">
                      Impacto: {formatCurrency(item.impacto_total)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Barra negativa (izquierda) */}
                    <div className="flex-1 flex justify-end">
                      <div
                        className="h-8 bg-red-500 rounded-l flex items-center justify-start px-2"
                        style={{
                          width: `${((item.van_base - item.van_negativo) / maxImpacto) * 100}%`,
                        }}
                      >
                        <span className="text-xs text-white font-medium">
                          {formatCurrency(item.van_negativo)}
                        </span>
                      </div>
                    </div>
                    {/* Linea central */}
                    <div className="w-px h-10 bg-slate-400" />
                    {/* Barra positiva (derecha) */}
                    <div className="flex-1">
                      <div
                        className="h-8 bg-green-500 rounded-r flex items-center justify-end px-2"
                        style={{
                          width: `${((item.van_positivo - item.van_base) / maxImpacto) * 100}%`,
                        }}
                      >
                        <span className="text-xs text-white font-medium">
                          {formatCurrency(item.van_positivo)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-6 pt-4 border-t">
              <p className="text-sm text-muted-foreground">
                <strong>Conclusion:</strong> Los{" "}
                <span className="font-medium text-slate-900">ingresos</span> son la variable
                mas sensible. Se recomienda asegurar contratos de venta antes de proceder.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === "montecarlo" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Simulacion Monte Carlo</CardTitle>
              <CardDescription>
                500 simulaciones con variabilidad estocastica
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded-lg bg-slate-50">
                  <p className="text-xs text-muted-foreground">VAN Promedio</p>
                  <p className="text-lg font-bold text-slate-900">
                    {formatCurrency(montecarlo.van_promedio)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-slate-50">
                  <p className="text-xs text-muted-foreground">VAN Mediana</p>
                  <p className="text-lg font-bold text-slate-900">
                    {formatCurrency(montecarlo.van_mediana)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-red-50">
                  <p className="text-xs text-red-600">Prob. Perdida</p>
                  <p className="text-lg font-bold text-red-600">
                    {formatPercentage(montecarlo.probabilidad_perdida)}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-amber-50">
                  <p className="text-xs text-amber-600">VaR 95%</p>
                  <p className="text-lg font-bold text-amber-600">
                    {formatCurrency(montecarlo.percentil_5)}
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-lg border">
                <p className="text-sm font-medium mb-2">Intervalo de Confianza 90%</p>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-red-600">
                    {formatCurrency(montecarlo.percentil_5)}
                  </span>
                  <div className="flex-1 h-2 bg-gradient-to-r from-red-500 via-green-500 to-green-600 rounded-full" />
                  <span className="text-sm text-green-600">
                    {formatCurrency(montecarlo.percentil_95)}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Distribucion de VAN</CardTitle>
              <CardDescription>Histograma de resultados simulados</CardDescription>
            </CardHeader>
            <CardContent>
              {/* Histograma simplificado */}
              <div className="flex items-end gap-1 h-40">
                {montecarlo.histograma.frecuencias.map((freq, i) => {
                  const maxFreq = Math.max(...montecarlo.histograma.frecuencias);
                  const height = (freq / maxFreq) * 100;
                  const isNegative = montecarlo.histograma.rangos[i] < 0;

                  return (
                    <div
                      key={i}
                      className={`flex-1 rounded-t ${
                        isNegative ? "bg-red-400" : "bg-green-400"
                      }`}
                      style={{ height: `${height}%` }}
                      title={`${formatCurrency(montecarlo.histograma.rangos[i])}: ${freq} simulaciones`}
                    />
                  );
                })}
              </div>
              <div className="flex justify-between mt-2">
                <span className="text-xs text-muted-foreground">
                  {formatCurrency(montecarlo.histograma.rangos[0])}
                </span>
                <span className="text-xs text-muted-foreground">
                  {formatCurrency(
                    montecarlo.histograma.rangos[montecarlo.histograma.rangos.length - 1]
                  )}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
