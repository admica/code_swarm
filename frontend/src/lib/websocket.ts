import { EventEmitter } from 'events';

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface WebSocketServiceConfig {
  url: string;
  initialMessage?: any;
  onMessage?: (data: any) => void;
  maxRetries?: number;
  retryDelay?: number;
  maxRetryDelay?: number;
  retryBackoff?: number;
  parseAsJson?: boolean;
}

interface WebSocketServiceInternalConfig {
  url: string;
  initialMessage: any | null;
  onMessage: ((data: any) => void) | null;
  maxRetries: number;
  retryDelay: number;
  maxRetryDelay: number;
  retryBackoff: number;
  parseAsJson: boolean;
}

class WebSocketService extends EventEmitter {
  private ws: WebSocket | null = null;
  private status: ConnectionStatus = 'disconnected';
  private connectionAttempts = 0;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private readonly config: WebSocketServiceInternalConfig;
  private isConnecting = false;

  constructor(config: WebSocketServiceConfig) {
    super();
    this.config = {
      url: config.url,
      initialMessage: config.initialMessage || null,
      onMessage: config.onMessage || null,
      maxRetries: config.maxRetries ?? 5,
      retryDelay: config.retryDelay ?? 2000,
      maxRetryDelay: config.maxRetryDelay ?? 30000,
      retryBackoff: config.retryBackoff ?? 1.5,
      parseAsJson: config.parseAsJson ?? true
    };
  }

  connect() {
    if (this.isConnecting || this.status === 'connected') {
      console.log(`Already ${this.isConnecting ? 'connecting to' : 'connected to'} ${this.config.url}`);
      return;
    }

    try {
      this.isConnecting = true;
      this.cleanup();
      
      this.setStatus('connecting');
      console.log(`Connecting to ${this.config.url}...`);

      const ws = new WebSocket(this.config.url);
      this.ws = ws;

      ws.onopen = () => {
        console.log(`Connected to ${this.config.url}`);
        this.setStatus('connected');
        this.connectionAttempts = 0;
        this.isConnecting = false;

        if (this.config.initialMessage) {
          ws.send(JSON.stringify(this.config.initialMessage));
        }
      };

      ws.onmessage = (event) => {
        try {
          let data = event.data;
          if (this.config.parseAsJson) {
            try {
              data = JSON.parse(event.data);
            } catch (e) {
              console.warn('Failed to parse message as JSON, using raw data:', e);
            }
          }
          this.emit('message', data);
          if (this.config.onMessage) {
            this.config.onMessage(data);
          }
        } catch (error) {
          console.error('Error processing message:', error);
        }
      };

      ws.onclose = (event) => {
        this.ws = null;
        this.isConnecting = false;
        const wasNormalClosure = event.code === 1000 || event.code === 1001;

        if (wasNormalClosure) {
          this.setStatus('disconnected');
          return;
        }

        this.setStatus('disconnected');
        this.handleReconnect();
      };

      ws.onerror = () => {
        this.isConnecting = false;
        this.setStatus('error');
      };
    } catch (error) {
      console.error('Error connecting to WebSocket:', error);
      this.isConnecting = false;
      this.setStatus('error');
      this.handleReconnect();
    }
  }

  private handleReconnect() {
    if (this.connectionAttempts >= this.config.maxRetries) {
      this.setStatus('error');
      this.emit('maxRetriesReached');
      return;
    }

    const nextAttempt = this.connectionAttempts + 1;
    const delay = Math.min(
      this.config.retryDelay * Math.pow(this.config.retryBackoff, this.connectionAttempts),
      this.config.maxRetryDelay
    );

    console.log(`Reconnecting in ${Math.round(delay/1000)}s (attempt ${nextAttempt}/${this.config.maxRetries})`);
    this.emit('reconnecting', { attempt: nextAttempt, delay });

    this.reconnectTimeout = setTimeout(() => {
      this.connectionAttempts = nextAttempt;
      this.connect();
    }, delay);
  }

  private setStatus(status: ConnectionStatus) {
    this.status = status;
    this.emit('statusChange', status);
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  disconnect() {
    this.cleanup();
    this.setStatus('disconnected');
  }

  private cleanup() {
    if (this.ws) {
      this.ws.close(1000, 'Normal closure');
      this.ws = null;
    }
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  send(data: any) {
    if (this.ws && this.status === 'connected') {
      this.ws.send(JSON.stringify(data));
    }
  }
}

// Create singleton instances for different WebSocket connections
export const logsWebSocket = new WebSocketService({
  url: 'ws://localhost:8000/ws/logs',
  parseAsJson: false  // Log messages are plain text
});

export const agentWebSocket = new WebSocketService({
  url: 'ws://localhost:8000/ws/agent',
  initialMessage: {
    type: 'frontend_connect',
    timestamp: new Date().toISOString()
  },
  parseAsJson: true  // Agent messages are JSON
});

// Custom hook for using WebSocket connections
import { useEffect, useState } from 'react';

export function useWebSocket(service: WebSocketService) {
  const [status, setStatus] = useState<ConnectionStatus>(service.getStatus());

  useEffect(() => {
    const handleStatusChange = (newStatus: ConnectionStatus) => {
      setStatus(newStatus);
    };

    service.on('statusChange', handleStatusChange);
    
    // Connect if not already connected
    if (service.getStatus() === 'disconnected') {
      service.connect();
    }

    return () => {
      service.removeListener('statusChange', handleStatusChange);
    };
  }, [service]);

  return status;
} 