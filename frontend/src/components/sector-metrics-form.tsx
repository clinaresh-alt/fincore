"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiClient } from "@/lib/api-client";
import {
  Calculator,
  Save,
  Loader2,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  TrendingUp,
  Info,
} from "lucide-react";

interface FieldConfig {
  label: string;
  type: "integer" | "decimal" | "percentage";
  required: boolean;
}

interface SectorFields {
  sector: string;
  fields: Record<string, FieldConfig>;
  calculated_indicators: string[];
}

interface SectorMetricsData {
  id?: string;
  proyecto_id: string;
  sector: string;
  input_data: Record<string, number | null>;
  calculated_indicators: Record<string, number | string | null>;
  calculated_at?: string;
}

interface SectorMetricsFormProps {
  projectId: string;
  sector: string;
  projectName: string;
  onSaved?: () => void;
}

const indicatorLabels: Record<string, string> = {
  // Tecnologia
  ltv_cac_ratio: "Ratio LTV/CAC",
  burn_rate: "Tasa de Quema Mensual",
  runway_meses: "Runway (meses)",
  mrr: "MRR",
  arr: "ARR",
  churn_rate: "Churn Rate",
  arpu: "ARPU",
  nps: "NPS Score",
  crecimiento_usuarios: "Crecimiento Usuarios",

  // Inmobiliario
  cap_rate: "Cap Rate",
  yield_bruto: "Yield Bruto",
  yield_neto: "Yield Neto",
  noi: "NOI",
  loan_to_value: "Loan to Value",
  precio_m2: "Precio por M2",
  ocupacion: "Ocupacion",

  // Energia
  lcoe: "LCOE ($/kWh)",
  factor_capacidad: "Factor de Capacidad",
  produccion_anual: "Produccion Anual (kWh)",
  roi_energia: "ROI Energia",
  payback_energia: "Payback (anos)",
  ingresos_anuales: "Ingresos Anuales",

  // Fintech
  take_rate: "Take Rate",
  volumen_procesado: "Volumen Procesado",
  default_rate: "Default Rate",
  spread: "Spread",
  cartera_neta: "Cartera Neta",

  // Industrial
  utilizacion_capacidad: "Utilizacion Capacidad",
  margen_operativo: "Margen Operativo",
  margen_contribucion: "Margen Contribucion",
  punto_equilibrio_unidades: "Punto Equilibrio",
  costo_unitario: "Costo Unitario",
  rotacion_inventario: "Rotacion Inventario",

  // Comercio
  ventas_m2: "Ventas por M2",
  margen_bruto: "Margen Bruto",
  ticket_promedio: "Ticket Promedio",
  conversion_rate: "Conversion Rate",
  punto_equilibrio: "Punto Equilibrio",

  // Agrotech
  rendimiento_hectarea: "Rendimiento/Ha",
  ingreso_por_hectarea: "Ingreso/Ha",
  costo_produccion_ton: "Costo/Ton",
  produccion_total: "Produccion Total",
  ingreso_bruto: "Ingreso Bruto",

  // Infraestructura
  ingresos_diarios: "Ingresos Diarios",
  ingresos_anuales_infra: "Ingresos Anuales",
  margen_operativo_infra: "Margen Operativo",
  payback_anos: "Payback (anos)",
  roi_anual: "ROI Anual",
  beneficio_costo: "Beneficio/Costo",
};

export function SectorMetricsForm({
  projectId,
  sector,
  projectName,
  onSaved,
}: SectorMetricsFormProps) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [sectorFields, setSectorFields] = useState<SectorFields | null>(null);
  const [formData, setFormData] = useState<Record<string, string>>({});
  const [calculatedIndicators, setCalculatedIndicators] = useState<Record<string, number | string | null>>({});
  const [existingData, setExistingData] = useState<SectorMetricsData | null>(null);

  // Load sector fields and existing data
  useEffect(() => {
    loadData();
  }, [projectId, sector]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Load sector fields
      const fieldsResponse = await apiClient.get(`/sector-metrics/sectors/${sector.toLowerCase()}/fields`);
      setSectorFields(fieldsResponse.data);

      // Load existing metrics for project
      const metricsResponse = await apiClient.get(`/sector-metrics/projects/${projectId}`);
      const metrics = metricsResponse.data;

      if (metrics.input_data && Object.keys(metrics.input_data).length > 0) {
        setExistingData(metrics);
        // Convert stored data to form strings
        const formValues: Record<string, string> = {};
        for (const [key, value] of Object.entries(metrics.input_data)) {
          formValues[key] = value !== null ? String(value) : "";
        }
        setFormData(formValues);
        setCalculatedIndicators(metrics.calculated_indicators || {});
      }
    } catch (err: any) {
      console.error("Error loading sector data:", err);
      setError(err.response?.data?.detail || "Error cargando datos del sector");
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setSuccess(false);
  };

  const parseFormData = (): Record<string, number | null> => {
    const parsed: Record<string, number | null> = {};
    for (const [key, value] of Object.entries(formData)) {
      if (value === "" || value === null || value === undefined) {
        parsed[key] = null;
      } else {
        const num = parseFloat(value);
        parsed[key] = isNaN(num) ? null : num;
      }
    }
    return parsed;
  };

  const handleCalculatePreview = async () => {
    setCalculating(true);
    setError(null);
    try {
      const inputData = parseFormData();
      const response = await apiClient.post(`/sector-metrics/projects/${projectId}/calculate`, {
        input_data: inputData,
      });
      setCalculatedIndicators(response.data.calculated_indicators || {});
    } catch (err: any) {
      console.error("Error calculating:", err);
      setError(err.response?.data?.detail || "Error calculando indicadores");
    } finally {
      setCalculating(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const inputData = parseFormData();
      const response = await apiClient.post(`/sector-metrics/projects/${projectId}`, {
        input_data: inputData,
      });
      setCalculatedIndicators(response.data.calculated_indicators || {});
      setExistingData(response.data);
      setSuccess(true);
      onSaved?.();
    } catch (err: any) {
      console.error("Error saving:", err);
      setError(err.response?.data?.detail || "Error guardando datos");
    } finally {
      setSaving(false);
    }
  };

  const formatIndicatorValue = (key: string, value: number | string | null): string => {
    if (value === null || value === undefined) return "N/A";
    if (typeof value === "string") return value;

    // Percentages
    if (
      key.includes("rate") ||
      key.includes("ratio") ||
      key.includes("yield") ||
      key.includes("cap") ||
      key.includes("ltv") ||
      key.includes("margen") ||
      key.includes("conversion") ||
      key.includes("utilizacion") ||
      key.includes("ocupacion") ||
      key.includes("roi") ||
      key.includes("factor")
    ) {
      return `${(value * 100).toFixed(2)}%`;
    }

    // Currency
    if (
      key.includes("mrr") ||
      key.includes("arr") ||
      key.includes("burn") ||
      key.includes("noi") ||
      key.includes("ingreso") ||
      key.includes("costo") ||
      key.includes("volumen") ||
      key.includes("cartera") ||
      key.includes("ventas") ||
      key.includes("ticket") ||
      key.includes("arpu") ||
      key.includes("punto_equilibrio")
    ) {
      return `$${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    // Numbers with decimals
    if (key.includes("runway") || key.includes("payback") || key.includes("anos") || key.includes("meses")) {
      return value.toFixed(1);
    }

    // Default
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-primary mr-2" />
        <span className="text-muted-foreground">Cargando formulario...</span>
      </div>
    );
  }

  if (!sectorFields) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No se encontraron campos para el sector {sector}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Datos Sectoriales - {sector}</h3>
          <p className="text-sm text-muted-foreground">{projectName}</p>
        </div>
        {existingData?.calculated_at && (
          <span className="text-xs text-muted-foreground">
            Ultimo calculo: {new Date(existingData.calculated_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <span className="text-sm text-red-700">{error}</span>
        </div>
      )}

      {/* Success Message */}
      {success && (
        <div className="p-3 rounded-lg bg-green-50 border border-green-200 flex items-center gap-2">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <span className="text-sm text-green-700">Datos guardados y calculados exitosamente</span>
        </div>
      )}

      {/* Input Form */}
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="text-base flex items-center gap-2">
            <Calculator className="h-4 w-4" />
            Datos de Entrada
          </CardTitle>
          <CardDescription>
            Ingrese los datos especificos del sector para calcular indicadores
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(sectorFields.fields).map(([fieldKey, fieldConfig]) => (
              <div key={fieldKey} className="space-y-1.5">
                <Label htmlFor={fieldKey} className="text-sm flex items-center gap-1">
                  {fieldConfig.label}
                  {fieldConfig.required && <span className="text-red-500">*</span>}
                  {fieldConfig.type === "percentage" && (
                    <span className="text-xs text-muted-foreground ml-1">(%)</span>
                  )}
                </Label>
                <Input
                  id={fieldKey}
                  type="number"
                  step={fieldConfig.type === "integer" ? "1" : "0.01"}
                  placeholder={fieldConfig.type === "percentage" ? "Ej: 5.5" : "0"}
                  value={formData[fieldKey] || ""}
                  onChange={(e) => handleInputChange(fieldKey, e.target.value)}
                  className={fieldConfig.required && !formData[fieldKey] ? "border-yellow-300" : ""}
                />
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 mt-6 pt-4 border-t">
            <Button
              onClick={handleCalculatePreview}
              variant="outline"
              disabled={calculating}
            >
              {calculating ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Calcular Preview
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Save className="h-4 w-4 mr-2" />
              )}
              Guardar y Calcular
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Calculated Indicators */}
      {Object.keys(calculatedIndicators).length > 0 && (
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Indicadores Calculados
            </CardTitle>
            <CardDescription>
              Indicadores especificos para el sector {sector}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {Object.entries(calculatedIndicators).map(([key, value]) => (
                <div
                  key={key}
                  className="p-3 bg-slate-50 rounded-lg border"
                >
                  <p className="text-lg font-bold text-primary">
                    {formatIndicatorValue(key, value)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {indicatorLabels[key] || key.replace(/_/g, " ")}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Info about sector indicators */}
      <div className="text-xs text-muted-foreground flex items-start gap-2 p-3 bg-slate-50 rounded-lg">
        <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
        <div>
          <p className="font-medium mb-1">Indicadores del sector {sector}:</p>
          <p>{sectorFields.calculated_indicators.map(i => indicatorLabels[i] || i).join(", ")}</p>
        </div>
      </div>
    </div>
  );
}
