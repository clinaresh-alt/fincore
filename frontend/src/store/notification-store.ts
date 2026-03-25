/**
 * Store de Notificaciones con WebSocket.
 * Gestiona conexion WebSocket y estado de notificaciones.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

// Tipos de notificacion
export type NotificationType =
  | "audit_started"
  | "audit_completed"
  | "audit_failed"
  | "audit_finding"
  | "compliance_alert"
  | "kyc_status_change"
  | "risk_alert"
  | "investment_received"
  | "investment_confirmed"
  | "dividend_available"
  | "project_status_change"
  | "project_milestone"
  | "system_alert"
  | "system_maintenance"
  | "info"
  | "warning"
  | "error"
  | "success";

export type NotificationPriority = "low" | "medium" | "high" | "critical";

export interface Notification {
  id: string;
  notification_type: NotificationType;
  priority: NotificationPriority;
  title: string;
  message: string;
  data?: Record<string, unknown>;
  is_read: boolean;
  read_at?: string;
  created_at: string;
}

export interface WebSocketMessage {
  type: string;
  notification_type: NotificationType;
  title: string;
  message: string;
  priority: NotificationPriority;
  data?: Record<string, unknown>;
  timestamp: string;
  id: string;
}

interface NotificationStore {
  // Estado
  notifications: Notification[];
  unreadCount: number;
  isConnected: boolean;
  isConnecting: boolean;
  connectionError: string | null;

  // WebSocket
  ws: WebSocket | null;

  // Preferencias (cacheadas)
  preferences: {
    enableSound: boolean;
    enableDesktop: boolean;
  };

  // Acciones
  connect: (token: string) => void;
  disconnect: () => void;
  reconnect: () => void;

  // Notificaciones
  addNotification: (notification: Notification | WebSocketMessage) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  deleteNotification: (id: string) => void;
  clearAll: () => void;
  fetchNotifications: () => Promise<void>;
  fetchUnreadCount: () => Promise<void>;

  // Preferencias
  setPreference: (key: keyof NotificationStore["preferences"], value: boolean) => void;
}

// URL base del API
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// URL del WebSocket
const getWsUrl = (token: string) => {
  const wsProtocol = API_BASE_URL.startsWith("https") ? "wss" : "ws";
  // Extraer solo host:puerto sin path (baseUrl puede incluir /api/v1)
  const urlMatch = API_BASE_URL.match(/^https?:\/\/([^/]+)/);
  const wsHost = urlMatch ? urlMatch[1] : "localhost:8000";
  return `${wsProtocol}://${wsHost}/api/v1/notifications/ws?token=${token}`;
};

// Helper para obtener token de localStorage
const getStoredToken = () => {
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token");
  }
  return null;
};

// Reproducir sonido de notificacion
const playNotificationSound = () => {
  try {
    const audio = new Audio("/sounds/notification.mp3");
    audio.volume = 0.5;
    audio.play().catch(() => {});
  } catch {
    // Ignorar errores de audio
  }
};

// Mostrar notificacion de escritorio
const showDesktopNotification = (title: string, body: string) => {
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification(title, {
      body,
      icon: "/favicon.ico",
      tag: "fincore-notification",
    });
  }
};

// Variables para reconexion
let reconnectAttempts = 0;
let reconnectTimeout: NodeJS.Timeout | null = null;
let storedToken: string | null = null;
let connectionId = 0; // Para evitar race conditions con StrictMode

export const useNotificationStore = create<NotificationStore>()(
  persist(
    (set, get) => ({
      // Estado inicial
      notifications: [],
      unreadCount: 0,
      isConnected: false,
      isConnecting: false,
      connectionError: null,
      ws: null,
      preferences: {
        enableSound: true,
        enableDesktop: false,
      },

      // Conectar WebSocket
      connect: (token: string) => {
        const { ws, isConnecting } = get();

        // Evitar conexiones duplicadas
        if (ws && ws.readyState === WebSocket.OPEN) return;
        if (isConnecting) return;

        storedToken = token;
        connectionId++; // Incrementar para invalidar conexiones anteriores
        const currentConnectionId = connectionId;

        set({ isConnecting: true, connectionError: null });

        const websocket = new WebSocket(getWsUrl(token));

        websocket.onopen = () => {
          // Verificar que esta conexion sigue siendo valida
          if (currentConnectionId !== connectionId) {
            websocket.close(1000, "Conexion obsoleta");
            return;
          }

          console.log("[WS] Conectado");
          reconnectAttempts = 0;
          set({
            ws: websocket,
            isConnected: true,
            isConnecting: false,
            connectionError: null,
          });

          // Fetch inicial de notificaciones
          get().fetchNotifications();
          get().fetchUnreadCount();
        };

        websocket.onmessage = (event) => {
          // Ignorar mensajes de conexiones obsoletas
          if (currentConnectionId !== connectionId) return;

          try {
            const message = JSON.parse(event.data) as WebSocketMessage;

            if (message.type === "notification") {
              get().addNotification(message);

              // Efectos secundarios
              const { preferences } = get();
              if (preferences.enableSound) {
                playNotificationSound();
              }
              if (preferences.enableDesktop) {
                showDesktopNotification(message.title, message.message);
              }
            }
          } catch (err) {
            console.error("[WS] Error parsing message:", err);
          }
        };

        websocket.onerror = (error) => {
          // Ignorar errores de conexiones obsoletas
          if (currentConnectionId !== connectionId) return;

          console.error("[WS] Error:", error);
          set({ connectionError: "Error de conexion WebSocket" });
        };

        websocket.onclose = (event) => {
          // Ignorar eventos de conexiones obsoletas
          if (currentConnectionId !== connectionId) return;

          console.log("[WS] Desconectado:", event.code, event.reason);
          set({ ws: null, isConnected: false, isConnecting: false });

          // Reconexion automatica (no reconectar si fue cierre limpio o sin token)
          if (event.code !== 1000 && storedToken && currentConnectionId === connectionId) {
            reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);

            console.log(`[WS] Reconectando en ${delay}ms (intento ${reconnectAttempts})`);

            reconnectTimeout = setTimeout(() => {
              if (storedToken && currentConnectionId === connectionId) {
                get().connect(storedToken);
              }
            }, delay);
          }
        };

        set({ ws: websocket });
      },

      // Desconectar
      disconnect: () => {
        const { ws } = get();
        storedToken = null;
        connectionId++; // Invalidar cualquier conexion en progreso

        if (reconnectTimeout) {
          clearTimeout(reconnectTimeout);
          reconnectTimeout = null;
        }

        // Solo cerrar si esta abierto (no si esta conectando para evitar errores)
        if (ws && ws.readyState === WebSocket.OPEN) {
          try {
            ws.close(1000, "Usuario desconectado");
          } catch {
            // Ignorar errores al cerrar
          }
        }

        set({ ws: null, isConnected: false, isConnecting: false });
      },

      // Reconectar manualmente
      reconnect: () => {
        if (storedToken) {
          get().disconnect();
          setTimeout(() => {
            if (storedToken) {
              get().connect(storedToken);
            }
          }, 500);
        }
      },

      // Agregar notificacion
      addNotification: (notification) => {
        const newNotif: Notification = {
          id: notification.id,
          notification_type: notification.notification_type,
          priority: notification.priority,
          title: notification.title,
          message: notification.message,
          data: notification.data,
          is_read: false,
          created_at: "timestamp" in notification ? notification.timestamp : notification.created_at,
        };

        set((state) => ({
          notifications: [newNotif, ...state.notifications].slice(0, 100), // Max 100
          unreadCount: state.unreadCount + 1,
        }));
      },

      // Marcar como leida
      markAsRead: async (id: string) => {
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, is_read: true, read_at: new Date().toISOString() } : n
          ),
          unreadCount: Math.max(0, state.unreadCount - 1),
        }));

        // Sync con backend
        try {
          const token = getStoredToken();
          await fetch(`${API_BASE_URL}/notifications/mark-read`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token && { Authorization: `Bearer ${token}` }),
            },
            body: JSON.stringify({ notification_ids: [id] }),
          });
        } catch {
          // Ignorar errores de sync
        }
      },

      // Marcar todas como leidas
      markAllAsRead: async () => {
        set((state) => ({
          notifications: state.notifications.map((n) => ({
            ...n,
            is_read: true,
            read_at: new Date().toISOString(),
          })),
          unreadCount: 0,
        }));

        try {
          const token = getStoredToken();
          await fetch(`${API_BASE_URL}/notifications/mark-read`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token && { Authorization: `Bearer ${token}` }),
            },
            body: JSON.stringify({ mark_all: true }),
          });
        } catch {
          // Ignorar errores de sync
        }
      },

      // Eliminar notificacion
      deleteNotification: async (id: string) => {
        const notification = get().notifications.find((n) => n.id === id);

        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
          unreadCount: notification && !notification.is_read
            ? Math.max(0, state.unreadCount - 1)
            : state.unreadCount,
        }));

        try {
          const token = getStoredToken();
          await fetch(`${API_BASE_URL}/notifications/${id}`, {
            method: "DELETE",
            headers: token ? { Authorization: `Bearer ${token}` } : {},
          });
        } catch {
          // Ignorar errores
        }
      },

      // Limpiar todas
      clearAll: () => {
        set({ notifications: [], unreadCount: 0 });
      },

      // Fetch de notificaciones del backend
      fetchNotifications: async () => {
        try {
          const token = getStoredToken();
          const headers: HeadersInit = token
            ? { Authorization: `Bearer ${token}` }
            : {};
          const response = await fetch(`${API_BASE_URL}/notifications?limit=50`, { headers });
          if (response.ok) {
            const data = await response.json();
            set({
              notifications: data.notifications,
              unreadCount: data.total_unread,
            });
          }
        } catch {
          console.error("Error fetching notifications");
        }
      },

      // Fetch solo del conteo
      fetchUnreadCount: async () => {
        try {
          const token = getStoredToken();
          const headers: HeadersInit = token
            ? { Authorization: `Bearer ${token}` }
            : {};
          const response = await fetch(`${API_BASE_URL}/notifications/unread-count`, { headers });
          if (response.ok) {
            const data = await response.json();
            set({ unreadCount: data.unread_count });
          }
        } catch {
          // Ignorar errores
        }
      },

      // Cambiar preferencia
      setPreference: (key, value) => {
        set((state) => ({
          preferences: { ...state.preferences, [key]: value },
        }));

        // Solicitar permisos de notificacion si se habilita
        if (key === "enableDesktop" && value && "Notification" in window) {
          Notification.requestPermission();
        }
      },
    }),
    {
      name: "fincore-notifications",
      partialize: (state) => ({
        preferences: state.preferences,
      }),
    }
  )
);

// Hook para obtener notificaciones no leidas
export const useUnreadNotifications = () => {
  const notifications = useNotificationStore((state) => state.notifications);
  return notifications.filter((n) => !n.is_read);
};

// Hook para notificaciones por tipo
export const useNotificationsByType = (type: NotificationType) => {
  const notifications = useNotificationStore((state) => state.notifications);
  return notifications.filter((n) => n.notification_type === type);
};

// Hook para notificaciones criticas
export const useCriticalNotifications = () => {
  const notifications = useNotificationStore((state) => state.notifications);
  return notifications.filter(
    (n) => n.priority === "critical" || n.priority === "high"
  );
};
