"use client";

import { useMemo, useCallback } from "react";
import { useWebSocket, WebSocketStatus } from "./use-websocket";

// Tipos de datos de remesas
export interface RemittanceStatusUpdate {
  id: string;
  status: string;
  previous_status: string;
  updated_at: string;
  error_message?: string;
}

export interface RemittanceProgressUpdate {
  id: string;
  step: string;
  progress: number;
  message: string;
  timestamp: string;
}

export interface RemittanceCompletedData {
  id: string;
  status: "completed" | "failed";
  amount_usdc: number;
  amount_mxn: number;
  exchange_rate: number;
  fee_usdc: number;
  completed_at: string;
  tx_hash?: string;
  stp_tracking_code?: string;
  error_message?: string;
}

export interface RemittanceBlockchainUpdate {
  id: string;
  tx_hash: string;
  confirmations: number;
  required_confirmations: number;
  status: "pending" | "confirmed" | "failed";
}

export interface RemittanceSTPUpdate {
  id: string;
  stp_status: string;
  stp_tracking_code?: string;
  stp_timestamp?: string;
  error?: string;
}

export interface UseRemittanceWebSocketOptions {
  /** ID de remesa a monitorear (opcional, si no se pasa escucha todas) */
  remittanceId?: string;
  /** Callback para cambios de estado */
  onStatusChange?: (data: RemittanceStatusUpdate) => void;
  /** Callback para actualizaciones de progreso */
  onProgress?: (data: RemittanceProgressUpdate) => void;
  /** Callback cuando la remesa se completa */
  onCompleted?: (data: RemittanceCompletedData) => void;
  /** Callback para actualizaciones de blockchain */
  onBlockchainUpdate?: (data: RemittanceBlockchainUpdate) => void;
  /** Callback para actualizaciones de STP */
  onSTPUpdate?: (data: RemittanceSTPUpdate) => void;
  /** Callback generico para cualquier mensaje */
  onMessage?: (type: string, data: Record<string, unknown>) => void;
  /** Reconectar automaticamente */
  autoReconnect?: boolean;
}

export interface UseRemittanceWebSocketReturn {
  /** Estado de la conexion */
  status: WebSocketStatus;
  /** Si esta conectado */
  isConnected: boolean;
  /** Error actual */
  error: string | null;
  /** Conectar manualmente */
  connect: () => void;
  /** Desconectar manualmente */
  disconnect: () => void;
  /** Suscribirse a una remesa especifica */
  watchRemittance: (remittanceId: string) => void;
  /** Dejar de monitorear una remesa */
  unwatchRemittance: (remittanceId: string) => void;
}

/**
 * Hook para monitorear actualizaciones de remesas en tiempo real
 * Permite suscribirse a remesas especificas o escuchar todas las actualizaciones
 */
export function useRemittanceWebSocket(
  options: UseRemittanceWebSocketOptions = {}
): UseRemittanceWebSocketReturn {
  const {
    remittanceId,
    onStatusChange,
    onProgress,
    onCompleted,
    onBlockchainUpdate,
    onSTPUpdate,
    onMessage,
    autoReconnect = true,
  } = options;

  // Construir URL del WebSocket
  const wsUrl = useMemo(() => {
    if (typeof window === "undefined") return "";

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";

    let baseUrl: string;
    if (apiUrl.startsWith("http")) {
      baseUrl = apiUrl.replace(/^http/, "ws") + "/remittances/ws";
    } else {
      baseUrl = `${wsProtocol}//${window.location.host}/api/v1/remittances/ws`;
    }

    // Agregar ID de remesa si se especifica
    if (remittanceId) {
      return `${baseUrl}?remittance_id=${remittanceId}`;
    }

    return baseUrl;
  }, [remittanceId]);

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
        case "remittance.status_change":
          onStatusChange?.(data as unknown as RemittanceStatusUpdate);
          break;
        case "remittance.progress":
          onProgress?.(data as unknown as RemittanceProgressUpdate);
          break;
        case "remittance.completed":
        case "remittance.failed":
          onCompleted?.(data as unknown as RemittanceCompletedData);
          break;
        case "remittance.blockchain_update":
          onBlockchainUpdate?.(data as unknown as RemittanceBlockchainUpdate);
          break;
        case "remittance.stp_update":
          onSTPUpdate?.(data as unknown as RemittanceSTPUpdate);
          break;
      }
    },
    [onStatusChange, onProgress, onCompleted, onBlockchainUpdate, onSTPUpdate, onMessage]
  );

  // Canales iniciales
  const initialChannels = useMemo(() => {
    const channels = ["remittances"];
    if (remittanceId) {
      channels.push(`remittance:${remittanceId}`);
    }
    return channels;
  }, [remittanceId]);

  // Usar el hook generico
  const {
    status,
    isConnected,
    error,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
  } = useWebSocket({
    url: wsUrl,
    autoReconnect,
    reconnectInterval: 3000,
    maxReconnectAttempts: 15,
    useExponentialBackoff: true,
    pingInterval: 30000,
    subscribeChannels: initialChannels,
    onMessage: handleMessage,
    onConnect: () => {
      console.log("[Remittance WS] Connected");
    },
    onDisconnect: (event) => {
      console.log("[Remittance WS] Disconnected:", event.code);
    },
  });

  // Suscribirse a una remesa especifica
  const watchRemittance = useCallback((id: string) => {
    subscribe(`remittance:${id}`);
    send({ type: "watch", remittance_id: id });
  }, [subscribe, send]);

  // Dejar de monitorear una remesa
  const unwatchRemittance = useCallback((id: string) => {
    unsubscribe(`remittance:${id}`);
    send({ type: "unwatch", remittance_id: id });
  }, [unsubscribe, send]);

  return {
    status,
    isConnected,
    error,
    connect,
    disconnect,
    watchRemittance,
    unwatchRemittance,
  };
}
