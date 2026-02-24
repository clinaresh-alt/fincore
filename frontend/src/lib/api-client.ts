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
    const response = await apiClient.get("/projects", { params });
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
    const response = await apiClient.post("/projects", data);
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

  analyzeRisk: async (projectId: string, data: any) => {
    const response = await apiClient.post(
      `/projects/${projectId}/risk-analysis`,
      data
    );
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
