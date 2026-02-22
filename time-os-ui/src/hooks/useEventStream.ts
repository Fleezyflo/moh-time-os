// Custom hook for SSE connection to /api/v2/events/stream
import { useEffect, useRef, useCallback } from 'react';
import { useAuth } from '../components/auth/AuthContext';

interface EventData {
  type: string;
  data: unknown;
  timestamp?: string;
}

type EventCallback = (event: EventData) => void;

interface UseEventStreamOptions {
  onEvent?: EventCallback;
  onError?: (error: Error) => void;
  autoReconnect?: boolean;
  reconnectDelay?: number;
}

export function useEventStream({
  onEvent,
  onError,
  autoReconnect = true,
  reconnectDelay = 3000,
}: UseEventStreamOptions = {}) {
  const { token, isAuthenticated } = useAuth();
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const apiBase = import.meta.env.VITE_API_BASE_URL || '/api/v2';

  const connect = useCallback(() => {
    if (!isAuthenticated || !token) return;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      // EventSource doesn't support custom headers, so we pass token as query param
      const url = new URL(`${apiBase}/events/stream`, window.location.origin);
      url.searchParams.append('token', token);

      const eventSource = new EventSource(url.toString());

      eventSource.addEventListener('message', (event) => {
        try {
          const data = JSON.parse(event.data);
          onEvent?.({ type: 'message', data, timestamp: new Date().toISOString() });
        } catch (err) {
          console.error('Failed to parse event data:', err);
        }
      });

      eventSource.addEventListener('error', () => {
        const error = new Error('EventSource connection lost');
        onError?.(error);

        // Attempt to reconnect
        if (autoReconnect) {
          if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
          }
          reconnectTimeoutRef.current = setTimeout(connect, reconnectDelay);
        }
      });

      eventSource.addEventListener('ping', (event) => {
        try {
          const data = JSON.parse(event.data);
          onEvent?.({ type: 'ping', data, timestamp: new Date().toISOString() });
        } catch {
          // Ignore ping parsing errors
        }
      });

      eventSourceRef.current = eventSource;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Failed to connect to event stream');
      onError?.(error);

      if (autoReconnect) {
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = setTimeout(connect, reconnectDelay);
      }
    }
  }, [token, isAuthenticated, apiBase, autoReconnect, reconnectDelay, onEvent, onError]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected: eventSourceRef.current?.readyState === EventSource.OPEN,
    disconnect,
    reconnect: connect,
  };
}
