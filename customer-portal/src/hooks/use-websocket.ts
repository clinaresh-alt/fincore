"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useSession } from "next-auth/react";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "error";

export interface WebSocketMessage {
  type: string;
  notification_type?: string;
  title?: string;
  message?: string;
  priority?: "low" | "medium" | "high" | "critical";
  data?: Record<string, unknown>;
  timestamp?: string;
  id?: string;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
  pingInterval?: number;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectInterval = 3000,
    pingInterval = 30000,
  } = options;

  const { data: session, status } = useSession();
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("disconnected");

  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const disconnect = useCallback(() => {
    cleanup();
    if (wsRef.current) {
      wsRef.current.close(1000, "Client disconnect");
      wsRef.current = null;
    }
    setConnectionStatus("disconnected");
  }, [cleanup]);

  const connect = useCallback(() => {
    // Solo conectar si hay sesión autenticada
    if (status !== "authenticated" || !session?.accessToken) {
      return;
    }

    // Limpiar conexión existente
    if (wsRef.current) {
      wsRef.current.close();
    }

    setConnectionStatus("connecting");

    const wsUrl = `${WS_URL}/api/v1/notifications/ws?token=${session.accessToken}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("[WebSocket] Connected");
      setConnectionStatus("connected");
      reconnectCountRef.current = 0;
      onConnect?.();

      // Iniciar ping interval
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, pingInterval);
    };

    ws.onmessage = (event) => {
      try {
        // Ignorar pongs
        if (event.data === "pong" || event.data === '{"type":"pong"}') {
          return;
        }

        const message: WebSocketMessage = JSON.parse(event.data);
        onMessage?.(message);
      } catch (error) {
        console.error("[WebSocket] Error parsing message:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("[WebSocket] Error:", error);
      setConnectionStatus("error");
      onError?.(error);
    };

    ws.onclose = (event) => {
      console.log("[WebSocket] Disconnected:", event.code, event.reason);
      cleanup();
      setConnectionStatus("disconnected");
      onDisconnect?.();

      // Intentar reconectar si no fue un cierre limpio
      if (event.code !== 1000 && reconnectCountRef.current < reconnectAttempts) {
        reconnectCountRef.current++;
        console.log(
          `[WebSocket] Reconnecting... Attempt ${reconnectCountRef.current}/${reconnectAttempts}`
        );
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectInterval);
      }
    };

    wsRef.current = ws;
  }, [
    session,
    status,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    cleanup,
    reconnectAttempts,
    reconnectInterval,
    pingInterval,
  ]);

  // Conectar cuando la sesión esté disponible
  useEffect(() => {
    if (status === "authenticated" && session?.accessToken) {
      connect();
    } else if (status === "unauthenticated") {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [status, session?.accessToken, connect, disconnect]);

  // Enviar mensaje
  const send = useCallback((data: string | object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      const message = typeof data === "string" ? data : JSON.stringify(data);
      wsRef.current.send(message);
    }
  }, []);

  return {
    connectionStatus,
    send,
    connect,
    disconnect,
    isConnected: connectionStatus === "connected",
  };
}
