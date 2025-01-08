import { useEffect, useState, useRef, useCallback } from 'react';
import { AgentMessage } from '../types/messages';

function isValidMessage(msg: any): msg is AgentMessage {
  if (!msg || typeof msg !== 'object') return false;
  if (!msg.type || typeof msg.type !== 'string') return false;
  if (!msg.timestamp || typeof msg.timestamp !== 'string') return false;
  
  // System messages don't require agent field
  if (msg.type === 'system') {
    return typeof msg.message === 'string';
  }
  
  // All other messages require agent field
  if (!msg.agent || typeof msg.agent !== 'string') return false;
  
  return true;
}

export function AgentMessages({ className = '' }: { className?: string }) {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const MAX_MESSAGES = 1000;

  const connectWebSocket = useCallback(() => {
    try {
      console.log("Attempting to connect to agent WebSocket...");
      const ws = new WebSocket('ws://localhost:8000/ws/agent');
      wsRef.current = ws;
      setWsStatus('connecting');

      ws.onopen = () => {
        console.log("Agent WebSocket connected, sending frontend_connect message");
        // Send frontend connect message
        ws.send(JSON.stringify({
          type: 'frontend_connect',
          timestamp: new Date().toISOString()
        }));
        setWsStatus('connected');
        console.log("Frontend connect message sent");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log("Received agent message:", data);
          if (!isValidMessage(data)) {
            console.error('Invalid message format:', data);
            return;
          }
          setMessages(prev => {
            const updated = [...prev, data];
            return updated.slice(-MAX_MESSAGES);
          });
        } catch (error) {
          console.error('Error processing message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log("Agent WebSocket closed:", event.code, event.reason);
        setWsStatus('disconnected');
        wsRef.current = null;
      };

      ws.onerror = (error) => {
        console.error('Agent WebSocket error:', error);
        setWsStatus('error');
      };
    } catch (error) {
      console.error('Error connecting to agent messages:', error);
      setWsStatus('error');
    }
  }, []);

  useEffect(() => {
    connectWebSocket();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  const handleReconnect = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    connectWebSocket();
  };

  const renderMessageContent = (msg: AgentMessage) => {
    switch (msg.type) {
      case 'agent_connect':
        return (
          <div className="text-green-400">
            Agent connected: {msg.data.name}
            <div className="text-sm text-slate-400">
              Status: {msg.data.status.running ? 'Running' : 'Stopped'}
              {msg.data.status.current_task && ` | Task: ${msg.data.status.current_task}`}
            </div>
          </div>
        );

      case 'agent_status':
        return (
          <div>
            <div className="text-blue-400">Status update from {msg.data.name}</div>
            <div className="text-slate-300">
              Running: {msg.data.running ? 'Yes' : 'No'}
              {msg.data.current_task && ` | Task: ${msg.data.current_task}`}
              <div className="text-sm text-slate-400">
                Health: {msg.data.health.status}
                {msg.data.monitor_path && ` | Path: ${msg.data.monitor_path}`}
              </div>
            </div>
          </div>
        );

      case 'agent_activity':
        return (
          <div className="text-cyan-400">
            {msg.data.action}: {msg.data.file_path}
            {msg.data.details && (
              <pre className="mt-1 text-xs text-slate-400 overflow-auto">
                {JSON.stringify(msg.data.details, null, 2)}
              </pre>
            )}
          </div>
        );

      case 'system':
        return (
          <div className="text-yellow-400">
            {msg.message}
          </div>
        );

      case 'log':
        return (
          <div className={`${
            msg.level === 'error' ? 'text-red-400' :
            msg.level === 'warning' ? 'text-yellow-400' :
            msg.level === 'debug' ? 'text-slate-400' :
            'text-slate-300'
          }`}>
            [{msg.category}] {msg.message}
            {msg.data && (
              <pre className="mt-1 text-xs text-slate-400 overflow-auto">
                {JSON.stringify(msg.data, null, 2)}
              </pre>
            )}
          </div>
        );

      case 'ai_analysis':
        return (
          <div>
            <div className="text-purple-400">AI Analysis for {msg.data.file_path}</div>
            <div className="text-slate-300 whitespace-pre-wrap">{msg.data.analysis}</div>
            {msg.data.metrics && (
              <pre className="mt-1 text-xs text-slate-400 overflow-auto">
                {JSON.stringify(msg.data.metrics, null, 2)}
              </pre>
            )}
          </div>
        );

      default:
        return (
          <pre className="text-xs text-slate-400 overflow-auto">
            {JSON.stringify(msg, null, 2)}
          </pre>
        );
    }
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-lg font-semibold text-white">Agent Messages</h2>
        <div className="flex items-center gap-2">
          <div className={`px-2 py-1 rounded text-xs font-medium ${
            wsStatus === 'connected' ? 'bg-green-900/50 text-green-300' :
            wsStatus === 'connecting' ? 'bg-yellow-900/50 text-yellow-300' :
            wsStatus === 'error' ? 'bg-red-900/50 text-red-300' :
            'bg-slate-700 text-slate-300'
          }`}>
            {wsStatus}
          </div>
          {(wsStatus === 'error' || wsStatus === 'disconnected') && (
            <button
              onClick={handleReconnect}
              className="px-2 py-1 rounded text-xs font-medium bg-blue-900/50 text-blue-300 hover:bg-blue-900"
            >
              Reconnect
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-auto bg-slate-900 rounded p-4">
        {messages.map((msg, i) => (
          <div key={i} className="mb-3 text-sm border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-slate-500">{new Date(msg.timestamp).toLocaleTimeString()}</span>
              <span className="text-slate-400">{msg.type}</span>
              <span className="text-slate-500">{msg.agent}</span>
            </div>
            {renderMessageContent(msg)}
          </div>
        ))}
      </div>
    </div>
  );
} 