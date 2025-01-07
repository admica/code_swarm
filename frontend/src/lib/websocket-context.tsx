'use client';

import React, { createContext, useContext, useEffect, useRef } from 'react';
import { WebSocketClient } from './websocket';

interface WebSocketContextValue {
  subscribe: (topic: string, callback: (data: any) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  children: React.ReactNode;
}

export function WebSocketProvider({ children }: WebSocketProviderProps) {
  const wsRef = useRef<WebSocketClient | null>(null);
  const subscriptionsRef = useRef<Map<string, Set<(data: any) => void>>>(new Map());

  useEffect(() => {
    // Initialize WebSocket client
    wsRef.current = new WebSocketClient();
    wsRef.current.setMessageHandler((message: any) => {
      const { topic, data } = message;
      const callbacks = subscriptionsRef.current.get(topic);
      if (callbacks) {
        callbacks.forEach(callback => callback(data));
      }
    });

    return () => {
      wsRef.current?.disconnect();
    };
  }, []);

  const subscribe = (topic: string, callback: (data: any) => void) => {
    if (!subscriptionsRef.current.has(topic)) {
      subscriptionsRef.current.set(topic, new Set());
    }
    subscriptionsRef.current.get(topic)!.add(callback);

    return () => {
      const callbacks = subscriptionsRef.current.get(topic);
      if (callbacks) {
        callbacks.delete(callback);
        if (callbacks.size === 0) {
          subscriptionsRef.current.delete(topic);
        }
      }
    };
  };

  return (
    <WebSocketContext.Provider value={{ subscribe }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketSubscription(topic: string, callback: (data: any) => void) {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocketSubscription must be used within a WebSocketProvider');
  }

  useEffect(() => {
    return context.subscribe(topic, callback);
  }, [topic, callback, context]);
} 