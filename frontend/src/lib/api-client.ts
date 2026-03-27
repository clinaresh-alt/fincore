/**
 * Cliente API para FinCore
 * Configurado con interceptores para JWT y refresh tokens
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

// Crear instancia de Axios
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// Interceptor de request: agregar token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Interceptor de response: manejar errores y refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Si es 401 y no es retry, intentar refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem("refresh_token");
        if (refreshToken) {
          // TODO: Implementar endpoint de refresh
          // const response = await apiClient.post("/auth/refresh", { refresh_token: refreshToken });
          // localStorage.setItem("access_token", response.data.access_token);
          // return apiClient(originalRequest);
        }
      } catch (refreshError) {
        // Refresh fallido, limpiar tokens y redirigir a login
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.href = "/login";
      }
    }

    return Promise.reject(error);
  }
);

// === AUTH API ===
export const authAPI = {
  login: async (email: string, password: string) => {
    // Limpiar tokens viejos antes del login para evitar conflictos
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");

    const formData = new URLSearchParams();
    formData.append("username", email);
    formData.append("password", password);

    // Usar axios directamente sin interceptores para evitar token en login
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL || "/api/v1"}/auth/login`,
      formData,
      {
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      }
    );
    return response.data;
  },

  verifyMFA: async (code: string, mfaToken: string) => {
    const response = await apiClient.post("/auth/mfa/verify", {
      code,
      mfa_token: mfaToken,
    });
    return response.data;
  },

  register: async (email: string, password: string, rol: string) => {
    // Usar axios directamente sin interceptores para registro
    const response = await axios.post(
      `${process.env.NEXT_PUBLIC_API_URL || "/api/v1"}/auth/register`,
      { email, password, rol }
    );
    return response.data;
  },

  setupMFA: async () => {
    const response = await apiClient.post("/auth/mfa/setup");
    return response.data;
  },

  enableMFA: async (code: string) => {
    const response = await apiClient.post(`/auth/mfa/enable?code=${code}`);
    return response.data;
  },

  getCurrentUser: async () => {
    const response = await apiClient.get("/auth/me");
    return response.data;
  },

  logout: async () => {
    const response = await apiClient.post("/auth/logout");
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    return response.data;
  },
};

// === PROJECTS API ===
export const projectsAPI = {
  list: async (params?: { estado?: string; sector?: string }) => {
    const response = await apiClient.get("/projects/", { params });
    return response.data;
  },

  get: async (id: string) => {
    const response = await apiClient.get(`/projects/${id}`);
    return response.data;
  },

  getAnalytics: async (id: string) => {
    const response = await apiClient.get(`/projects/${id}/analytics`);
    return response.data;
  },

  create: async (data: {
    nombre: string;
    descripcion?: string;
    sector: string;
    monto_solicitado: number;
    plazo_meses: number;
    tasa_rendimiento_anual?: number;
  }) => {
    const response = await apiClient.post("/projects/", data);
    return response.data;
  },

  evaluate: async (data: {
    proyecto_id: string;
    inversion_inicial: number;
    tasa_descuento: number;
    flujos_caja: Array<{
      periodo_nro: number;
      monto_ingreso: number;
      monto_egreso: number;
    }>;
  }) => {
    const response = await apiClient.post("/projects/evaluate", data);
    return response.data;
  },

  analyzeFeasibility: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post("/projects/analyze-feasibility", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  getIndicatorsBySector: async (sector: string) => {
    const response = await apiClient.get(`/projects/indicators/${sector}`);
    return response.data;
  },

  analyzeRisk: async (projectId: string, data: any) => {
    const response = await apiClient.post(
      `/projects/${projectId}/risk-analysis`,
      data
    );
    return response.data;
  },

  update: async (id: string, data: {
    nombre?: string;
    descripcion?: string;
    sector?: string;
    monto_solicitado?: number;
    monto_minimo_inversion?: number;
    plazo_meses?: number;
    fecha_inicio_estimada?: string;
    fecha_fin_estimada?: string;
    tasa_rendimiento_anual?: number;
    rendimiento_proyectado?: number;
    empresa_solicitante?: string;
    tiene_documentacion_completa?: boolean;
  }) => {
    const response = await apiClient.put(`/projects/${id}`, data);
    return response.data;
  },

  delete: async (id: string) => {
    await apiClient.delete(`/projects/${id}`);
  },

  // Indicadores del sector
  getIndicators: async (projectId: string) => {
    const response = await apiClient.get(`/projects/${projectId}/indicators`);
    return response.data;
  },

  saveIndicators: async (projectId: string, data: Record<string, any>) => {
    const response = await apiClient.post(`/projects/${projectId}/indicators`, data);
    return response.data;
  },

  updateIndicators: async (projectId: string, data: Record<string, any>) => {
    const response = await apiClient.put(`/projects/${projectId}/indicators`, data);
    return response.data;
  },

  deleteIndicators: async (projectId: string) => {
    await apiClient.delete(`/projects/${projectId}/indicators`);
  },

  // Obtener evaluacion completa del proyecto
  getEvaluation: async (projectId: string) => {
    const response = await apiClient.get(`/projects/${projectId}/evaluation`);
    return response.data;
  },
};

// === COMPANIES API ===
export const companiesAPI = {
  list: async (params?: { estado?: string; sector?: string; search?: string; page?: number; page_size?: number }) => {
    const response = await apiClient.get("/companies/", { params });
    return response.data;
  },

  get: async (id: string) => {
    const response = await apiClient.get(`/companies/${id}`);
    return response.data;
  },

  getTypes: async () => {
    const response = await apiClient.get("/companies/types");
    return response.data;
  },

  create: async (data: Record<string, any>) => {
    const response = await apiClient.post("/companies/", data);
    return response.data;
  },

  update: async (id: string, data: Record<string, any>) => {
    const response = await apiClient.put(`/companies/${id}`, data);
    return response.data;
  },

  delete: async (id: string) => {
    await apiClient.delete(`/companies/${id}`);
  },

  updateVerification: async (id: string, data: { estado_verificacion: string; notas_verificacion?: string; score_riesgo?: number }) => {
    const response = await apiClient.put(`/companies/${id}/verification`, data);
    return response.data;
  },

  // Documents
  listDocuments: async (companyId: string, tipo?: string) => {
    const response = await apiClient.get(`/companies/${companyId}/documents`, { params: { tipo } });
    return response.data;
  },

  uploadDocument: async (companyId: string, file: File, data: { tipo: string; descripcion?: string; fecha_emision?: string; fecha_vencimiento?: string }) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("tipo", data.tipo);
    if (data.descripcion) formData.append("descripcion", data.descripcion);
    if (data.fecha_emision) formData.append("fecha_emision", data.fecha_emision);
    if (data.fecha_vencimiento) formData.append("fecha_vencimiento", data.fecha_vencimiento);

    const response = await apiClient.post(`/companies/${companyId}/documents`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  getDocument: async (companyId: string, documentId: string) => {
    const response = await apiClient.get(`/companies/${companyId}/documents/${documentId}`);
    return response.data;
  },

  updateDocument: async (companyId: string, documentId: string, data: Record<string, any>) => {
    const response = await apiClient.put(`/companies/${companyId}/documents/${documentId}`, data);
    return response.data;
  },

  deleteDocument: async (companyId: string, documentId: string) => {
    await apiClient.delete(`/companies/${companyId}/documents/${documentId}`);
  },

  // Projects
  listProjects: async (companyId: string) => {
    const response = await apiClient.get(`/companies/${companyId}/projects`);
    return response.data;
  },
};

// === INVESTOR API ===
export const investorAPI = {
  getPortfolio: async () => {
    const response = await apiClient.get("/investor/portfolio");
    return response.data;
  },

  invest: async (data: { proyecto_id: string; monto: number }) => {
    const response = await apiClient.post("/investor/invest", data);
    return response.data;
  },

  listInvestments: async () => {
    const response = await apiClient.get("/investor/investments");
    return response.data;
  },

  getInvestmentDetail: async (id: string) => {
    const response = await apiClient.get(`/investor/investments/${id}`);
    return response.data;
  },
};

// === BLOCKCHAIN API ===
export const blockchainAPI = {
  // Networks
  getNetworks: async () => {
    const response = await apiClient.get("/blockchain/networks");
    return response.data;
  },

  getNetworkStatus: async (network: string) => {
    const response = await apiClient.get(`/blockchain/networks/${network}/status`);
    return response.data;
  },

  getGasEstimate: async (network: string) => {
    const response = await apiClient.get("/blockchain/gas-estimate", {
      params: { network },
    });
    return response.data;
  },

  // Wallets
  createWallet: async (data: { address: string; network: string; label?: string }) => {
    const response = await apiClient.post("/blockchain/wallets", data);
    return response.data;
  },

  verifyWallet: async (data: { wallet_id: string; message: string; signature: string }) => {
    const response = await apiClient.post("/blockchain/wallets/verify", data);
    return response.data;
  },

  listWallets: async () => {
    const response = await apiClient.get("/blockchain/wallets");
    return response.data;
  },

  getWalletBalance: async (walletId: string) => {
    const response = await apiClient.get(`/blockchain/wallets/${walletId}/balance`);
    return response.data;
  },

  deleteWallet: async (walletId: string) => {
    await apiClient.delete(`/blockchain/wallets/${walletId}`);
  },

  // Tokens
  createToken: async (data: {
    proyecto_id: string;
    nombre: string;
    simbolo: string;
    supply_total: number;
    precio_por_token: number;
    network: string;
  }) => {
    const response = await apiClient.post("/blockchain/tokens", data);
    return response.data;
  },

  listTokens: async (params?: { proyecto_id?: string; activo?: boolean }) => {
    const response = await apiClient.get("/blockchain/tokens", { params });
    return response.data;
  },

  getTokenStats: async (tokenId: string) => {
    const response = await apiClient.get(`/blockchain/tokens/${tokenId}/stats`);
    return response.data;
  },

  activateToken: async (tokenId: string, contractAddress: string) => {
    const response = await apiClient.post(`/blockchain/tokens/${tokenId}/activate`, {
      contract_address: contractAddress,
    });
    return response.data;
  },

  getTokenHolders: async (tokenId: string) => {
    const response = await apiClient.get(`/blockchain/tokens/${tokenId}/holders`);
    return response.data;
  },

  purchaseTokens: async (data: { token_id: string; cantidad: number; wallet_id: string }) => {
    const response = await apiClient.post("/blockchain/tokens/purchase", data);
    return response.data;
  },

  transferTokens: async (data: {
    token_id: string;
    from_wallet_id: string;
    to_address: string;
    cantidad: number;
  }) => {
    const response = await apiClient.post("/blockchain/tokens/transfer", data);
    return response.data;
  },

  // Portfolio
  getPortfolio: async (walletId?: string) => {
    const response = await apiClient.get("/blockchain/portfolio", {
      params: walletId ? { wallet_id: walletId } : {},
    });
    return response.data;
  },

  // Dividends
  createDividend: async (data: {
    token_id: string;
    monto_total: number;
    descripcion?: string;
  }) => {
    const response = await apiClient.post("/blockchain/dividends", data);
    return response.data;
  },

  calculateDividends: async (tokenId: string) => {
    const response = await apiClient.get(`/blockchain/dividends/calculate/${tokenId}`);
    return response.data;
  },

  claimDividend: async (data: { distribution_id: string; wallet_id: string }) => {
    const response = await apiClient.post("/blockchain/dividends/claim", data);
    return response.data;
  },

  getDividendHistory: async (tokenId: string) => {
    const response = await apiClient.get(`/blockchain/dividends/${tokenId}/history`);
    return response.data;
  },

  // Transactions
  listTransactions: async (params?: {
    wallet_id?: string;
    tipo?: string;
    limit?: number;
  }) => {
    const response = await apiClient.get("/blockchain/transactions", { params });
    return response.data;
  },

  getTransaction: async (txId: string) => {
    const response = await apiClient.get(`/blockchain/transactions/${txId}`);
    return response.data;
  },

  // KYC
  registerKYC: async () => {
    const response = await apiClient.post("/blockchain/kyc/register");
    return response.data;
  },

  getKYCStatus: async (userId: string) => {
    const response = await apiClient.get(`/blockchain/kyc/${userId}`);
    return response.data;
  },
};

// === COMPLIANCE API ===
export const complianceAPI = {
  // Dashboard
  getDashboard: async () => {
    const response = await apiClient.get("/compliance/dashboard");
    return response.data;
  },

  // KYC
  getKYCProfile: async () => {
    const response = await apiClient.get("/compliance/kyc/profile");
    return response.data;
  },

  updateKYCProfile: async (data: {
    first_name?: string;
    last_name?: string;
    curp?: string;
    rfc?: string;
    date_of_birth?: string;
    nationality?: string;
    street_address?: string;
    city?: string;
    state?: string;
    postal_code?: string;
    occupation?: string;
    source_of_funds?: string;
  }) => {
    const response = await apiClient.put("/compliance/kyc/profile", data);
    return response.data;
  },

  verifyCURP: async (curp: string) => {
    const response = await apiClient.post("/compliance/kyc/verify-curp", { curp });
    return response.data;
  },

  getRiskScore: async () => {
    const response = await apiClient.get("/compliance/kyc/risk-score");
    return response.data;
  },

  // KYC Documents
  listDocuments: async () => {
    const response = await apiClient.get("/compliance/kyc/documents");
    return response.data;
  },

  uploadDocument: async (documentType: string, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await apiClient.post(
      `/compliance/kyc/documents?document_type=${documentType}`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return response.data;
  },

  // AML Alerts
  listAlerts: async (params?: { status?: string; severity?: string; limit?: number }) => {
    const response = await apiClient.get("/compliance/aml/alerts", { params });
    return response.data;
  },

  getAlert: async (alertId: string) => {
    const response = await apiClient.get(`/compliance/aml/alerts/${alertId}`);
    return response.data;
  },

  investigateAlert: async (alertId: string, notes: string) => {
    const response = await apiClient.post(`/compliance/aml/alerts/${alertId}/investigate`, { notes });
    return response.data;
  },

  escalateAlert: async (alertId: string) => {
    const response = await apiClient.post(`/compliance/aml/alerts/${alertId}/escalate`);
    return response.data;
  },

  closeAlert: async (alertId: string, data: { false_positive: boolean; notes: string }) => {
    const response = await apiClient.post(`/compliance/aml/alerts/${alertId}/close`, data);
    return response.data;
  },

  getAMLStatistics: async () => {
    const response = await apiClient.get("/compliance/aml/statistics");
    return response.data;
  },

  // Reports
  listReports: async (params?: { report_type?: string; status?: string }) => {
    const response = await apiClient.get("/compliance/reports", { params });
    return response.data;
  },

  generateROV: async (periodStart: string, periodEnd: string) => {
    const response = await apiClient.post("/compliance/reports/rov", {
      period_start: periodStart,
      period_end: periodEnd,
    });
    return response.data;
  },

  generateROS: async (alertIds: string[], narrative: string) => {
    const response = await apiClient.post("/compliance/reports/ros", {
      alert_ids: alertIds,
      narrative,
    });
    return response.data;
  },

  approveReport: async (reportId: string) => {
    const response = await apiClient.post(`/compliance/reports/${reportId}/approve`);
    return response.data;
  },

  submitReport: async (reportId: string) => {
    const response = await apiClient.post(`/compliance/reports/${reportId}/submit`);
    return response.data;
  },

  downloadReportXML: async (reportId: string) => {
    const response = await apiClient.get(`/compliance/reports/${reportId}/xml`);
    return response.data;
  },
};

// === AUDIT API ===
export const auditAPI = {
  // Contract Auditing
  auditContract: async (data: { contract_path: string; generate_html?: boolean }) => {
    const response = await apiClient.post("/audit/contracts/audit", data);
    return response.data;
  },

  listDetectors: async () => {
    const response = await apiClient.get("/audit/contracts/audit/detectors");
    return response.data;
  },

  // Transaction Monitoring
  analyzeTransaction: async (data: {
    tx_hash: string;
    from_address: string;
    to_address: string;
    value: number;
    gas_price: number;
    input_data?: string;
    network?: string;
  }) => {
    const response = await apiClient.post("/audit/monitoring/analyze-transaction", data);
    return response.data;
  },

  getAlerts: async (params?: { limit?: number; severity?: string }) => {
    const response = await apiClient.get("/audit/monitoring/alerts", { params });
    return response.data;
  },

  acknowledgeAlert: async (alertId: string) => {
    const response = await apiClient.post(`/audit/monitoring/alerts/${alertId}/acknowledge`);
    return response.data;
  },

  getMonitoringStatistics: async () => {
    const response = await apiClient.get("/audit/monitoring/statistics");
    return response.data;
  },

  // Incidents
  createIncident: async (data: {
    title: string;
    description: string;
    severity: "sev1" | "sev2" | "sev3" | "sev4";
    affected_contracts?: string[];
    related_transactions?: string[];
  }) => {
    const response = await apiClient.post("/audit/incidents", data);
    return response.data;
  },

  listIncidents: async (activeOnly?: boolean) => {
    const response = await apiClient.get("/audit/incidents", {
      params: { active_only: activeOnly },
    });
    return response.data;
  },

  containIncident: async (incidentId: string) => {
    const response = await apiClient.post(`/audit/incidents/${incidentId}/contain`);
    return response.data;
  },

  resolveIncident: async (incidentId: string, rootCause?: string) => {
    const response = await apiClient.post(`/audit/incidents/${incidentId}/resolve`, null, {
      params: { root_cause: rootCause },
    });
    return response.data;
  },

  getPostmortem: async (incidentId: string) => {
    const response = await apiClient.get(`/audit/incidents/${incidentId}/postmortem`);
    return response.data;
  },

  getIncidentStatistics: async () => {
    const response = await apiClient.get("/audit/incidents/statistics");
    return response.data;
  },

  // Dashboard
  getDashboard: async () => {
    const response = await apiClient.get("/audit/dashboard");
    return response.data;
  },
};

// === REMITTANCES API ===
export const remittancesAPI = {
  // Quote
  getQuote: async (data: {
    amount_source: number;
    currency_source: string;
    currency_destination: string;
    stablecoin?: string;
  }) => {
    const response = await apiClient.post("/remittances/quote", data);
    return response.data;
  },

  // Create remittance
  create: async (data: {
    amount_fiat_source: number;
    currency_source: string;
    currency_destination: string;
    recipient_info: {
      full_name: string;
      email?: string;
      phone?: string;
      country: string;
      bank_name?: string;
      bank_account?: string;
      clabe?: string;
      routing_number?: string;
      swift_code?: string;
    };
    payment_method?: string;
    disbursement_method?: string;
    stablecoin?: string;
    notes?: string;
  }) => {
    const response = await apiClient.post("/remittances", data);
    return response.data;
  },

  // List remittances
  list: async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }) => {
    const response = await apiClient.get("/remittances", { params });
    return response.data;
  },

  // Get by ID
  get: async (id: string) => {
    const response = await apiClient.get(`/remittances/${id}`);
    return response.data;
  },

  // Get by reference code
  getByReference: async (referenceCode: string) => {
    const response = await apiClient.get(`/remittances/reference/${referenceCode}`);
    return response.data;
  },

  // Lock funds in escrow
  lockFunds: async (remittanceId: string) => {
    const response = await apiClient.post(`/remittances/${remittanceId}/lock`);
    return response.data;
  },

  // Cancel remittance
  cancel: async (remittanceId: string, reason?: string) => {
    const response = await apiClient.post(`/remittances/${remittanceId}/cancel`, {
      reason,
    });
    return response.data;
  },

  // Release funds (operator/admin only)
  releaseFunds: async (remittanceId: string, disbursementReference?: string) => {
    const response = await apiClient.post(`/remittances/${remittanceId}/release`, {
      disbursement_reference: disbursementReference,
    });
    return response.data;
  },

  // Get pending refunds (admin only)
  getPendingRefunds: async () => {
    const response = await apiClient.get("/remittances/pending-refunds");
    return response.data;
  },

  // Process refund (admin only)
  processRefund: async (remittanceId: string) => {
    const response = await apiClient.post(`/remittances/${remittanceId}/refund`);
    return response.data;
  },

  // Get limits for corridor
  getLimits: async (corridorSource: string, corridorDestination: string) => {
    const response = await apiClient.get("/remittances/limits", {
      params: { corridor_source: corridorSource, corridor_destination: corridorDestination },
    });
    return response.data;
  },

  // Get blockchain transactions for remittance
  getTransactions: async (remittanceId: string) => {
    const response = await apiClient.get(`/remittances/${remittanceId}/transactions`);
    return response.data;
  },
};

// === MONITORING DASHBOARD API ===
export const monitoringAPI = {
  // Dashboard snapshot
  getSnapshot: async () => {
    const response = await apiClient.get("/dashboard/snapshot");
    return response.data;
  },

  // Health check
  getHealth: async () => {
    const response = await apiClient.get("/dashboard/health");
    return response.data;
  },

  // Metrics
  getRemittanceMetrics: async () => {
    const response = await apiClient.get("/dashboard/metrics/remittances");
    return response.data;
  },

  getFinancialMetrics: async () => {
    const response = await apiClient.get("/dashboard/metrics/financial");
    return response.data;
  },

  getQueueMetrics: async () => {
    const response = await apiClient.get("/dashboard/metrics/queue");
    return response.data;
  },

  getSystemMetrics: async () => {
    const response = await apiClient.get("/dashboard/metrics/system");
    return response.data;
  },

  // Status
  getSystemStatus: async () => {
    const response = await apiClient.get("/dashboard/status");
    return response.data;
  },

  getServiceStatus: async (serviceName: string) => {
    const response = await apiClient.get(`/dashboard/status/service/${serviceName}`);
    return response.data;
  },

  // Alerts
  listAlerts: async (params?: { status?: string; severity?: string; limit?: number }) => {
    const response = await apiClient.get("/dashboard/alerts", { params });
    return response.data;
  },

  getAlertSummary: async () => {
    const response = await apiClient.get("/dashboard/alerts/summary");
    return response.data;
  },

  getAlert: async (alertId: string) => {
    const response = await apiClient.get(`/dashboard/alerts/${alertId}`);
    return response.data;
  },

  acknowledgeAlert: async (alertId: string, acknowledgedBy: string, comment?: string) => {
    const response = await apiClient.post(`/dashboard/alerts/${alertId}/acknowledge`, {
      acknowledged_by: acknowledgedBy,
      comment,
    });
    return response.data;
  },

  resolveAlert: async (alertId: string) => {
    const response = await apiClient.post(`/dashboard/alerts/${alertId}/resolve`);
    return response.data;
  },

  silenceAlert: async (alertId: string, durationMinutes: number, reason?: string) => {
    const response = await apiClient.post(`/dashboard/alerts/${alertId}/silence`, {
      duration_minutes: durationMinutes,
      reason,
    });
    return response.data;
  },

  // Alert Rules
  listAlertRules: async () => {
    const response = await apiClient.get("/dashboard/rules");
    return response.data;
  },

  createAlertRule: async (data: {
    name: string;
    type: string;
    severity: string;
    metric: string;
    operator: string;
    threshold: number;
    duration_seconds?: number;
    notify_channels?: string[];
    description?: string;
  }) => {
    const response = await apiClient.post("/dashboard/rules", data);
    return response.data;
  },

  updateAlertRule: async (ruleId: string, data: {
    name?: string;
    severity?: string;
    threshold?: number;
    enabled?: boolean;
    notify_channels?: string[];
  }) => {
    const response = await apiClient.put(`/dashboard/rules/${ruleId}`, data);
    return response.data;
  },

  deleteAlertRule: async (ruleId: string) => {
    await apiClient.delete(`/dashboard/rules/${ruleId}`);
  },
};

export default apiClient;
