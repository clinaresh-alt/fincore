// FinCore Types

// === AUTH ===
export interface User {
  id: string;
  email: string;
  rol: "Cliente" | "Inversionista" | "Analista" | "Admin";
  mfa_enabled: boolean;
  email_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  mfa_required: boolean;
  mfa_token?: string;
}

export interface MFASetup {
  secret: string;
  qr_code_base64: string;
  manual_entry_key: string;
}

// === PROJECTS ===
export interface Project {
  id: string;
  nombre: string;
  descripcion?: string;
  sector: string;
  monto_solicitado: number;
  monto_financiado: number;
  monto_minimo_inversion?: number;
  plazo_meses: number;
  fecha_inicio_estimada?: string;
  fecha_fin_estimada?: string;
  estado: ProjectStatus;
  tasa_rendimiento_anual?: number;
  rendimiento_proyectado?: number;
  empresa_solicitante?: string;
  tiene_documentacion_completa?: boolean;
  created_at: string;
}

export type ProjectStatus =
  | "En Evaluacion"
  | "Aprobado"
  | "Rechazado"
  | "Financiando"
  | "Financiado"
  | "En Ejecucion"
  | "Completado"
  | "Default";

export interface ProjectAnalytics {
  project_id: string;
  nombre: string;
  estado: string;
  financials: {
    van: number;
    tir: number | null;
    roi: number;
    risk_level: string;
  };
  cash_flow_series: Array<{
    period: string;
    amount: number;
  }>;
  monto_solicitado: number;
  monto_financiado: number;
  porcentaje_financiado: number;
  total_inversionistas: number;
}

// === EVALUACION FINANCIERA ===
export interface EvaluationResult {
  proyecto_id: string;
  inversion_inicial: number;
  tasa_descuento: number;
  van: number;
  tir: number | null;
  roi: number;
  payback_period: number | null;
  indice_rentabilidad: number;
  escenarios?: Array<{
    escenario: string;
    van: number;
    tir: number | null;
    es_viable: boolean;
  }>;
  es_viable: boolean;
  mensaje: string;
  fecha_evaluacion: string;
}

export interface RiskAnalysis {
  proyecto_id: string;
  score_total: number;
  score_capacidad_pago: number;
  score_historial: number;
  score_garantias: number;
  nivel_riesgo: "AAA" | "AA" | "A" | "B" | "C";
  accion_recomendada: string;
  probabilidad_default: number;
  probabilidad_exito: number;
  ratio_deuda_ingreso?: number;
  loan_to_value?: number;
  tasa_interes_sugerida: number;
  monto_maximo_aprobado?: number;
  requiere_garantias_adicionales: boolean;
  observaciones: string[];
}

// === INVERSIONES ===
export interface Investment {
  id: string;
  proyecto_id: string;
  proyecto_nombre?: string;
  monto_invertido: number;
  monto_rendimiento_acumulado: number;
  monto_total_recibido: number;
  porcentaje_participacion?: number;
  estado: InvestmentStatus;
  fecha_inversion: string;
  fecha_vencimiento?: string;
}

export type InvestmentStatus =
  | "Pendiente"
  | "Activa"
  | "En Rendimiento"
  | "Liquidada"
  | "Cancelada";

export interface Transaction {
  id: string;
  tipo: string;
  monto: number;
  concepto?: string;
  fecha_transaccion: string;
}

// === PORTFOLIO ===
export interface PortfolioKPIs {
  total_invertido: number;
  rendimiento_total: number;
  rendimiento_porcentual: number;
  tir_cartera: number | null;
  moic: number;
  proyectos_activos: number;
  proyectos_completados: number;
  proyectos_en_default: number;
}

export interface SectorDistribution {
  sector: string;
  monto: number;
  porcentaje: number;
  cantidad_proyectos: number;
}

export interface Portfolio {
  kpis: PortfolioKPIs;
  distribucion_sectores: SectorDistribution[];
  inversiones: Investment[];
  proximos_pagos: Array<{
    proyecto_id: string;
    proyecto_nombre: string;
    tipo: string;
    monto_esperado: number;
    fecha_esperada: string;
  }>;
  rendimiento_historico: Array<{
    mes: string;
    rendimiento: number;
  }>;
}
