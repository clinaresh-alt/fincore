"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
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
} from "lucide-react";
import { formatCurrency, formatPercentage } from "@/lib/utils";

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

// Datos de ejemplo para demo
const mockEvaluation: EvaluationData = {
  evaluacion: {
    van: 2450000,
    tir: 0.2347,
    roi: 0.4520,
    payback_period: 18.5,
    indice_rentabilidad: 1.49,
    es_viable: true,
    mensaje: "Proyecto VIABLE: VAN positivo y TIR superior a la tasa minima.",
  },
  sensibilidad: {
    ingresos: [
      { escenario: "Pesimista", variacion: -0.2, van: 980000, tir: 0.12, estado_viabilidad: "Riesgo Moderado" },
      { escenario: "Pesimista", variacion: -0.1, van: 1715000, tir: 0.18, estado_viabilidad: "Viable" },
      { escenario: "Base", variacion: 0, van: 2450000, tir: 0.2347, estado_viabilidad: "Viable" },
      { escenario: "Optimista", variacion: 0.1, van: 3185000, tir: 0.29, estado_viabilidad: "Viable" },
      { escenario: "Optimista", variacion: 0.2, van: 3920000, tir: 0.34, estado_viabilidad: "Viable" },
    ],
    costos: [
      { escenario: "Optimista", variacion: -0.2, van: 3100000, tir: 0.28, estado_viabilidad: "Viable" },
      { escenario: "Optimista", variacion: -0.1, van: 2775000, tir: 0.26, estado_viabilidad: "Viable" },
      { escenario: "Base", variacion: 0, van: 2450000, tir: 0.2347, estado_viabilidad: "Viable" },
      { escenario: "Pesimista", variacion: 0.1, van: 2125000, tir: 0.21, estado_viabilidad: "Viable" },
      { escenario: "Pesimista", variacion: 0.2, van: 1800000, tir: 0.18, estado_viabilidad: "Riesgo Moderado" },
    ],
  },
  tornado: [
    { variable: "ingresos", van_positivo: 3920000, van_negativo: 980000, van_base: 2450000, impacto_total: 2940000 },
    { variable: "costos", van_positivo: 3100000, van_negativo: 1800000, van_base: 2450000, impacto_total: 1300000 },
    { variable: "tasa_descuento", van_positivo: 2800000, van_negativo: 2100000, van_base: 2450000, impacto_total: 700000 },
  ],
  matriz_cruzada: {
    matriz: [
      [{ van: 1200000, viable: true }, { van: 980000, viable: true }, { van: 760000, viable: true }],
      [{ van: 1850000, viable: true }, { van: 2450000, viable: true }, { van: 2150000, viable: true }],
      [{ van: 2500000, viable: true }, { van: 3185000, viable: true }, { van: 3920000, viable: true }],
    ],
    etiquetas_filas: ["-10% Ingresos", "Base", "+10% Ingresos"],
    etiquetas_columnas: ["10.8%", "12%", "13.2%"],
  },
  montecarlo: {
    van_promedio: 2380000,
    van_mediana: 2420000,
    probabilidad_perdida: 0.08,
    percentil_5: 650000,
    percentil_95: 4200000,
    histograma: {
      rangos: [-500000, 0, 500000, 1000000, 1500000, 2000000, 2500000, 3000000, 3500000, 4000000, 4500000],
      frecuencias: [5, 15, 45, 85, 120, 95, 70, 40, 18, 7],
    },
  },
};

export default function EvaluatePage() {
  const params = useParams();
  const router = useRouter();
  const [evaluation, setEvaluation] = useState<EvaluationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"resumen" | "sensibilidad" | "tornado" | "montecarlo">("resumen");
  const [sensitivitySlider, setSensitivitySlider] = useState(0.1);

  useEffect(() => {
    // Simular carga de datos
    setTimeout(() => {
      setEvaluation(mockEvaluation);
      setLoading(false);
    }, 1000);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    );
  }

  if (!evaluation) return null;

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
