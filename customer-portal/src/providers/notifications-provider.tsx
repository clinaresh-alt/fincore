"use client";

import { createContext, useContext, useCallback, useState, useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { useWebSocket, type WebSocketMessage, type ConnectionStatus } from "@/hooks/use-websocket";
import { remittanceKeys } from "@/features/remittances/hooks/use-remittances";

// Tipos de notificación que nos interesan para remesas
const REMITTANCE_NOTIFICATION_TYPES = [
  "remittance_created",
  "remittance_locked",
  "remittance_processing",
  "remittance_disbursed",
  "remittance_completed",
  "remittance_failed",
  "remittance_cancelled",
  "remittance_refunded",
];

export interface Notification {
  id: string;
  type: string;
  title: string;
  message: string;
  priority: "low" | "medium" | "high" | "critical";
  data?: Record<string, unknown>;
  timestamp: string;
  read: boolean;
}

interface NotificationsContextValue {
  notifications: Notification[];
  unreadCount: number;
  connectionStatus: ConnectionStatus;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearNotifications: () => void;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (!context) {
    throw new Error("useNotifications must be used within NotificationsProvider");
  }
  return context;
}

interface NotificationsProviderProps {
  children: ReactNode;
}

export function NotificationsProvider({ children }: NotificationsProviderProps) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [notifications, setNotifications] = useState<Notification[]>([]);

  // Manejar mensajes WebSocket
  const handleMessage = useCallback(
    (message: WebSocketMessage) => {
      // Solo procesar notificaciones
      if (message.type !== "notification") return;

      const notification: Notification = {
        id: message.id || crypto.randomUUID(),
        type: message.notification_type || "info",
        title: message.title || "Notificación",
        message: message.message || "",
        priority: message.priority || "medium",
        data: message.data,
        timestamp: message.timestamp || new Date().toISOString(),
        read: false,
      };

      // Agregar a la lista
      setNotifications((prev) => [notification, ...prev].slice(0, 50)); // Max 50

      // Mostrar toast según prioridad y tipo
      showNotificationToast(notification, router, queryClient);

      // Invalidar queries relevantes para actualizar datos
      if (REMITTANCE_NOTIFICATION_TYPES.includes(notification.type)) {
        queryClient.invalidateQueries({ queryKey: remittanceKeys.all });
      }
    },
    [router, queryClient]
  );

  const handleConnect = useCallback(() => {
    console.log("[Notifications] WebSocket connected");
  }, []);

  const handleDisconnect = useCallback(() => {
    console.log("[Notifications] WebSocket disconnected");
  }, []);

  const { connectionStatus } = useWebSocket({
    onMessage: handleMessage,
    onConnect: handleConnect,
    onDisconnect: handleDisconnect,
  });

  // Calcular no leídas
  const unreadCount = notifications.filter((n) => !n.read).length;

  // Marcar como leída
  const markAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  // Marcar todas como leídas
  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  // Limpiar notificaciones
  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  return (
    <NotificationsContext.Provider
      value={{
        notifications,
        unreadCount,
        connectionStatus,
        markAsRead,
        markAllAsRead,
        clearNotifications,
      }}
    >
      {children}
    </NotificationsContext.Provider>
  );
}

// Helper para mostrar toasts según tipo de notificación
function showNotificationToast(
  notification: Notification,
  router: ReturnType<typeof useRouter>,
  _queryClient: ReturnType<typeof useQueryClient>
) {
  const { type, title, message, priority, data } = notification;

  // Determinar el tipo de toast
  const toastFn =
    priority === "critical" || type.includes("failed")
      ? toast.error
      : type.includes("completed") || type.includes("success")
      ? toast.success
      : type.includes("warning") || priority === "high"
      ? toast.warning
      : toast.info;

  // Acción de click según tipo
  const getAction = () => {
    if (type.includes("remittance") && data?.remittance_id) {
      return {
        label: "Ver detalle",
        onClick: () => router.push(`/remittances/${data.remittance_id}`),
      };
    }
    if (type === "kyc_status_change") {
      return {
        label: "Ver KYC",
        onClick: () => router.push("/verify-kyc"),
      };
    }
    return undefined;
  };

  const action = getAction();

  toastFn(title, {
    description: message,
    duration: priority === "critical" ? 10000 : priority === "high" ? 6000 : 4000,
    action: action
      ? {
          label: action.label,
          onClick: action.onClick,
        }
      : undefined,
  });
}
