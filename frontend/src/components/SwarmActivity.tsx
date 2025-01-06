import { useEffect, useRef, useState } from 'react';
import { useWebSocket } from '../lib/websocket';
import { AgentState, ChangelogEntry, ReadmeUpdate, DependencyGraph } from '../types/agents';

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
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMessage = (message: any) => {
    const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
    let activityMessage: ActivityMessage | null = null;

    switch (message.type) {
      case 'agent_update':
        const agentState = message.data as AgentState;
        activityMessage = {
          timestamp: now,
          type: 'status',
          agent: agentState.name,
          content: `Agent ${agentState.running ? 'started' : 'stopped'}${agentState.last_error ? ` (Error: ${agentState.last_error})` : ''}`,
          level: agentState.last_error ? 'error' : 'info'
        };
        break;
      case 'changelog':
        const changelog = message.data as ChangelogEntry;
        activityMessage = {
          timestamp: now,
          type: 'changelog',
          agent: 'changelog',
          content: `New changes in ${changelog.file}: ${changelog.summary}`,
          level: 'info'
        };
        break;
      case 'readme':
        const readme = message.data as ReadmeUpdate;
        activityMessage = {
          timestamp: now,
          type: 'readme',
          agent: 'readme',
          content: `Updated README for ${readme.file}`,
          level: 'info'
        };
        break;
      case 'dependency':
        const deps = message.data as DependencyGraph;
        activityMessage = {
          timestamp: now,
          type: 'dependency',
          agent: 'deps',
          content: `Updated dependency graph${deps.aiInsights ? ' with AI analysis' : ''}`,
          level: 'info'
        };
        break;
    }

    if (activityMessage) {
      setMessages(prev => [...prev, activityMessage!]);
      
      if (autoScroll && containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    }
  };

  useWebSocket({ onMessage: handleMessage });

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

      <div
        ref={containerRef}
        className="flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-900/50 font-mono text-sm"
      >
        <div className="p-4 space-y-1">
          {messages.map((message, index) => (
            <pre
              key={index}
              className={`whitespace-pre-wrap break-all font-mono text-xs ${getMessageColor(message)}`}
            >
              <span className="text-slate-500">{message.timestamp}</span>
              {' '}
              <span className="font-semibold">[{message.agent}]</span>
              {' '}
              <span className="font-semibold">({message.type})</span>
              {' '}
              {message.content}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
} 