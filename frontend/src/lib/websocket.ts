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
  private maxReconnectAttempts = 10;
  private backendAvailable = true;
  private pingInterval: NodeJS.Timeout | null = null;
  private pongTimeout: NodeJS.Timeout | null = null;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    // Don't try to connect if backend is known to be down
    if (!this.backendAvailable) {
      console.log('Backend is not available, skipping WebSocket connection attempt');
      return;
    }

    try {
      console.log('Attempting to connect to WebSocket:', this.url);
      this.updateStatus('connecting');
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected successfully');
        this.reconnectAttempts = 0;
        this.backendAvailable = true;
        this.updateStatus('connected');
        this.startPingPong();
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.debug('WebSocket message received:', message);
          
          // Handle ping/pong messages
          if (message.type === 'pong') {
            this.handlePong();
            return;
          }
          
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
        this.checkBackendAndReconnect();
      };

      this.ws.onerror = (event) => {
        console.error('WebSocket connection failed');
        this.updateStatus('error');
        this.ws?.close();
        this.checkBackendAndReconnect();
      };

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      this.updateStatus('error');
      this.checkBackendAndReconnect();
    }
  }

  private async checkBackendAndReconnect() {
    try {
      console.log('Checking backend availability...');
      const response = await fetch('http://localhost:8000/api/info');
      
      if (response.ok) {
        console.log('Backend is available, scheduling reconnect');
        this.backendAvailable = true;
        this.scheduleReconnect();
      } else {
        console.error('Backend returned error:', response.status);
        this.backendAvailable = false;
        this.updateStatus('error');
      }
    } catch (error) {
      console.error('Backend appears to be down:', error);
      this.backendAvailable = false;
      this.updateStatus('error');
      
      // Schedule a check for backend availability
      setTimeout(() => this.checkBackendAndReconnect(), 5000);
    }
  }

  disconnect() {
    console.log('Disconnecting WebSocket');
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
    if (this.pongTimeout) {
      clearTimeout(this.pongTimeout);
      this.pongTimeout = null;
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

  private startPingPong() {
    // Clear any existing intervals
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
    }
    if (this.pongTimeout) {
      clearTimeout(this.pongTimeout);
    }

    // Send a ping every 30 seconds
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
        
        // Set a timeout to close the connection if no pong is received
        this.pongTimeout = setTimeout(() => {
          console.log('No pong received, closing connection');
          this.ws?.close();
        }, 5000); // Wait 5 seconds for pong
      }
    }, 30000);
  }

  private handlePong() {
    if (this.pongTimeout) {
      clearTimeout(this.pongTimeout);
      this.pongTimeout = null;
    }
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