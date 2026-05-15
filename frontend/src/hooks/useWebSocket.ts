import { useEffect, useRef, useCallback } from 'react';
import type { WSMessage } from '../types';

const BASE_WS_URL = (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000';

type MessageHandler = (message: WSMessage) => void;

interface UseWebSocketOptions {
  executionId: string | null;
  onMessage: MessageHandler;
  enabled?: boolean;
}

interface UseWebSocketReturn {
  connected: boolean;
  disconnect: () => void;
}

export function useWebSocket({
  executionId,
  onMessage,
  enabled = true,
}: UseWebSocketOptions): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const connectedRef = useRef(false);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef<MessageHandler>(onMessage);

  // Keep handler ref fresh without triggering reconnects
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onclose = null; // Prevent reconnect on manual close
      wsRef.current.close();
      wsRef.current = null;
    }
    connectedRef.current = false;
  }, []);

  const connect = useCallback(() => {
    if (!executionId || !enabled) return;

    const url = `${BASE_WS_URL}/ws/executions/${executionId}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        connectedRef.current = true;
      };

      ws.onmessage = (event: MessageEvent<string>) => {
        try {
          const message = JSON.parse(event.data) as WSMessage;
          onMessageRef.current(message);
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {
        connectedRef.current = false;
      };

      ws.onclose = (event) => {
        connectedRef.current = false;
        wsRef.current = null;

        // Reconnect on unexpected close (not manual)
        if (!event.wasClean && enabled && executionId) {
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, 2000);
        }
      };
    } catch {
      // WebSocket connection failed
    }
  }, [executionId, enabled]);

  useEffect(() => {
    if (!enabled || !executionId) {
      disconnect();
      return;
    }

    connect();

    return () => {
      disconnect();
    };
  }, [executionId, enabled, connect, disconnect]);

  return {
    connected: connectedRef.current,
    disconnect,
  };
}
