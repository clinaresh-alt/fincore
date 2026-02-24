"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
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
        descripcion: `Mes ${newPeriod}`,
      },
    ]);
  };

  const removeCashFlowRow = (index: number) => {
    if (cashFlows.length > 1) {
      const newFlows = cashFlows.filter((_, i) => i !== index);
      setCashFlows(
        newFlows.map((f, i) => ({ ...f, periodo: i + 1, descripcion: `Mes ${i + 1}` }))
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

  const handleSubmit = async () => {
    // TODO: Enviar al backend
    alert("Proyecto guardado exitosamente");
    router.push("/projects");
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
                    <span className="text-sm text-muted-foreground">meses</span>
                  </div>
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
                          <span className="text-sm font-medium">Mes {cf.periodo}</span>
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
                        {evaluation.payback !== null ? `${evaluation.payback} meses` : "N/A"}
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

      {/* Navigation */}
      <div className="flex justify-between">
        <Button variant="outline" onClick={handleBack} disabled={currentStep === 1}>
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
            <Button onClick={handleSubmit} disabled={!evaluation?.es_viable}>
              <Check className="h-4 w-4 mr-2" />
              Guardar Proyecto
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
