import { useEffect, useState, useRef } from 'react';
import { agentsApi } from '../lib/api';
import { useWebSocket } from '../lib/websocket';
import { ChangelogEntry, ReadmeUpdate, DependencyGraph, AgentState } from '../types/agents';

interface LogWindowProps {
  agents: string[];
  className?: string;
}

interface ActivityMessage {
  timestamp: string;
  type: 'log' | 'status' | 'changelog' | 'readme' | 'dependency' | 'api';
  content: string;
  agent?: string;
  level: 'info' | 'warning' | 'error';
  details?: string;
}

export function LogWindow({ agents, className = '' }: LogWindowProps) {
  const [logs, setLogs] = useState<ActivityMessage[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string | 'all'>('all');
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Handle WebSocket messages
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
      setLogs(prev => [...prev, activityMessage!].sort((a, b) => b.timestamp.localeCompare(a.timestamp)));
    }
  };

  useWebSocket({ onMessage: handleMessage });

  // Convert backend log message to ActivityMessage
  const parseBackendLog = (log: string): ActivityMessage => {
    const timestamp = log.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0] || '';
    const isError = log.includes(' ERROR ');
    const isWarning = log.includes(' WARNING ');
    
    // Parse controller logs
    if (log.includes('swarm_controller')) {
      const message = log.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - swarm_controller - /, '');
      return {
        timestamp,
        type: 'log',
        agent: 'controller',
        content: message,
        level: isError ? 'error' : isWarning ? 'warning' : 'info'
      };
    }
    
    // Parse HTTP request logs
    if (log.includes('HTTP/1.1')) {
      const [method, path, status] = log.match(/(?:"(GET|POST) ([^"]+) HTTP\/1\.1") (\d{3})/i)?.slice(1) || [];
      const isError = status && parseInt(status) >= 400;
      return {
        timestamp,
        type: 'api',
        agent: 'controller',
        content: `${method} ${path}`,
        level: isError ? 'error' : 'info',
        details: status
      } as const;
    }
    
    // Parse agent logs
    const agentMatch = log.match(/agent_code_mon_(\w+)\.py/);
    const agent = agentMatch ? agentMatch[1] : '';
    const message = log.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - /, '');
    
    return {
      timestamp,
      type: 'log',
      agent,
      content: message,
      level: isError ? 'error' : isWarning ? 'warning' : 'info'
    };
  };

  // Fetch logs for all agents periodically
  useEffect(() => {
    let isMounted = true;
    let errorCount = 0;
    let lastFetchTime = 0;
    const minInterval = 1000; // Minimum time between fetches
    const maxInterval = 5000; // Maximum time between fetches
    const maxErrorBackoff = 30000; // Maximum backoff time on error

    const fetchLogs = async () => {
      const now = Date.now();
      const timeSinceLastFetch = now - lastFetchTime;
      
      // Ensure minimum time between fetches
      if (timeSinceLastFetch < minInterval) {
        return;
      }

      try {
        lastFetchTime = now;
        
        // Fetch logs sequentially to avoid overwhelming the backend
        const allLogs: string[] = [];
        for (const agent of agents) {
          if (!isMounted) return; // Stop if component unmounted
          const logs = await agentsApi.getAgentLogs(agent, 100); // Reduced from 1000
          allLogs.push(...logs);
        }
        
        if (!isMounted) return;

        // Convert log strings to ActivityMessage format
        const logMessages: ActivityMessage[] = allLogs.map(parseBackendLog);

        // Filter logs if an agent is selected
        const filteredLogs = selectedAgent === 'all' 
          ? logMessages
          : logMessages.filter(log => log.agent === selectedAgent);

        setLogs(filteredLogs);

        // Auto-scroll to bottom if enabled
        if (autoScroll && logContainerRef.current) {
          logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }

        // Reset error count on success
        errorCount = 0;
      } catch (error) {
        console.error('Error fetching logs:', error);
        errorCount++;
      }
    };

    // Initial fetch
    fetchLogs();

    // Set up polling with dynamic interval based on error count
    const interval = setInterval(() => {
      const backoffTime = Math.min(
        maxInterval * Math.pow(2, errorCount),
        maxErrorBackoff
      );
      fetchLogs();
    }, Math.max(minInterval, Math.min(maxInterval, errorCount ? maxInterval : minInterval)));

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [agents, autoScroll, selectedAgent]);

  const handleClear = () => {
    setLogs([]);
  };

  const getMessageColor = (message: ActivityMessage) => {
    // Handle error and warning levels first
    if (message.level === 'error') return 'text-red-300';
    if (message.level === 'warning') return 'text-yellow-300';

    // Then handle specific message types
    switch (message.type) {
      case 'status': return 'text-blue-300';
      case 'changelog': return 'text-purple-300';
      case 'readme': return 'text-green-300';
      case 'dependency': return 'text-cyan-300';
      case 'api': return 'text-blue-200';
      default: return 'text-slate-300';
    }
  };

  return (
    <div className={`flex flex-col h-[40rem] ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white">Agent Activity</h2>
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value as string)}
            className="rounded-md bg-slate-800 border-slate-700 text-sm text-slate-300 focus:ring-0 focus:border-slate-600"
          >
            <option value="all">All Agents</option>
            {agents.map(agent => (
              <option key={agent} value={agent}>
                {agent.charAt(0).toUpperCase() + agent.slice(1)} Agent
              </option>
            ))}
          </select>
          <button
            onClick={handleClear}
            className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
          >
            Clear Logs
          </button>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">
            {logs.length} messages
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
        ref={logContainerRef}
        className="flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-900/50 font-mono text-sm"
      >
        <div className="p-4 space-y-1">
          {logs.map((message, index) => (
            <pre
              key={index}
              className={`whitespace-pre-wrap break-all font-mono text-xs ${getMessageColor(message)}`}
            >
              {/* Timestamp */}
              <span className="text-slate-500">{message.timestamp}</span>
              {' '}
              {/* Agent name highlight */}
              {message.agent && (
                <span className="font-semibold">
                  [{message.agent}]
                </span>
              )}
              {' '}
              {/* Type indicator for non-log messages */}
              {message.type !== 'log' && (
                <span className="font-semibold">
                  ({message.type})
                </span>
              )}
              {' '}
              {/* Message content */}
              {message.content}
              {/* Status code for API requests */}
              {message.type === 'api' && message.details && (
                <span className={parseInt(message.details) >= 400 ? 'text-red-400' : 'text-green-400'}>
                  {' '}{message.details}
                </span>
              )}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
} 