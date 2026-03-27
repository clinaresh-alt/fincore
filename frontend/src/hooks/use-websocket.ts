"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export type WebSocketStatus = "connecting" | "connected" | "disconnecting" | "disconnected" | "error";

export interface WebSocketMessage<T = Record<string, unknown>> {
  type: string;
  timestamp?: string;
  data?: T;
  channel?: string;
  error?: string;
}

export interface UseWebSocketOptions<T = Record<string, unknown>> {
  /** URL del WebSocket */
  url: string;
  /** Reconectar automaticamente */
  autoReconnect?: boolean;
  /** Intervalo inicial de reconexion (ms) */
  reconnectInterval?: number;
  /** Maximo de reintentos de reconexion */
  maxReconnectAttempts?: number;
  /** Usar backoff exponencial para reconexion */
  useExponentialBackoff?: boolean;
  /** Intervalo de ping/heartbeat (ms), 0 para desactivar */
  pingInterval?: number;
  /** Canales a los que suscribirse al conectar */
  subscribeChannels?: string[];
  /** Callback cuando se conecta */
  onConnect?: () => void;
  /** Callback cuando se desconecta */
  onDisconnect?: (event: CloseEvent) => void;
  /** Callback cuando hay error */
  onError?: (error: Event) => void;
  /** Callback para cada mensaje recibido */
  onMessage?: (message: WebSocketMessage<T>) => void;
  /** Callbacks por tipo de mensaje */
  messageHandlers?: Record<string, (data: T) => void>;
}

export interface UseWebSocketReturn<T = Record<string, unknown>> {
  /** Estado de la conexion */
  status: WebSocketStatus;
  /** Si esta conectado */
  isConnected: boolean;
  /** Ultimo mensaje recibido */
  lastMessage: WebSocketMessage<T> | null;
  /** Error actual */
  error: string | null;
  /** Contador de reconexiones */
  reconnectCount: number;
  /** Conectar manualmente */
  connect: () => void;
  /** Desconectar manualmente */
  disconnect: () => void;
  /** Enviar mensaje */
  send: (message: Record<string, unknown>) => boolean;
  /** Suscribirse a un canal */
  subscribe: (channel: string) => void;
  /** Desuscribirse de un canal */
  unsubscribe: (channel: string) => void;
}

export function useWebSocket<T = Record<string, unknown>>(
  options: UseWebSocketOptions<T>
): UseWebSocketReturn<T> {
  const {
    url,
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
    useExponentialBackoff = true,
    pingInterval = 30000,
    subscribeChannels = [],
    onConnect,
    onDisconnect,
    onError,
    onMessage,
    messageHandlers = {},
  } = options;

  const [status, setStatus] = useState<WebSocketStatus>("disconnected");
  const [lastMessage, setLastMessage] = useState<WebSocketMessage<T> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reconnectCount, setReconnectCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const subscribedChannelsRef = useRef<Set<string>>(new Set(subscribeChannels));
  const shouldReconnectRef = useRef(autoReconnect);
  const reconnectAttemptsRef = useRef(0);

  // Calcular delay de reconexion con backoff exponencial
  const getReconnectDelay = useCallback(() => {
    if (!useExponentialBackoff) return reconnectInterval;
    const attempt = reconnectAttemptsRef.current;
    const delay = Math.min(reconnectInterval * Math.pow(2, attempt), 60000); // Max 60s
    return delay + Math.random() * 1000; // Agregar jitter
  }, [reconnectInterval, useExponentialBackoff]);

  // Enviar mensaje
  const send = useCallback((message: Record<string, unknown>): boolean => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    console.warn("[WS] Cannot send message, WebSocket is not connected");
    return false;
  }, []);

  // Suscribirse a canal
  const subscribe = useCallback((channel: string) => {
    subscribedChannelsRef.current.add(channel);
    send({ type: "subscribe", channel });
  }, [send]);

  // Desuscribirse de canal
  const unsubscribe = useCallback((channel: string) => {
    subscribedChannelsRef.current.delete(channel);
    send({ type: "unsubscribe", channel });
  }, [send]);

  // Desconectar
  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    setStatus("disconnecting");

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close(1000, "Manual disconnect");
      wsRef.current = null;
    }

    setStatus("disconnected");
    reconnectAttemptsRef.current = 0;
    setReconnectCount(0);
  }, []);

  // Conectar
  const connect = useCallback(() => {
    // Evitar conexiones duplicadas
    if (wsRef.current?.readyState === WebSocket.OPEN ||
        wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    shouldReconnectRef.current = autoReconnect;
    setStatus("connecting");
    setError(null);

    try {
      wsRef.current = new WebSocket(url);

      wsRef.current.onopen = () => {
        console.log("[WS] Connected to", url);
        setStatus("connected");
        setError(null);
        reconnectAttemptsRef.current = 0;
        setReconnectCount(0);

        // Suscribirse a canales
        subscribedChannelsRef.current.forEach((channel) => {
          send({ type: "subscribe", channel });
        });

        // Iniciar ping interval
        if (pingInterval > 0) {
          pingIntervalRef.current = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({ type: "ping" }));
            }
          }, pingInterval);
        }

        onConnect?.();
      };

      wsRef.current.onclose = (event) => {
        console.log("[WS] Disconnected:", event.code, event.reason);
        setStatus("disconnected");

        // Limpiar ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current);
          pingIntervalRef.current = null;
        }

        onDisconnect?.(event);

        // Auto reconectar si corresponde
        if (shouldReconnectRef.current && !event.wasClean) {
          if (reconnectAttemptsRef.current < maxReconnectAttempts) {
            const delay = getReconnectDelay();
            console.log(`[WS] Reconnecting in ${Math.round(delay)}ms (attempt ${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);

            reconnectTimeoutRef.current = setTimeout(() => {
              reconnectAttemptsRef.current++;
              setReconnectCount((c) => c + 1);
              connect();
            }, delay);
          } else {
            console.error("[WS] Max reconnection attempts reached");
            setError("Se alcanzo el maximo de intentos de reconexion");
          }
        }
      };

      wsRef.current.onerror = (event) => {
        console.error("[WS] Error:", event);
        setStatus("error");
        setError("Error de conexion WebSocket");
        onError?.(event);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage<T> = JSON.parse(event.data);
          setLastMessage(message);

          // Ignorar pong
          if (message.type === "pong") return;

          // Callback general
          onMessage?.(message);

          // Handler especifico por tipo
          const handler = messageHandlers[message.type];
          if (handler && message.data) {
            handler(message.data);
          }
        } catch (err) {
          console.error("[WS] Error parsing message:", err);
        }
      };
    } catch (err) {
      console.error("[WS] Connection error:", err);
      setStatus("error");
      setError("No se pudo establecer conexion WebSocket");
    }
  }, [
    url,
    autoReconnect,
    pingInterval,
    maxReconnectAttempts,
    getReconnectDelay,
    send,
    onConnect,
    onDisconnect,
    onError,
    onMessage,
    messageHandlers,
  ]);

  // Conectar al montar
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    status,
    isConnected: status === "connected",
    lastMessage,
    error,
    reconnectCount,
    connect,
    disconnect,
    send,
    subscribe,
    unsubscribe,
  };
}
