import { useEffect, useState, useCallback } from 'react';
import { agentWebSocket, useWebSocket } from '../lib/websocket';
import { AgentMessage } from '../types/messages';

export function AgentMessages({ className = '' }: { className?: string }) {
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const wsStatus = useWebSocket(agentWebSocket);
  const MAX_MESSAGES = 1000;

  // Handle incoming messages
  useEffect(() => {
    const handleMessage = (data: AgentMessage) => {
      console.log("Received agent message:", data);
      setMessages(prev => {
        const updated = [...prev, data];
        return updated.slice(-MAX_MESSAGES);
      });
    };

    agentWebSocket.on('message', handleMessage);

    return () => {
      agentWebSocket.removeListener('message', handleMessage);
    };
  }, []);

  const handleReconnect = () => {
    agentWebSocket.connect();
  };

  const renderMessageContent = (message: AgentMessage) => {
    switch (message.type) {
      case 'agent_connect':
        return `Agent ${message.data.name} connected`;
      case 'agent_status':
        return `Agent ${message.data.name} status: ${message.data.running ? 'running' : 'stopped'}`;
      case 'agent_activity':
        return `${message.data.action} - ${message.data.file_path}`;
      case 'system':
        return message.message;
      default:
        return JSON.stringify(message);
    }
  };

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white">Agent Messages</h2>
          <div className={`px-2 py-1 rounded text-xs font-medium ${
            wsStatus === 'connected' ? 'bg-green-900/50 text-green-300' :
            wsStatus === 'connecting' ? 'bg-yellow-900/50 text-yellow-300' :
            wsStatus === 'error' ? 'bg-red-900/50 text-red-300' :
            'bg-slate-700 text-slate-300'
          }`}>
            {wsStatus}
          </div>
          {wsStatus === 'error' && (
            <button
              onClick={handleReconnect}
              className="px-2 py-1 rounded text-xs font-medium bg-blue-900/50 text-blue-300 hover:bg-blue-900"
            >
              Retry Connection
            </button>
          )}
        </div>
        <span className="text-xs text-slate-400">
          {messages.length} messages {messages.length === MAX_MESSAGES && '(max reached)'}
        </span>
      </div>
      <div className="flex-1 overflow-auto bg-slate-900/50 border border-slate-800 rounded-lg p-2">
        <div className="space-y-1">
          {messages.map((message, index) => (
            <div key={index} className="flex items-start text-sm hover:bg-slate-800/30 p-1 rounded">
              <span className="text-slate-500 shrink-0 w-14">
                {new Date(message.timestamp).toLocaleTimeString().split(':').slice(0, 2).join(':')}
              </span>
              <span className="text-slate-400 shrink-0 w-24 px-2">
                [{message.agent || 'system'}]
              </span>
              <span className="text-slate-300 break-all">
                {renderMessageContent(message)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
} 