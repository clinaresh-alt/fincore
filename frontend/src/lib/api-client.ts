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

export default apiClient;
