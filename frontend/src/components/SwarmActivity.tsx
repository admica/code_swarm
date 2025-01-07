import { useEffect, useRef, useState } from 'react';
import { AgentState, ChangelogEntry, ReadmeUpdate, DependencyGraph } from '../types/agents';
import { agentsApi } from '../lib/api';

interface ActivityMessage {
  timestamp: string;
  type: 'status' | 'changelog' | 'readme' | 'dependency';
  agent: string;
  content: string;
  level: 'info' | 'warning' | 'error';
}

interface SwarmActivityProps {
  className?: string;
}

export function SwarmActivity({ className = '' }: SwarmActivityProps) {
  const [messages, setMessages] = useState<ActivityMessage[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const pollInterval = setInterval(async () => {
      try {
        const agents = await agentsApi.getAgents();
        // Process agent statuses
        Object.entries(agents).forEach(([name, state]) => {
          if (state.last_error) {
            setMessages(prev => [...prev, {
              timestamp: new Date().toISOString(),
              type: 'status',
              agent: name,
              content: state.last_error || 'Unknown error',
              level: 'error'
            }]);
          }
        });
      } catch (error) {
        console.error('Error polling agent status:', error);
      }
    }, 5000);

    return () => clearInterval(pollInterval);
  }, []);

  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, autoScroll]);

  const handleClear = () => {
    setMessages([]);
  };

  const getMessageColor = (message: ActivityMessage) => {
    if (message.level === 'error') return 'text-red-300';
    if (message.level === 'warning') return 'text-yellow-300';

    switch (message.type) {
      case 'status': return 'text-blue-300';
      case 'changelog': return 'text-purple-300';
      case 'readme': return 'text-green-300';
      case 'dependency': return 'text-cyan-300';
      default: return 'text-slate-300';
    }
  };

  return (
    <div className={`flex flex-col h-64 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white">Swarm Activity</h2>
          <button
            onClick={handleClear}
            className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
          >
            Clear
          </button>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">
            {messages.length} messages
          </span>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-slate-700 bg-slate-900 text-green-500 focus:ring-0"
            />
            <span className="text-sm text-slate-300">Auto-scroll</span>
          </label>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto bg-slate-900 rounded p-4">
        {messages.map((message, index) => (
          <div key={index} className="mb-2">
            <span className="text-xs text-slate-500">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
            <span className="ml-2 text-sm">
              <span className="text-slate-400">[{message.agent}]</span>
              <span className={`ml-2 ${getMessageColor(message)}`}>
                {message.content}
              </span>
            </span>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
} 