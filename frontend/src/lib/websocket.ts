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
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    try {
      console.log('Attempting to connect to WebSocket:', this.url);
      this.updateStatus('connecting');
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected successfully');
        this.reconnectAttempts = 0;
        this.updateStatus('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.debug('WebSocket message received:', message);
          this.messageHandlers.forEach(handler => handler(message));
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
          console.error('Raw message:', event.data);
        }
      };

      this.ws.onclose = (event) => {
        console.log('WebSocket closed:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        });
        this.updateStatus('disconnected');
        this.scheduleReconnect();
      };

      this.ws.onerror = (event) => {
        // Log the entire event since the error details might be in different properties
        console.error('WebSocket error event:', {
          type: event.type,
          eventPhase: event.eventPhase,
          currentTarget: event.currentTarget,
          target: event.target,
          timeStamp: event.timeStamp,
          // Try to get any additional properties that might contain error info
          ...(event as any)
        });
        
        // Check if we can connect to the backend at all
        this.checkBackendAvailability();
        
        this.updateStatus('error');
        this.ws?.close();
      };

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      this.updateStatus('error');
      this.scheduleReconnect();
    }
  }

  private async checkBackendAvailability() {
    try {
      // Try to fetch from the HTTP endpoint to check if backend is running
      const response = await fetch('http://localhost:8000/api/info');
      if (!response.ok) {
        console.error('Backend server returned error:', response.status);
      } else {
        console.log('Backend server is running');
      }
    } catch (error) {
      console.error('Backend server appears to be down:', error);
    }
  }

  disconnect() {
    console.log('Disconnecting WebSocket');
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
    console.log('WebSocket status changed:', status);
    this.statusHandlers.forEach(handler => handler(status));
  }

  private scheduleReconnect() {
    if (this.reconnectTimeout) return;
    
    this.reconnectAttempts++;
    if (this.reconnectAttempts > this.maxReconnectAttempts) {
      console.error(`Max reconnection attempts (${this.maxReconnectAttempts}) reached`);
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 30000);
    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
    
    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      console.log(`Attempting reconnect #${this.reconnectAttempts}`);
      this.connect();
    }, delay);
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