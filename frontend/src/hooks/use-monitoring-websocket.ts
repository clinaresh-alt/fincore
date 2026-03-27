"use client";

import { useMemo, useCallback } from "react";
import { useWebSocket, WebSocketStatus } from "./use-websocket";

// Tipos de datos de monitoreo
export interface MetricsUpdateData {
  remittance_metrics?: Record<string, unknown>;
  financial_metrics?: Record<string, unknown>;
  queue_metrics?: Record<string, unknown>;
  system_metrics?: Record<string, unknown>;
  system_status?: Record<string, unknown>;
  alert_summary?: Record<string, unknown>;
}

export interface AlertData {
  id: string;
  type: string;
  severity: string;
  title: string;
  message: string;
  triggered_at?: string;
  resolved_at?: string;
  remittance_id?: string;
  job_id?: string;
}

export interface StatusChangeData {
  service: string;
  status: string;
  latency_ms?: number;
  error?: string;
  overall_status?: string;
}

export interface RemittanceUpdateData {
  id: string;
  status: string;
  previous_status?: string;
  amount_usdc?: number;
  amount_mxn?: number;
  updated_at: string;
}

export interface UseMonitoringWebSocketOptions {
  /** Callback para actualizaciones de metricas */
  onMetricsUpdate?: (data: MetricsUpdateData) => void;
  /** Callback cuando se dispara una alerta */
  onAlertTriggered?: (data: AlertData) => void;
  /** Callback cuando se resuelve una alerta */
  onAlertResolved?: (data: AlertData) => void;
  /** Callback para cambios de estado de servicios */
  onStatusChange?: (data: StatusChangeData) => void;
  /** Callback para actualizaciones de remesas */
  onRemittanceUpdate?: (data: RemittanceUpdateData) => void;
  /** Callback generico para cualquier mensaje */
  onMessage?: (type: string, data: Record<string, unknown>) => void;
  /** Reconectar automaticamente */
  autoReconnect?: boolean;
  /** Intervalo de reconexion inicial (ms) */
  reconnectInterval?: number;
  /** Maximo intentos de reconexion */
  maxReconnectAttempts?: number;
}

export interface UseMonitoringWebSocketReturn {
  /** Estado de la conexion */
  status: WebSocketStatus;
  /** Si esta conectado */
  isConnected: boolean;
  /** Error actual */
  error: string | null;
  /** Contador de reconexiones */
  reconnectCount: number;
  /** Conectar manualmente */
  connect: () => void;
  /** Desconectar manualmente */
  disconnect: () => void;
  /** Enviar mensaje al servidor */
  sendMessage: (message: Record<string, unknown>) => boolean;
  /** Suscribirse a canal especifico */
  subscribeToChannel: (channel: string) => void;
  /** Desuscribirse de canal */
  unsubscribeFromChannel: (channel: string) => void;
}

/**
 * Hook para conectarse al WebSocket de monitoreo del dashboard
 * Maneja automaticamente la reconexion, heartbeat y routing de mensajes
 */
export function useMonitoringWebSocket(
  options: UseMonitoringWebSocketOptions = {}
): UseMonitoringWebSocketReturn {
  const {
    onMetricsUpdate,
    onAlertTriggered,
    onAlertResolved,
    onStatusChange,
    onRemittanceUpdate,
    onMessage,
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options;

  // Construir URL del WebSocket
  const wsUrl = useMemo(() => {
    if (typeof window === "undefined") return "";

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";

    if (apiUrl.startsWith("http")) {
      return apiUrl.replace(/^http/, "ws") + "/dashboard/ws";
    }

    return `${wsProtocol}//${window.location.host}/api/v1/dashboard/ws`;
  }, []);

  // Handler de mensajes con routing
  const handleMessage = useCallback(
    (message: { type: string; data?: Record<string, unknown> }) => {
      const { type, data } = message;

      // Callback generico
      if (onMessage && data) {
        onMessage(type, data);
      }

      // Routing por tipo
      if (!data) return;

      switch (type) {
        case "metrics_update":
          onMetricsUpdate?.(data as unknown as MetricsUpdateData);
          break;
        case "alert_triggered":
          onAlertTriggered?.(data as unknown as AlertData);
          break;
        case "alert_resolved":
          onAlertResolved?.(data as unknown as AlertData);
          break;
        case "status_change":
          onStatusChange?.(data as unknown as StatusChangeData);
          break;
        case "remittance_update":
          onRemittanceUpdate?.(data as unknown as RemittanceUpdateData);
          break;
      }
    },
    [onMetricsUpdate, onAlertTriggered, onAlertResolved, onStatusChange, onRemittanceUpdate, onMessage]
  );

  // Usar el hook generico
  const {
    status,
    isConnected,
    error,
    reconnectCount,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
  } = useWebSocket({
    url: wsUrl,
    autoReconnect,
    reconnectInterval,
    maxReconnectAttempts,
    useExponentialBackoff: true,
    pingInterval: 30000,
    subscribeChannels: ["monitoring", "alerts"],
    onMessage: handleMessage,
    onConnect: () => {
      console.log("[Monitoring WS] Connected successfully");
    },
    onDisconnect: (event) => {
      console.log("[Monitoring WS] Disconnected:", event.code);
    },
  });

  return {
    status,
    isConnected,
    error,
    reconnectCount,
    connect,
    disconnect,
    sendMessage: send,
    subscribeToChannel: subscribe,
    unsubscribeFromChannel: unsubscribe,
  };
}
