import { useEffect, useState, useRef, useCallback } from 'react';
import { agentsApi } from '../lib/api';
import { ChangelogEntry, ReadmeUpdate, DependencyGraph, AgentState } from '../types/agents';
import { logsWebSocket, useWebSocket } from '../lib/websocket';

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
  const wsStatus = useWebSocket(logsWebSocket);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const autoScrollAnchorRef = useRef<HTMLDivElement>(null);

  const MAX_LOGS = 1000; // Maximum number of logs to keep in memory

  // Add log with rate limiting
  const addLog = useCallback((newLog: ActivityMessage) => {
    setLogs(prev => {
      const updated = [...prev, newLog];
      // Keep only the last MAX_LOGS entries
      return updated.slice(-MAX_LOGS);
    });

    // Scroll to bottom if auto-scroll is enabled
    if (autoScroll && autoScrollAnchorRef.current) {
      autoScrollAnchorRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [autoScroll, MAX_LOGS]);

  // Convert backend log message to ActivityMessage
  const parseBackendLog = (log: string): ActivityMessage | null => {
    try {
      const timestamp = log.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0] || new Date().toISOString();
      
      // Look for the last log level indicator in case of wrapped messages
      const logParts = log.split(/- (?:INFO|WARNING|ERROR) -/);
      const lastPart = logParts[logParts.length - 1].trim();
      
      // Determine the log level - check the whole message for level indicators
      const level = log.includes(' ERROR - ') 
        ? 'error' 
        : log.includes(' WARNING - ') 
          ? 'warning' 
          : 'info';
      
      // Parse controller logs
      if (log.includes('swarm_controller')) {
        const message = log.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - swarm_controller - (?:INFO|WARNING|ERROR) - /, '');
        return {
          timestamp,
          type: 'log',
          agent: 'controller',
          content: message,
          level
        };
      }
      
      // Parse agent logs - extract actual message content
      const agentMatch = log.match(/agent_code_mon_(\w+)/);
      const agent = agentMatch ? agentMatch[1] : '';
      
      // Get the actual message content, handling both wrapped and direct logs
      let message = lastPart;
      if (message.includes(': ')) {
        message = message.split(': ').slice(1).join(': ');
      }
      
      return {
        timestamp,
        type: 'log',
        agent,
        content: message,
        level
      };
    } catch (error) {
      console.error('Error parsing log:', error);
      return null;
    }
  };

  // Handle incoming WebSocket messages
  useEffect(() => {
    const handleMessage = (data: string) => {
      const log = parseBackendLog(data);
      if (log) {
        addLog(log);
      }
    };

    logsWebSocket.on('message', handleMessage);

    return () => {
      logsWebSocket.removeListener('message', handleMessage);
    };
  }, [addLog]);

  // Add connection status messages
  useEffect(() => {
    if (wsStatus === 'connected') {
      addLog({
        timestamp: new Date().toISOString(),
        type: 'status',
        agent: 'system',
        content: 'Connected to log stream',
        level: 'info'
      });
    } else if (wsStatus === 'error') {
      addLog({
        timestamp: new Date().toISOString(),
        type: 'status',
        agent: 'system',
        content: 'Connection error. Click "Retry Connection" to reconnect.',
        level: 'error'
      });
    }
  }, [wsStatus, addLog]);

  const handleClear = () => {
    setLogs([]);
  };

  const handleReconnect = () => {
    logsWebSocket.connect();
  };

  const filteredLogs = selectedAgent === 'all'
    ? logs
    : logs.filter(log => log.agent === selectedAgent);

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white">Agent Logs</h2>
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
          <select
            value={selectedAgent}
            onChange={(e) => setSelectedAgent(e.target.value)}
            className="bg-slate-800 text-slate-300 rounded px-2 py-1 text-sm"
          >
            <option value="all">All Agents</option>
            {agents.map(agent => (
              <option key={agent} value={agent}>{agent}</option>
            ))}
          </select>
          <button
            onClick={handleClear}
            className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
          >
            Clear
          </button>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">
            {filteredLogs.length} logs {logs.length === MAX_LOGS && '(max reached)'}
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
        className="flex-1 overflow-auto bg-slate-900/50 border border-slate-800 rounded-lg p-2 min-h-[600px] max-h-[1000px]"
      >
        <div className="font-mono text-xs leading-4">
          {filteredLogs.map((log, index) => (
            <div key={index} className="flex items-start hover:bg-slate-800/30">
              <span className="text-slate-500 shrink-0 w-20 pl-1">
                {new Date(log.timestamp).toLocaleTimeString().split(':').slice(0, 2).join(':')}
              </span>
              <span className="text-slate-400 shrink-0 w-24 px-1">[{log.agent || 'sys'}]</span>
              <span className={`${
                log.level === 'error' ? 'text-red-300' :
                log.level === 'warning' ? 'text-yellow-300' :
                'text-slate-300'
              } break-all`}>
                {log.content.length > 255 ? `${log.content.slice(0, 255)}...` : log.content}
                {log.details && (
                  <span className="text-slate-500 ml-1">({log.details})</span>
                )}
              </span>
            </div>
          ))}
          <div ref={autoScrollAnchorRef} />
        </div>
      </div>
    </div>
  );
} 