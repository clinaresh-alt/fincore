import axios, { AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from "axios";

// Tipos de error de la API
export interface APIError {
  detail: string;
  code?: string;
  field?: string;
}

export interface APIErrorResponse {
  detail: string | APIError[];
  status_code?: number;
}

// Configuración base
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Cliente API con manejo de JWT en HttpOnly cookies.
 *
 * Seguridad:
 * - Los tokens JWT se almacenan en cookies HttpOnly (no accesibles desde JS)
 * - Las cookies son configuradas por el backend con flags Secure, SameSite
 * - El cliente solo envía las cookies automáticamente con withCredentials
 */
class ApiClient {
  private client: AxiosInstance;
  private isLoggingOut = false;
  private tokenConfigured = false;

  constructor() {
    this.client = axios.create({
      baseURL: `${API_URL}/api/v1`,
      timeout: 30000,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      // Enviar cookies automáticamente (para JWT HttpOnly)
      withCredentials: true,
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // Agregar headers de seguridad adicionales
        config.headers.set("X-Requested-With", "XMLHttpRequest");

        // Agregar timestamp para prevenir cache
        if (config.method === "get") {
          config.params = {
            ...config.params,
            _t: Date.now(),
          };
        }

        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<APIErrorResponse>) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & {
          _retry?: boolean;
        };

        // Manejar 401 Unauthorized - token expirado o inválido
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          // Solo disparar logout si el token ya fue configurado previamente
          // Si tokenConfigured es false, la autenticación aún se está inicializando
          if (this.tokenConfigured) {
            console.warn("[API] Token expirado o inválido. Redirigiendo al login...");
            this.handleAuthError();
          } else {
            console.log("[API] 401 recibido pero token aún no configurado, ignorando logout");
          }
          return Promise.reject(error);
        }

        // Manejar 403 Forbidden (KYC no completado, etc.)
        if (error.response?.status === 403) {
          const detail = error.response.data?.detail;
          if (typeof detail === "string" && detail.includes("KYC")) {
            // Redirigir a completar KYC
            if (typeof window !== "undefined") {
              window.location.href = "/verify-kyc";
            }
          }
        }

        // Manejar 429 Too Many Requests
        if (error.response?.status === 429) {
          console.warn("Rate limit alcanzado. Espera antes de reintentar.");
        }

        return Promise.reject(this.formatError(error));
      }
    );
  }

  private handleAuthError(): void {
    // No hacer nada en SSR
    if (typeof window === "undefined") {
      return;
    }

    // No redirigir si ya estamos en páginas de autenticación
    const authPaths = ["/login", "/register", "/forgot-password", "/api/auth"];
    const currentPath = window.location.pathname;
    if (authPaths.some(path => currentPath.startsWith(path))) {
      console.log("[API] Ya en página de auth, no redirigir");
      return;
    }

    // Verificar si ya estamos en proceso de logout (usar sessionStorage para persistir)
    const logoutInProgress = sessionStorage.getItem("logout_in_progress");
    if (this.isLoggingOut || logoutInProgress === "true") {
      console.log("[API] Logout ya en progreso, ignorando");
      return;
    }

    this.isLoggingOut = true;
    sessionStorage.setItem("logout_in_progress", "true");

    // Disparar evento para que los stores limpien su estado
    window.dispatchEvent(new CustomEvent("auth:logout"));

    console.log("[API] Redirigiendo a signout...");
    // Usar la API de NextAuth para hacer signOut y limpiar la sesión
    window.location.href = "/api/auth/signout?callbackUrl=/login";
  }

  // Método para resetear el estado de logout (llamar después de login exitoso)
  resetLogoutState(): void {
    this.isLoggingOut = false;
    this.tokenConfigured = false;
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("logout_in_progress");
    }
  }

  private formatError(error: AxiosError<APIErrorResponse>): Error {
    if (error.response?.data) {
      const { detail } = error.response.data;
      if (typeof detail === "string") {
        return new Error(detail);
      }
      if (Array.isArray(detail)) {
        const messages = detail.map((e) => e.detail || e.toString()).join(", ");
        return new Error(messages);
      }
    }

    if (error.message === "Network Error") {
      return new Error("Error de conexión. Verifica tu internet.");
    }

    return new Error(error.message || "Error desconocido");
  }

  // Métodos HTTP
  async get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  async put<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.put<T>(url, data);
    return response.data;
  }

  async patch<T>(url: string, data?: unknown): Promise<T> {
    const response = await this.client.patch<T>(url, data);
    return response.data;
  }

  async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }

  // Método especial para subir archivos
  async upload<T>(url: string, formData: FormData): Promise<T> {
    const response = await this.client.post<T>(url, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    });
    return response.data;
  }

  // Método para requests con firma de transacción (WebAuthn/TOTP)
  async postWithSignature<T>(
    url: string,
    data: unknown,
    signature: string
  ): Promise<T> {
    const response = await this.client.post<T>(url, data, {
      headers: {
        "X-Transaction-Signature": signature,
      },
    });
    return response.data;
  }
}

// Exportar instancia singleton
export const apiClient = new ApiClient();

/**
 * Configura el token de autorización para todas las llamadas.
 * Usar desde un provider que tenga acceso a la sesión de NextAuth.
 */
export function setAuthToken(token: string | null): void {
  if (token) {
    apiClient["client"].defaults.headers.common["Authorization"] = `Bearer ${token}`;
    apiClient["tokenConfigured"] = true;
    // Resetear estado de logout cuando se configura un nuevo token válido
    apiClient.resetLogoutState();
    console.log("[API] Token configurado correctamente");
  } else {
    delete apiClient["client"].defaults.headers.common["Authorization"];
    apiClient["tokenConfigured"] = false;
  }
}

/**
 * Obtiene una instancia del cliente con un token específico.
 * Útil para llamadas que necesitan un token temporal.
 */
export function getAuthenticatedClient(token: string) {
  return {
    get: <T>(url: string, params?: Record<string, unknown>): Promise<T> =>
      apiClient["client"].get<T>(url, {
        params,
        headers: { Authorization: `Bearer ${token}` }
      }).then(r => r.data),
    post: <T>(url: string, data?: unknown): Promise<T> =>
      apiClient["client"].post<T>(url, data, {
        headers: { Authorization: `Bearer ${token}` }
      }).then(r => r.data),
    put: <T>(url: string, data?: unknown): Promise<T> =>
      apiClient["client"].put<T>(url, data, {
        headers: { Authorization: `Bearer ${token}` }
      }).then(r => r.data),
    delete: <T>(url: string): Promise<T> =>
      apiClient["client"].delete<T>(url, {
        headers: { Authorization: `Bearer ${token}` }
      }).then(r => r.data),
  };
}

// Exportar tipos útiles
export type { AxiosError };
