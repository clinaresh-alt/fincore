// ===========================================
// Tipos del Customer Portal - FinCore
// ===========================================

// ============ Usuario y Autenticación ============

export type UserRole = "Cliente" | "Inversionista";

export type KYCStatus = "pending" | "submitted" | "approved" | "rejected" | "expired";

export type KYCLevel = 0 | 1 | 2 | 3;

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone?: string;
  role: UserRole;
  kyc_status: KYCStatus;
  kyc_level: KYCLevel;
  mfa_enabled: boolean;
  created_at: string;
  last_login?: string;
  avatar_url?: string;
}

export interface AuthSession {
  user: User;
  access_token: string;
  expires_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterData {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
  accept_terms: boolean;
}

export interface MFAVerification {
  code: string;
  mfa_pending_token: string;
}

// ============ Remesas ============

export type RemittanceCurrency = "USD" | "MXN" | "EUR" | "CLP" | "COP" | "PEN" | "BRL" | "ARS";

export type Stablecoin = "USDC" | "USDT" | "DAI";

export type PaymentMethod = "spei" | "wire_transfer" | "card" | "crypto";

export type DisbursementMethod = "bank_transfer" | "mobile_wallet" | "cash_pickup" | "home_delivery";

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

export interface RecipientInfo {
  name: string;
  bank_name?: string;
  account_number?: string;
  clabe?: string;
  iban?: string;
  swift?: string;
  phone?: string;
  email?: string;
  country: string;
}

export interface Beneficiary {
  id: string;
  user_id: string;
  nickname: string;
  recipient_info: RecipientInfo;
  is_favorite: boolean;
  created_at: string;
  last_used_at?: string;
}

export interface RemittanceQuote {
  quote_id: string;
  amount_source: number;
  currency_source: RemittanceCurrency;
  amount_destination: number;
  currency_destination: RemittanceCurrency;
  amount_stablecoin: number;
  exchange_rate_source_usd: number;
  exchange_rate_usd_destination: number;
  platform_fee: number;
  network_fee: number;
  total_fees: number;
  total_to_pay: number;
  estimated_delivery: string;
  quote_expires_at: string;
}

export interface QuoteRequest {
  amount_source: number;
  currency_source: RemittanceCurrency;
  currency_destination: RemittanceCurrency;
}

export interface CreateRemittanceRequest {
  recipient_id?: string;
  recipient_info?: RecipientInfo;
  amount_source: number;
  currency_source: RemittanceCurrency;
  currency_destination: RemittanceCurrency;
  payment_method: PaymentMethod;
  disbursement_method: DisbursementMethod;
  quote_id?: string;
  notes?: string;
}

export interface Remittance {
  id: string;
  reference_code: string;
  sender_id: string;
  recipient_info: RecipientInfo;
  amount_fiat_source: number;
  currency_source: RemittanceCurrency;
  amount_fiat_destination: number;
  currency_destination: RemittanceCurrency;
  amount_stablecoin?: number;
  stablecoin: Stablecoin;
  exchange_rate_source_usd: number;
  exchange_rate_usd_destination?: number;
  platform_fee: number;
  network_fee: number;
  total_fees: number;
  status: RemittanceStatus;
  payment_method: PaymentMethod;
  disbursement_method: DisbursementMethod;
  escrow_locked_at?: string;
  escrow_expires_at?: string;
  blockchain_tx_hash?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface RemittanceLimits {
  daily_limit: number;
  monthly_limit: number;
  used_today: number;
  used_this_month: number;
  available_today: number;
  available_this_month: number;
  kyc_level: KYCLevel;
}

// ============ Wallet & Crypto ============

export type BlockchainNetwork = "polygon" | "ethereum" | "arbitrum" | "base";

export interface WalletBalance {
  currency: string;
  balance: number;
  balance_usd: number;
  network?: BlockchainNetwork;
}

export interface CryptoQuote {
  from_currency: string;
  to_currency: string;
  amount: number;
  rate: number;
  result_amount: number;
  fee: number;
  expires_at: string;
}

export interface CryptoPurchaseRequest {
  amount_fiat: number;
  currency_fiat: RemittanceCurrency;
  crypto_currency: Stablecoin;
  payment_method: PaymentMethod;
}

// ============ Transacciones ============

export type TransactionType = "remittance" | "crypto_purchase" | "crypto_sell" | "deposit" | "withdrawal";

export type TransactionStatus = "pending" | "processing" | "completed" | "failed" | "cancelled";

export interface Transaction {
  id: string;
  type: TransactionType;
  status: TransactionStatus;
  amount: number;
  currency: string;
  description: string;
  reference?: string;
  blockchain_tx_hash?: string;
  created_at: string;
  completed_at?: string;
}

// ============ Dispositivos y Seguridad ============

export interface AuthorizedDevice {
  id: string;
  device_name: string;
  device_type: "mobile" | "desktop" | "tablet";
  browser?: string;
  os?: string;
  ip_address: string;
  location?: string;
  last_active: string;
  created_at: string;
  is_current: boolean;
}

export interface SecuritySettings {
  mfa_enabled: boolean;
  mfa_method: "totp" | "webauthn" | null;
  webauthn_enabled: boolean;
  transaction_limit_daily: number;
  transaction_limit_per_tx: number;
  require_2fa_for_login: boolean;
  require_2fa_for_transactions: boolean;
}

export interface PasskeyCredential {
  id: string;
  name: string;
  created_at: string;
  last_used_at?: string;
}

// ============ Notificaciones ============

export type NotificationType =
  | "remittance_created"
  | "remittance_locked"
  | "remittance_completed"
  | "remittance_failed"
  | "kyc_approved"
  | "kyc_rejected"
  | "security_alert"
  | "system";

export type NotificationPriority = "low" | "medium" | "high" | "critical";

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  priority: NotificationPriority;
  data?: Record<string, unknown>;
  read: boolean;
  created_at: string;
}

// ============ WebSocket ============

export interface WSMessage {
  type: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface RemittanceStatusUpdate {
  remittance_id: string;
  reference_code: string;
  old_status: RemittanceStatus;
  new_status: RemittanceStatus;
  message: string;
  timestamp: string;
}

// ============ API Responses ============

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface APIResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface APIError {
  detail: string;
  code?: string;
  field?: string;
}

// ============ Formularios ============

export interface FormStep {
  id: string;
  title: string;
  description?: string;
  isCompleted: boolean;
  isActive: boolean;
}
