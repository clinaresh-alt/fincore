"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { projectsAPI } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Building2,
  DollarSign,
  LineChart,
  BarChart3,
  ArrowLeft,
  ArrowRight,
  Check,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle2,
  Info,
  Upload,
  FileText,
  Sparkles,
  Loader2,
} from "lucide-react";
import { formatCurrency, formatPercentage } from "@/lib/utils";

// Tipos
interface ProjectBasicData {
  nombre: string;
  descripcion: string;
  sector: string;
  ubicacion: string;
  empresa_solicitante: string;
}

interface FinancialConfig {
  inversion_inicial: number;
  tasa_descuento: number;
  plazo_meses: number;
  tasa_rendimiento_esperado: number;
  tipo_periodo: "mensual" | "anual";
}

interface CashFlowRow {
  periodo: number;
  ingresos: number;
  costos: number;
  descripcion: string;
}

interface EvaluationResult {
  van: number;
  tir: number | null;
  roi: number;
  payback: number | null;
  indice_rentabilidad: number;
  es_viable: boolean;
  mensaje: string;
}

const sectors = [
  "Inmobiliario",
  "Tecnologia",
  "Energia",
  "Agrotech",
  "Fintech",
  "Industrial",
  "Comercio",
  "Servicios",
  "Infraestructura",
  "Otro",
];

// Indicadores extendidos por tipo de proyecto
const indicatorsByProjectType: Record<string, string[]> = {
  Inmobiliario: ["cap_rate", "precio_m2", "yield_bruto", "yield_neto", "loan_to_value", "debt_service_coverage"],
  Tecnologia: ["ltv_cac_ratio", "burn_rate", "runway_meses", "mrr", "arr", "churn_rate", "nps"],
  Energia: ["lcoe", "factor_capacidad", "ingresos_kwh", "costo_instalacion_kw", "vida_util_anos"],
  Agrotech: ["rendimiento_hectarea", "margen_bruto", "costo_produccion_ton", "punto_equilibrio"],
  Fintech: ["take_rate", "volumen_procesado", "costo_adquisicion", "lifetime_value", "default_rate"],
  Industrial: ["margen_operativo", "utilizacion_capacidad", "costo_unitario", "punto_equilibrio_unidades"],
  Comercio: ["ventas_m2", "margen_bruto", "rotacion_inventario", "ticket_promedio", "conversion_rate"],
  Infraestructura: ["eirr", "firr", "beneficio_costo_ratio", "trafico_proyectado", "tarifa_promedio"],
  Servicios: ["margen_operativo", "ticket_promedio", "rotacion_clientes", "costo_adquisicion"],
  Otro: [],
};

// Descripciones de indicadores
const indicatorDescriptions: Record<string, { name: string; description: string }> = {
  // Inmobiliario
  cap_rate: { name: "Cap Rate", description: "Tasa de capitalizacion" },
  precio_m2: { name: "Precio/m2", description: "Precio por metro cuadrado" },
  yield_bruto: { name: "Yield Bruto", description: "Rendimiento bruto anual" },
  yield_neto: { name: "Yield Neto", description: "Rendimiento neto anual" },
  loan_to_value: { name: "LTV", description: "Relacion prestamo/valor" },
  debt_service_coverage: { name: "DSCR", description: "Cobertura servicio de deuda" },
  // Tecnologia
  ltv_cac_ratio: { name: "LTV/CAC", description: "Ratio valor vida cliente / costo adquisicion" },
  burn_rate: { name: "Burn Rate", description: "Tasa de quema mensual" },
  runway_meses: { name: "Runway", description: "Meses de operacion con capital actual" },
  mrr: { name: "MRR", description: "Ingresos recurrentes mensuales" },
  arr: { name: "ARR", description: "Ingresos recurrentes anuales" },
  churn_rate: { name: "Churn", description: "Tasa de cancelacion de clientes" },
  nps: { name: "NPS", description: "Net Promoter Score" },
  // Energia
  lcoe: { name: "LCOE", description: "Costo nivelado de energia" },
  factor_capacidad: { name: "Factor Cap.", description: "Factor de capacidad de planta" },
  ingresos_kwh: { name: "$/kWh", description: "Ingresos por kilovatio-hora" },
  costo_instalacion_kw: { name: "$/kW inst.", description: "Costo de instalacion por kW" },
  vida_util_anos: { name: "Vida Util", description: "Anos de vida util del proyecto" },
  // Agrotech
  rendimiento_hectarea: { name: "Rend./Ha", description: "Rendimiento por hectarea" },
  margen_bruto: { name: "Margen Bruto", description: "Margen bruto operativo" },
  costo_produccion_ton: { name: "$/Ton", description: "Costo produccion por tonelada" },
  punto_equilibrio: { name: "Break-Even", description: "Punto de equilibrio" },
  // Fintech
  take_rate: { name: "Take Rate", description: "Porcentaje de comision por transaccion" },
  volumen_procesado: { name: "TPV", description: "Volumen total procesado" },
  costo_adquisicion: { name: "CAC", description: "Costo adquisicion de cliente" },
  lifetime_value: { name: "LTV", description: "Valor de vida del cliente" },
  default_rate: { name: "Default Rate", description: "Tasa de incumplimiento" },
  // Industrial
  margen_operativo: { name: "Margen Op.", description: "Margen operativo" },
  utilizacion_capacidad: { name: "Utilizacion", description: "Porcentaje uso capacidad instalada" },
  costo_unitario: { name: "Costo Unit.", description: "Costo por unidad producida" },
  punto_equilibrio_unidades: { name: "BE Units", description: "Unidades para punto equilibrio" },
  // Comercio
  ventas_m2: { name: "Ventas/m2", description: "Ventas por metro cuadrado" },
  rotacion_inventario: { name: "Rotacion Inv.", description: "Veces que rota inventario al ano" },
  ticket_promedio: { name: "Ticket Prom.", description: "Valor promedio por transaccion" },
  conversion_rate: { name: "Conv. Rate", description: "Tasa de conversion de visitas" },
  // Infraestructura
  eirr: { name: "EIRR", description: "Tasa retorno economica" },
  firr: { name: "FIRR", description: "Tasa retorno financiera" },
  beneficio_costo_ratio: { name: "B/C Ratio", description: "Relacion beneficio/costo" },
  trafico_proyectado: { name: "Trafico", description: "Usuarios/vehiculos proyectados" },
  tarifa_promedio: { name: "Tarifa Prom.", description: "Tarifa promedio por uso" },
  // Servicios
  rotacion_clientes: { name: "Rotacion", description: "Tasa de rotacion de clientes" },
};

const steps = [
  { id: 1, title: "Datos Basicos", icon: Building2 },
  { id: 2, title: "Configuracion Financiera", icon: DollarSign },
  { id: 3, title: "Proyecciones de Flujo", icon: LineChart },
  { id: 4, title: "Analisis de Sensibilidad", icon: BarChart3 },
];

export default function NewProjectPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(1);
  const [isCalculating, setIsCalculating] = useState(false);

  // Step 1: Datos basicos
  const [basicData, setBasicData] = useState<ProjectBasicData>({
    nombre: "",
    descripcion: "",
    sector: "Otro",
    ubicacion: "",
    empresa_solicitante: "",
  });

  // Step 2: Configuracion financiera
  const [financialConfig, setFinancialConfig] = useState<FinancialConfig>({
    inversion_inicial: 1000000,
    tasa_descuento: 0.12,
    plazo_meses: 24,
    tasa_rendimiento_esperado: 0.15,
    tipo_periodo: "mensual",
  });

  // Step 3: Flujos de caja
  const [cashFlows, setCashFlows] = useState<CashFlowRow[]>([
    { periodo: 1, ingresos: 150000, costos: 50000, descripcion: "Mes 1" },
    { periodo: 2, ingresos: 180000, costos: 50000, descripcion: "Mes 2" },
    { periodo: 3, ingresos: 200000, costos: 55000, descripcion: "Mes 3" },
    { periodo: 4, ingresos: 220000, costos: 55000, descripcion: "Mes 4" },
    { periodo: 5, ingresos: 250000, costos: 60000, descripcion: "Mes 5" },
    { periodo: 6, ingresos: 280000, costos: 60000, descripcion: "Mes 6" },
  ]);

  // Step 4: Resultados y sensibilidad
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null);
  const [sensitivityVar, setSensitivityVar] = useState(0.1);

  // PDF Upload y analisis IA
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [isAnalyzingPdf, setIsAnalyzingPdf] = useState(false);
  const [pdfAnalysisResult, setPdfAnalysisResult] = useState<any>(null);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [sectorIndicators, setSectorIndicators] = useState<string[]>([]);

  // Estado para valores de indicadores editables
  const [indicatorValues, setIndicatorValues] = useState<Record<string, number | string>>({});

  // Funcion para analizar PDF con IA
  const handlePdfUpload = async (file: File) => {
    setPdfFile(file);
    setPdfError(null);
    setIsAnalyzingPdf(true);

    try {
      const result = await projectsAPI.analyzeFeasibility(file);
      setPdfAnalysisResult(result);

      // Auto-llenar datos extraidos
      if (result.extracted_data) {
        const { basic, financial_config, cash_flows } = result.extracted_data;

        // Datos basicos
        setBasicData({
          nombre: basic.nombre || "",
          descripcion: basic.descripcion || "",
          sector: basic.sector || "Otro",
          ubicacion: basic.ubicacion || "",
          empresa_solicitante: basic.empresa_solicitante || "",
        });

        // Configuracion financiera
        setFinancialConfig({
          inversion_inicial: financial_config.inversion_inicial || 1000000,
          tasa_descuento: financial_config.tasa_descuento || 0.12,
          plazo_meses: financial_config.plazo_meses || 24,
          tasa_rendimiento_esperado: financial_config.tasa_rendimiento_esperado || 0.15,
          tipo_periodo: financial_config.tipo_periodo || "mensual",
        });

        // Flujos de caja
        if (cash_flows && cash_flows.length > 0) {
          setCashFlows(
            cash_flows.map((cf: any) => ({
              periodo: cf.periodo,
              ingresos: cf.ingresos,
              costos: cf.costos,
              descripcion: cf.descripcion || `Periodo ${cf.periodo}`,
            }))
          );
        }

        // Indicadores del sector
        setSectorIndicators(result.recommended_indicators || []);
      }
    } catch (error: any) {
      console.error("Error analizando PDF:", error);
      setPdfError(error.response?.data?.detail || "Error al analizar el documento");
    } finally {
      setIsAnalyzingPdf(false);
    }
  };

  // Helper para etiqueta de periodo
  const getPeriodoLabel = (num: number) =>
    financialConfig.tipo_periodo === "mensual" ? `Mes ${num}` : `Ano ${num}`;

  // Handlers
  const addCashFlowRow = () => {
    const newPeriod = cashFlows.length + 1;
    const lastRow = cashFlows[cashFlows.length - 1];
    setCashFlows([
      ...cashFlows,
      {
        periodo: newPeriod,
        ingresos: lastRow?.ingresos || 100000,
        costos: lastRow?.costos || 30000,
        descripcion: getPeriodoLabel(newPeriod),
      },
    ]);
  };

  const removeCashFlowRow = (index: number) => {
    if (cashFlows.length > 1) {
      const newFlows = cashFlows.filter((_, i) => i !== index);
      setCashFlows(
        newFlows.map((f, i) => ({ ...f, periodo: i + 1, descripcion: getPeriodoLabel(i + 1) }))
      );
    }
  };

  const updateCashFlow = (index: number, field: keyof CashFlowRow, value: number | string) => {
    const newFlows = [...cashFlows];
    newFlows[index] = { ...newFlows[index], [field]: value };
    setCashFlows(newFlows);
  };

  // Calculo local de indicadores (simplificado)
  const calculateEvaluation = () => {
    setIsCalculating(true);

    setTimeout(() => {
      const I0 = financialConfig.inversion_inicial;
      const k = financialConfig.tasa_descuento;

      // Calcular VAN
      let van = -I0;
      cashFlows.forEach((cf, t) => {
        const flujoNeto = cf.ingresos - cf.costos;
        van += flujoNeto / Math.pow(1 + k, t + 1);
      });

      // Calcular ROI
      const totalIngresos = cashFlows.reduce((sum, cf) => sum + cf.ingresos, 0);
      const totalCostos = cashFlows.reduce((sum, cf) => sum + cf.costos, 0);
      const roi = (totalIngresos - totalCostos - I0) / I0;

      // Payback (simplificado)
      let acumulado = 0;
      let payback: number | null = null;
      for (let t = 0; t < cashFlows.length; t++) {
        acumulado += cashFlows[t].ingresos - cashFlows[t].costos;
        if (acumulado >= I0 && payback === null) {
          payback = t + 1;
        }
      }

      // TIR aproximada
      let tir: number | null = null;
      for (let r = 0; r <= 1; r += 0.001) {
        let npv = -I0;
        cashFlows.forEach((cf, t) => {
          npv += (cf.ingresos - cf.costos) / Math.pow(1 + r, t + 1);
        });
        if (Math.abs(npv) < 1000) {
          tir = r;
          break;
        }
      }

      // Indice de rentabilidad
      const ir = van > 0 ? (van + I0) / I0 : 0;

      setEvaluation({
        van: Math.round(van * 100) / 100,
        tir,
        roi: Math.round(roi * 10000) / 10000,
        payback,
        indice_rentabilidad: Math.round(ir * 100) / 100,
        es_viable: van > 0 && (tir === null || tir > k),
        mensaje:
          van > 0
            ? "Proyecto VIABLE: VAN positivo"
            : "Proyecto NO VIABLE: VAN negativo",
      });

      setIsCalculating(false);
    }, 500);
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return basicData.nombre.length >= 3 && basicData.sector;
      case 2:
        return financialConfig.inversion_inicial > 0 && financialConfig.tasa_descuento > 0;
      case 3:
        return cashFlows.length > 0;
      default:
        return true;
    }
  };

  const handleNext = () => {
    if (currentStep === 3) {
      calculateEvaluation();
    }
    setCurrentStep(Math.min(currentStep + 1, 4));
  };

  const handleBack = () => {
    setCurrentStep(Math.max(currentStep - 1, 1));
  };

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setIsSaving(true);
    setSaveError(null);

    try {
      // Crear proyecto
      const projectResponse = await projectsAPI.create({
        nombre: basicData.nombre,
        descripcion: basicData.descripcion,
        sector: basicData.sector,
        monto_solicitado: financialConfig.inversion_inicial,
        plazo_meses: financialConfig.plazo_meses,
        tasa_rendimiento_anual: financialConfig.tasa_rendimiento_esperado,
      });

      // Si hay evaluacion, enviar los flujos de caja
      if (evaluation && projectResponse.id) {
        await projectsAPI.evaluate({
          proyecto_id: projectResponse.id,
          inversion_inicial: financialConfig.inversion_inicial,
          tasa_descuento: financialConfig.tasa_descuento,
          flujos_caja: cashFlows.map((cf) => ({
            periodo_nro: cf.periodo,
            monto_ingreso: cf.ingresos,
            monto_egreso: cf.costos,
          })),
        });
      }

      // Guardar indicadores del sector si hay valores
      const indicatorsToSave = Object.entries(indicatorValues).reduce((acc, [key, value]) => {
        if (value !== "" && value !== null && value !== undefined) {
          acc[key] = typeof value === 'string' ? parseFloat(value) : value;
        }
        return acc;
      }, {} as Record<string, number>);

      if (Object.keys(indicatorsToSave).length > 0 && projectResponse.id) {
        try {
          await projectsAPI.saveIndicators(projectResponse.id, indicatorsToSave);
        } catch (indicatorError) {
          console.warn("Error guardando indicadores:", indicatorError);
          // No fallar el guardado completo si fallan los indicadores
        }
      }

      alert("Proyecto guardado exitosamente");
      router.push("/projects");
    } catch (error: any) {
      console.error("Error guardando proyecto:", error);
      setSaveError(error.response?.data?.detail || "Error al guardar el proyecto");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => router.back()}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Volver
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Nuevo Proyecto</h1>
          <p className="text-muted-foreground">
            Complete el wizard para cargar y evaluar un proyecto
          </p>
        </div>
      </div>

      {/* Progress Steps */}
      <div className="flex items-center justify-between">
        {steps.map((step, index) => (
          <div key={step.id} className="flex items-center">
            <div
              className={`flex items-center justify-center h-10 w-10 rounded-full border-2 transition-colors ${
                currentStep >= step.id
                  ? "bg-primary border-primary text-white"
                  : "border-slate-300 text-slate-400"
              }`}
            >
              {currentStep > step.id ? (
                <Check className="h-5 w-5" />
              ) : (
                <step.icon className="h-5 w-5" />
              )}
            </div>
            <div className="ml-2 hidden sm:block">
              <p
                className={`text-sm font-medium ${
                  currentStep >= step.id ? "text-primary" : "text-slate-400"
                }`}
              >
                {step.title}
              </p>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`h-0.5 w-12 mx-4 ${
                  currentStep > step.id ? "bg-primary" : "bg-slate-200"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <Card>
        <CardContent className="p-6">
          {/* Step 1: Datos Basicos */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div>
                <CardTitle className="text-lg mb-1">Datos Basicos del Proyecto</CardTitle>
                <CardDescription>
                  Informacion general sobre el proyecto de inversion
                </CardDescription>
              </div>

              {/* PDF Upload con IA */}
              <div className="p-4 rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 hover:border-primary hover:bg-slate-100 transition-colors">
                <div className="flex flex-col items-center justify-center py-4">
                  {isAnalyzingPdf ? (
                    <>
                      <Loader2 className="h-10 w-10 text-primary animate-spin mb-3" />
                      <p className="text-sm font-medium text-slate-700">Analizando documento con IA...</p>
                      <p className="text-xs text-muted-foreground mt-1">Extrayendo datos del estudio de factibilidad</p>
                    </>
                  ) : pdfAnalysisResult ? (
                    <>
                      <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="h-6 w-6 text-green-600" />
                        <CheckCircle2 className="h-6 w-6 text-green-600" />
                      </div>
                      <p className="text-sm font-medium text-green-700">Documento analizado exitosamente</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {pdfFile?.name} - Confianza: {Math.round((pdfAnalysisResult.extraction_confidence || 0.8) * 100)}%
                      </p>
                      {pdfAnalysisResult.extraction_notes && (
                        <p className="text-xs text-amber-600 mt-2 text-center max-w-md">
                          {pdfAnalysisResult.extraction_notes}
                        </p>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-3"
                        onClick={() => {
                          setPdfFile(null);
                          setPdfAnalysisResult(null);
                        }}
                      >
                        Cargar otro documento
                      </Button>
                    </>
                  ) : (
                    <>
                      <div className="flex items-center gap-2 mb-3">
                        <Upload className="h-8 w-8 text-slate-400" />
                        <Sparkles className="h-6 w-6 text-primary" />
                      </div>
                      <p className="text-sm font-medium text-slate-700">Cargar Estudio de Factibilidad (PDF)</p>
                      <p className="text-xs text-muted-foreground mt-1 text-center max-w-sm">
                        Sube tu documento PDF y la IA extraera automaticamente los datos financieros del proyecto
                      </p>
                      <label className="mt-4 cursor-pointer">
                        <input
                          type="file"
                          accept=".pdf"
                          className="hidden"
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              handlePdfUpload(file);
                            }
                          }}
                        />
                        <span className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-white text-sm font-medium rounded-md hover:bg-primary/90 transition-colors">
                          <FileText className="h-4 w-4" />
                          Seleccionar PDF
                        </span>
                      </label>
                    </>
                  )}
                </div>

                {/* Error de PDF */}
                {pdfError && (
                  <div className="mt-3 p-3 rounded-md bg-red-50 border border-red-200">
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-red-600" />
                      <p className="text-sm text-red-700">{pdfError}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Separador */}
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white px-2 text-muted-foreground">O completa manualmente</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Nombre del Proyecto *</label>
                  <Input
                    value={basicData.nombre}
                    onChange={(e) => setBasicData({ ...basicData, nombre: e.target.value })}
                    placeholder="Ej: Plaza Comercial Centro"
                    className="mt-1"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Descripcion</label>
                  <textarea
                    value={basicData.descripcion}
                    onChange={(e) => setBasicData({ ...basicData, descripcion: e.target.value })}
                    placeholder="Descripcion detallada del proyecto..."
                    className="mt-1 w-full min-h-[100px] px-3 py-2 border rounded-md text-sm"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium">Sector *</label>
                  <select
                    value={basicData.sector}
                    onChange={(e) => setBasicData({ ...basicData, sector: e.target.value })}
                    className="mt-1 w-full px-3 py-2 border rounded-md text-sm"
                  >
                    {sectors.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="text-sm font-medium">Ubicacion</label>
                  <Input
                    value={basicData.ubicacion}
                    onChange={(e) => setBasicData({ ...basicData, ubicacion: e.target.value })}
                    placeholder="Ciudad, Estado"
                    className="mt-1"
                  />
                </div>

                <div className="md:col-span-2">
                  <label className="text-sm font-medium">Empresa Solicitante</label>
                  <Input
                    value={basicData.empresa_solicitante}
                    onChange={(e) =>
                      setBasicData({ ...basicData, empresa_solicitante: e.target.value })
                    }
                    placeholder="Nombre de la empresa"
                    className="mt-1"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Configuracion Financiera */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div>
                <CardTitle className="text-lg mb-1">Configuracion Financiera</CardTitle>
                <CardDescription>
                  Parametros para el calculo de indicadores financieros
                </CardDescription>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-4 rounded-lg border bg-slate-50">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <DollarSign className="h-4 w-4 text-primary" />
                    Inversion Inicial (I0)
                  </label>
                  <Input
                    type="number"
                    value={financialConfig.inversion_inicial}
                    onChange={(e) =>
                      setFinancialConfig({
                        ...financialConfig,
                        inversion_inicial: parseFloat(e.target.value) || 0,
                      })
                    }
                    className="mt-2"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Total de CAPEX y gastos pre-operativos
                  </p>
                </div>

                <div className="p-4 rounded-lg border bg-slate-50">
                  <label className="text-sm font-medium flex items-center gap-2">
                    <LineChart className="h-4 w-4 text-primary" />
                    Tasa de Descuento (k)
                  </label>
                  <div className="flex items-center gap-2 mt-2">
                    <Input
                      type="number"
                      step="0.01"
                      value={(financialConfig.tasa_descuento * 100).toFixed(0)}
                      onChange={(e) =>
                        setFinancialConfig({
                          ...financialConfig,
                          tasa_descuento: (parseFloat(e.target.value) || 0) / 100,
                        })
                      }
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">%</span>
                    <input
                      type="range"
                      min="5"
                      max="30"
                      value={financialConfig.tasa_descuento * 100}
                      onChange={(e) =>
                        setFinancialConfig({
                          ...financialConfig,
                          tasa_descuento: parseFloat(e.target.value) / 100,
                        })
                      }
                      className="flex-1"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    WACC o costo de oportunidad
                  </p>
                </div>

                <div className="p-4 rounded-lg border bg-slate-50">
                  <label className="text-sm font-medium">Plazo del Proyecto</label>
                  <div className="flex items-center gap-2 mt-2">
                    <Input
                      type="number"
                      value={financialConfig.plazo_meses}
                      onChange={(e) =>
                        setFinancialConfig({
                          ...financialConfig,
                          plazo_meses: parseInt(e.target.value) || 0,
                        })
                      }
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">
                      {financialConfig.tipo_periodo === "mensual" ? "meses" : "anos"}
                    </span>
                  </div>
                </div>

                <div className="p-4 rounded-lg border bg-slate-50">
                  <label className="text-sm font-medium">Tipo de Periodo</label>
                  <div className="flex items-center gap-4 mt-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="tipo_periodo"
                        value="mensual"
                        checked={financialConfig.tipo_periodo === "mensual"}
                        onChange={() =>
                          setFinancialConfig({
                            ...financialConfig,
                            tipo_periodo: "mensual",
                          })
                        }
                        className="w-4 h-4 text-primary"
                      />
                      <span className="text-sm">Mensual</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="radio"
                        name="tipo_periodo"
                        value="anual"
                        checked={financialConfig.tipo_periodo === "anual"}
                        onChange={() =>
                          setFinancialConfig({
                            ...financialConfig,
                            tipo_periodo: "anual",
                          })
                        }
                        className="w-4 h-4 text-primary"
                      />
                      <span className="text-sm">Anual</span>
                    </label>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Define si los flujos de caja son por mes o por ano
                  </p>
                </div>

                <div className="p-4 rounded-lg border bg-slate-50">
                  <label className="text-sm font-medium">Tasa de Rendimiento Esperado</label>
                  <div className="flex items-center gap-2 mt-2">
                    <Input
                      type="number"
                      step="0.01"
                      value={(financialConfig.tasa_rendimiento_esperado * 100).toFixed(0)}
                      onChange={(e) =>
                        setFinancialConfig({
                          ...financialConfig,
                          tasa_rendimiento_esperado: (parseFloat(e.target.value) || 0) / 100,
                        })
                      }
                      className="w-24"
                    />
                    <span className="text-sm text-muted-foreground">% anual</span>
                  </div>
                </div>
              </div>

              <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                <div className="flex items-start gap-3">
                  <Info className="h-5 w-5 text-blue-600 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-blue-800">Formula VAN</p>
                    <p className="text-xs text-blue-600 mt-1">
                      VAN = SUM(Ft / (1+k)^t) - I0, donde Ft son los flujos netos
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Step 3: Proyecciones de Flujo */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg mb-1">Proyecciones de Flujo de Caja</CardTitle>
                  <CardDescription>
                    Ingrese los flujos proyectados por periodo
                  </CardDescription>
                </div>
                <Button onClick={addCashFlowRow} size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  Agregar Periodo
                </Button>
              </div>

              <div className="border rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">
                        Periodo
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">
                        Ingresos
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">
                        Costos
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-slate-500">
                        Flujo Neto
                      </th>
                      <th className="px-4 py-3 w-10"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {cashFlows.map((cf, index) => (
                      <tr key={index} className="border-t">
                        <td className="px-4 py-2">
                          <span className="text-sm font-medium">{getPeriodoLabel(cf.periodo)}</span>
                        </td>
                        <td className="px-4 py-2">
                          <Input
                            type="number"
                            value={cf.ingresos}
                            onChange={(e) =>
                              updateCashFlow(index, "ingresos", parseFloat(e.target.value) || 0)
                            }
                            className="w-32"
                          />
                        </td>
                        <td className="px-4 py-2">
                          <Input
                            type="number"
                            value={cf.costos}
                            onChange={(e) =>
                              updateCashFlow(index, "costos", parseFloat(e.target.value) || 0)
                            }
                            className="w-32"
                          />
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`text-sm font-medium ${
                              cf.ingresos - cf.costos >= 0 ? "text-green-600" : "text-red-600"
                            }`}
                          >
                            {formatCurrency(cf.ingresos - cf.costos)}
                          </span>
                        </td>
                        <td className="px-4 py-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeCashFlowRow(index)}
                            disabled={cashFlows.length <= 1}
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-slate-50">
                    <tr className="border-t-2">
                      <td className="px-4 py-3 font-medium">Total</td>
                      <td className="px-4 py-3 font-medium text-green-600">
                        {formatCurrency(cashFlows.reduce((s, cf) => s + cf.ingresos, 0))}
                      </td>
                      <td className="px-4 py-3 font-medium text-red-600">
                        {formatCurrency(cashFlows.reduce((s, cf) => s + cf.costos, 0))}
                      </td>
                      <td className="px-4 py-3 font-bold">
                        {formatCurrency(
                          cashFlows.reduce((s, cf) => s + (cf.ingresos - cf.costos), 0)
                        )}
                      </td>
                      <td></td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}

          {/* Step 4: Analisis y Sensibilidad */}
          {currentStep === 4 && (
            <div className="space-y-6">
              <div>
                <CardTitle className="text-lg mb-1">Resultados y Analisis de Sensibilidad</CardTitle>
                <CardDescription>
                  Indicadores financieros calculados automaticamente
                </CardDescription>
              </div>

              {isCalculating ? (
                <div className="flex items-center justify-center py-12">
                  <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
                  <span className="ml-3 text-muted-foreground">Calculando indicadores...</span>
                </div>
              ) : evaluation ? (
                <>
                  {/* Resultado principal */}
                  <div
                    className={`p-6 rounded-lg border-2 ${
                      evaluation.es_viable
                        ? "bg-green-50 border-green-200"
                        : "bg-red-50 border-red-200"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      {evaluation.es_viable ? (
                        <CheckCircle2 className="h-8 w-8 text-green-600" />
                      ) : (
                        <AlertTriangle className="h-8 w-8 text-red-600" />
                      )}
                      <div>
                        <h3
                          className={`text-lg font-bold ${
                            evaluation.es_viable ? "text-green-800" : "text-red-800"
                          }`}
                        >
                          {evaluation.es_viable ? "Proyecto Viable" : "Proyecto No Viable"}
                        </h3>
                        <p
                          className={`text-sm ${
                            evaluation.es_viable ? "text-green-600" : "text-red-600"
                          }`}
                        >
                          {evaluation.mensaje}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* KPIs Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-4 rounded-lg border bg-white">
                      <p className="text-xs text-muted-foreground">VAN</p>
                      <p
                        className={`text-xl font-bold ${
                          evaluation.van >= 0 ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {formatCurrency(evaluation.van)}
                      </p>
                    </div>
                    <div className="p-4 rounded-lg border bg-white">
                      <p className="text-xs text-muted-foreground">TIR</p>
                      <p className="text-xl font-bold text-blue-600">
                        {evaluation.tir !== null ? formatPercentage(evaluation.tir) : "N/A"}
                      </p>
                    </div>
                    <div className="p-4 rounded-lg border bg-white">
                      <p className="text-xs text-muted-foreground">ROI</p>
                      <p className="text-xl font-bold text-purple-600">
                        {formatPercentage(evaluation.roi)}
                      </p>
                    </div>
                    <div className="p-4 rounded-lg border bg-white">
                      <p className="text-xs text-muted-foreground">Payback</p>
                      <p className="text-xl font-bold text-amber-600">
                        {evaluation.payback !== null
                          ? `${evaluation.payback} ${financialConfig.tipo_periodo === "mensual" ? "meses" : "anos"}`
                          : "N/A"}
                      </p>
                    </div>
                  </div>

                  {/* Slider de sensibilidad */}
                  <div className="p-4 rounded-lg border bg-slate-50">
                    <h4 className="text-sm font-medium mb-4">Analisis de Sensibilidad</h4>
                    <div className="flex items-center gap-4">
                      <span className="text-sm text-muted-foreground w-24">Variacion:</span>
                      <input
                        type="range"
                        min="0"
                        max="30"
                        value={sensitivityVar * 100}
                        onChange={(e) => setSensitivityVar(parseFloat(e.target.value) / 100)}
                        className="flex-1"
                      />
                      <span className="text-sm font-medium w-16">
                        +/- {(sensitivityVar * 100).toFixed(0)}%
                      </span>
                    </div>

                    {/* Escenarios */}
                    <div className="grid grid-cols-3 gap-4 mt-4">
                      <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-center">
                        <p className="text-xs text-red-600 font-medium">Pesimista</p>
                        <p className="text-lg font-bold text-red-700">
                          {formatCurrency(evaluation.van * (1 - sensitivityVar))}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-slate-100 border border-slate-200 text-center">
                        <p className="text-xs text-slate-600 font-medium">Base</p>
                        <p className="text-lg font-bold text-slate-700">
                          {formatCurrency(evaluation.van)}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-center">
                        <p className="text-xs text-green-600 font-medium">Optimista</p>
                        <p className="text-lg font-bold text-green-700">
                          {formatCurrency(evaluation.van * (1 + sensitivityVar))}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Indice de Rentabilidad */}
                  <div className="p-4 rounded-lg border">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium">Indice de Rentabilidad (PI)</p>
                        <p className="text-xs text-muted-foreground">
                          Si PI {">"} 1, el proyecto es rentable
                        </p>
                      </div>
                      <div className="text-right">
                        <p
                          className={`text-2xl font-bold ${
                            evaluation.indice_rentabilidad >= 1
                              ? "text-green-600"
                              : "text-red-600"
                          }`}
                        >
                          {evaluation.indice_rentabilidad.toFixed(2)}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Indicadores Extendidos por Sector - Editables */}
                  {indicatorsByProjectType[basicData.sector]?.length > 0 && (
                    <div className="p-4 rounded-lg border bg-gradient-to-r from-blue-50 to-indigo-50">
                      <div className="flex items-center gap-2 mb-4">
                        <Sparkles className="h-5 w-5 text-indigo-600" />
                        <h4 className="text-sm font-medium text-indigo-900">
                          Indicadores Especificos - Sector {basicData.sector}
                        </h4>
                      </div>
                      <p className="text-xs text-muted-foreground mb-4">
                        Ingrese las metricas relevantes para evaluar proyectos de tipo {basicData.sector.toLowerCase()}
                      </p>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                        {indicatorsByProjectType[basicData.sector].map((indicatorKey) => {
                          const indicator = indicatorDescriptions[indicatorKey];
                          if (!indicator) return null;
                          const isPercentage = indicatorKey.includes('rate') || indicatorKey.includes('ratio') || indicatorKey.includes('yield') || indicatorKey.includes('margen') || indicatorKey.includes('conversion') || indicatorKey.includes('utilizacion') || indicatorKey.includes('factor') || indicatorKey === 'ltv_cac_ratio';
                          const isInteger = indicatorKey.includes('meses') || indicatorKey.includes('anos') || indicatorKey.includes('unidades') || indicatorKey === 'nps' || indicatorKey === 'trafico_proyectado';
                          return (
                            <div
                              key={indicatorKey}
                              className="p-3 rounded-lg bg-white border border-indigo-100"
                            >
                              <label className="text-xs font-medium text-indigo-700">{indicator.name}</label>
                              <p className="text-[10px] text-muted-foreground mt-0.5 mb-2">
                                {indicator.description}
                              </p>
                              <div className="flex items-center gap-1">
                                <Input
                                  type="number"
                                  step={isPercentage ? "0.01" : isInteger ? "1" : "0.01"}
                                  placeholder={isPercentage ? "0.00" : "0"}
                                  value={indicatorValues[indicatorKey] ?? (pdfAnalysisResult?.extracted_data?.additional_data?.[indicatorKey] || "")}
                                  onChange={(e) => setIndicatorValues({
                                    ...indicatorValues,
                                    [indicatorKey]: e.target.value === "" ? "" : parseFloat(e.target.value)
                                  })}
                                  className="h-8 text-sm"
                                />
                                {isPercentage && <span className="text-xs text-muted-foreground">%</span>}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <p className="text-xs text-blue-600 mt-3 flex items-center gap-1">
                        <Info className="h-3 w-3" />
                        Estos indicadores se guardaran junto con el proyecto
                      </p>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12 text-muted-foreground">
                  Haga clic en "Siguiente" para calcular los indicadores
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error message */}
      {saveError && (
        <div className="p-4 rounded-lg bg-red-50 border border-red-200">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-5 w-5 text-red-600" />
            <p className="text-sm text-red-700">{saveError}</p>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={handleBack} disabled={currentStep === 1 || isSaving}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Anterior
        </Button>
        <div className="flex gap-2">
          {currentStep < 4 ? (
            <Button onClick={handleNext} disabled={!canProceed()}>
              Siguiente
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} disabled={!evaluation?.es_viable || isSaving}>
              {isSaving ? (
                <>
                  <div className="h-4 w-4 mr-2 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  Guardando...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Guardar Proyecto
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
