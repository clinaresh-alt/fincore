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

// === BLOCKCHAIN ===
export type BlockchainNetwork =
  | "polygon"
  | "polygon_mumbai"
  | "ethereum"
  | "ethereum_sepolia"
  | "arbitrum"
  | "base";

export type TokenType = "ERC20" | "ERC721" | "ERC1155";

export type TransactionStatus =
  | "pending"
  | "submitted"
  | "confirmed"
  | "failed";

export type BlockchainTransactionType =
  | "token_purchase"
  | "token_transfer"
  | "dividend_claim"
  | "kyc_registration"
  | "contract_deployment";

export interface NetworkInfo {
  name: string;
  chain_id: number;
  is_testnet: boolean;
  currency: string;
  explorer_url: string;
  rpc_configured: boolean;
}

export interface NetworkStatus {
  network: BlockchainNetwork;
  connected: boolean;
  block_number?: number;
  gas_price_gwei?: number;
  error?: string;
}

export interface UserWallet {
  id: string;
  user_id: string;
  address: string;
  network: BlockchainNetwork;
  label?: string;
  is_primary: boolean;
  is_verified: boolean;
  created_at: string;
}

export interface WalletBalance {
  wallet_id: string;
  address: string;
  network: string;
  native_balance: number;
  native_symbol: string;
  usdc_balance?: number;
  tokens: Array<{
    token_id: string;
    symbol: string;
    balance: number;
    value_usd: number;
  }>;
}

export interface ProjectToken {
  id: string;
  proyecto_id: string;
  proyecto_nombre?: string;
  nombre: string;
  simbolo: string;
  supply_total: number;
  supply_vendido: number;
  precio_por_token: number;
  network: BlockchainNetwork;
  contract_address?: string;
  token_type: TokenType;
  is_active: boolean;
  created_at: string;
}

export interface TokenStats {
  token_id: string;
  nombre: string;
  simbolo: string;
  supply_total: number;
  supply_vendido: number;
  supply_disponible: number;
  porcentaje_vendido: number;
  total_holders: number;
  total_recaudado: number;
  precio_actual: number;
}

export interface TokenHolding {
  id: string;
  token_id: string;
  wallet_id: string;
  cantidad: number;
  precio_promedio_compra: number;
  valor_actual: number;
  ganancia_perdida: number;
  porcentaje_ganancia: number;
}

export interface BlockchainPortfolio {
  total_value_usd: number;
  total_invested: number;
  total_gain_loss: number;
  porcentaje_ganancia: number;
  holdings: Array<{
    token: ProjectToken;
    cantidad: number;
    valor_actual: number;
    ganancia_perdida: number;
  }>;
  pending_dividends: number;
}

export interface DividendDistribution {
  id: string;
  token_id: string;
  token_nombre?: string;
  monto_total: number;
  monto_por_token: number;
  fecha_distribucion: string;
  descripcion?: string;
  total_reclamado: number;
  total_pendiente: number;
}

export interface BlockchainTransaction {
  id: string;
  wallet_id: string;
  tipo: BlockchainTransactionType;
  tx_hash?: string;
  network: BlockchainNetwork;
  status: TransactionStatus;
  monto?: number;
  gas_usado?: number;
  gas_precio?: number;
  error_mensaje?: string;
  created_at: string;
  confirmed_at?: string;
}

export interface KYCBlockchainStatus {
  user_id: string;
  is_registered: boolean;
  kyc_hash?: string;
  network?: BlockchainNetwork;
  tx_hash?: string;
  registered_at?: string;
}

// === AUDIT & SECURITY ===
export type AlertSeverity = "critical" | "high" | "medium" | "low" | "info";
export type AlertType =
  | "large_transaction"
  | "reentrancy"
  | "flash_loan"
  | "admin_function"
  | "unusual_gas"
  | "known_attacker"
  | "anomaly";

export type IncidentSeverity = "sev1" | "sev2" | "sev3" | "sev4";
export type IncidentStatus =
  | "detected"
  | "investigating"
  | "contained"
  | "eradicating"
  | "recovering"
  | "resolved"
  | "closed";

export interface AuditAlert {
  id: string;
  type: AlertType;
  severity: AlertSeverity;
  title: string;
  description: string;
  transaction_hash?: string;
  contract_address?: string;
  timestamp: string;
}

export interface AuditIncident {
  id: string;
  title: string;
  description: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  detected_at: string;
  contained_at?: string;
  resolved_at?: string;
  actions_count: number;
}

export interface ContractAuditResult {
  contract_path: string;
  timestamp: string;
  security_score: number;
  vulnerabilities_count: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    informational: number;
  };
  high_severity_issues: Array<{
    detector: string;
    description: string;
    impact: string;
    confidence: string;
  }>;
  recommendations: string[];
  report_path?: string;
}

export interface SecurityDashboard {
  alert_statistics: {
    total_alerts: number;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
    acknowledged_count: number;
    unacknowledged_count: number;
  };
  incident_statistics: {
    total_incidents: number;
    active_incidents: number;
    resolved_incidents: number;
    by_severity: Record<string, number>;
    mttr_hours?: number;
    mttd_minutes?: number;
  };
  active_incidents: Array<{
    id: string;
    title: string;
    severity: string;
    status: string;
    detected_at: string;
  }>;
  recent_alerts: Array<{
    id: string;
    type: string;
    severity: string;
    title: string;
    timestamp: string;
  }>;
}

// === REMITTANCES ===
export type RemittanceStatus =
  | "initiated"
  | "pending_deposit"
  | "deposited"
  | "locked"
  | "processing"
  | "disbursed"
  | "completed"
  | "refund_pending"
  | "refunded"
  | "failed"
  | "cancelled"
  | "expired";

export type PaymentMethod =
  | "spei"
  | "wire_transfer"
  | "card"
  | "cash"
  | "crypto";

export type DisbursementMethod =
  | "bank_transfer"
  | "mobile_wallet"
  | "cash_pickup"
  | "home_delivery";

export type RemittanceCurrency =
  | "USD"
  | "MXN"
  | "EUR"
  | "CLP"
  | "COP"
  | "PEN"
  | "BRL"
  | "ARS";

export type Stablecoin = "USDC" | "USDT" | "DAI";

export interface RecipientInfo {
  full_name: string;
  email?: string;
  phone?: string;
  country: string;
  bank_name?: string;
  bank_account?: string;
  clabe?: string;
  routing_number?: string;
  swift_code?: string;
}

export interface Remittance {
  id: string;
  reference_code: string;
  sender_id: string;
  recipient_info: RecipientInfo;
  amount_fiat_source: number;
  currency_source: RemittanceCurrency;
  amount_fiat_destination?: number;
  currency_destination: RemittanceCurrency;
  amount_stablecoin?: number;
  stablecoin: Stablecoin;
  exchange_rate_source_usd?: number;
  exchange_rate_usd_destination?: number;
  exchange_rate_locked_at?: string;
  platform_fee: number;
  network_fee: number;
  total_fees: number;
  status: RemittanceStatus;
  payment_method?: PaymentMethod;
  disbursement_method?: DisbursementMethod;
  escrow_locked_at?: string;
  escrow_expires_at?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  notes?: string;
}

export interface RemittanceQuote {
  amount_source: number;
  currency_source: RemittanceCurrency;
  amount_destination: number;
  currency_destination: RemittanceCurrency;
  amount_stablecoin: number;
  stablecoin: Stablecoin;
  exchange_rate_source_usd: number;
  exchange_rate_usd_destination: number;
  platform_fee: number;
  network_fee_estimate: number;
  total_fees: number;
  total_to_pay: number;
  recipient_receives: number;
  quote_valid_until: string;
}

export interface RemittanceBlockchainTx {
  id: string;
  remittance_id: string;
  tx_hash?: string;
  operation: string;
  blockchain_status: "pending" | "submitted" | "mined" | "confirmed" | "reverted" | "replaced";
  network: string;
  contract_address?: string;
  from_address?: string;
  to_address?: string;
  gas_used?: number;
  confirmations: number;
  error_message?: string;
  created_at: string;
  confirmed_at?: string;
}

export interface RemittanceLimit {
  corridor_source: RemittanceCurrency;
  corridor_destination: RemittanceCurrency;
  kyc_level: number;
  min_amount_usd: number;
  max_amount_usd: number;
  daily_limit_usd: number;
  monthly_limit_usd: number;
}
