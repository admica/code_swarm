import { useEffect } from 'react';

export type ConnectionStatus = 'connected' | 'connecting' | 'disconnected' | 'error';

interface WebSocketMessage {
  type: string;
  data: any;
}

interface WebSocketHookProps {
  onMessage: (data: WebSocketMessage) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
}

class WebSocketClient {
  private ws: WebSocket | null = null;
  private messageHandlers: Set<(message: WebSocketMessage) => void> = new Set();
  private statusHandlers: Set<(status: ConnectionStatus) => void> = new Set();
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private url = 'ws://localhost:8000/ws';

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.updateStatus('connecting');
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.updateStatus('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.messageHandlers.forEach(handler => handler(message));
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      this.ws.onclose = () => {
        this.updateStatus('disconnected');
        this.scheduleReconnect();
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.updateStatus('error');
        this.ws?.close();
      };

    } catch (error) {
      console.error('Error connecting to WebSocket:', error);
      this.updateStatus('error');
      this.scheduleReconnect();
    }
  }

  disconnect() {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  private updateStatus(status: ConnectionStatus) {
    this.statusHandlers.forEach(handler => handler(status));
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) return;
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      this.connect();
    }, 5000);
  }

  subscribe(handler: (message: WebSocketMessage) => void) {
    this.messageHandlers.add(handler);
    return () => this.messageHandlers.delete(handler);
  }

  subscribeToStatus(handler: (status: ConnectionStatus) => void) {
    this.statusHandlers.add(handler);
    return () => this.statusHandlers.delete(handler);
  }
}

export const wsClient = new WebSocketClient();

export function useWebSocket({ onMessage, onStatusChange }: WebSocketHookProps) {
  useEffect(() => {
    wsClient.connect();

    const unsubscribeMessage = wsClient.subscribe(onMessage);
    const unsubscribeStatus = onStatusChange 
      ? wsClient.subscribeToStatus(onStatusChange)
      : undefined;

    return () => {
      unsubscribeMessage();
      if (unsubscribeStatus) unsubscribeStatus();
      wsClient.disconnect();
    };
  }, [onMessage, onStatusChange]);
} 