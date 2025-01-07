import { useEffect, useState, useRef, useCallback } from 'react';
import { agentsApi } from '../lib/api';
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
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [connectionAttempts, setConnectionAttempts] = useState(0);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);
  const autoScrollAnchorRef = useRef<HTMLDivElement>(null);

  const MAX_LOGS = 1000; // Maximum number of logs to keep in memory
  const MAX_RETRY_ATTEMPTS = 5;
  const RETRY_DELAY = 2000; // 2 seconds initial delay
  const MAX_RETRY_DELAY = 30000; // 30 seconds max delay
  const RETRY_BACKOFF = 1.5; // Exponential backoff multiplier

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

  const connectWebSocket = useCallback(() => {
    try {
      // Clear any existing connection and timeout
      if (wsRef.current) {
        wsRef.current.close(1000, 'Normal closure');  // Use normal closure code
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = undefined;
      }

      setWsStatus('connecting');

      const ws = new WebSocket('ws://localhost:8000/ws/logs');
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus('connected');
        setConnectionAttempts(0); // Reset attempts on successful connection
        addLog({
          timestamp: new Date().toISOString(),
          type: 'status',
          agent: 'system',
          content: 'Connected to log stream',
          level: 'info'
        });
      };

      ws.onmessage = (event) => {
        const log = parseBackendLog(event.data);
        if (log) {
          addLog(log);
        }
      };

      ws.onclose = (event) => {
        // Clear existing connection
        wsRef.current = null;
        
        // Don't increment attempts if it was a normal closure
        const wasNormalClosure = event.code === 1000 || event.code === 1001;
        
        if (wasNormalClosure) {
          setWsStatus('disconnected');
          return;  // Don't attempt to reconnect on normal closure
        }

        // Only log abnormal closures
        addLog({
          timestamp: new Date().toISOString(),
          type: 'status',
          agent: 'system',
          content: `Disconnected from log stream (code: ${event.code})${event.reason ? ': ' + event.reason : ''}`,
          level: 'warning'
        });

        setWsStatus('disconnected');

        // Attempt to reconnect if not at max attempts
        if (connectionAttempts < MAX_RETRY_ATTEMPTS) {
          const nextAttempt = connectionAttempts + 1;
          const currentDelay = Math.min(
            RETRY_DELAY * Math.pow(RETRY_BACKOFF, connectionAttempts),
            MAX_RETRY_DELAY
          );

          addLog({
            timestamp: new Date().toISOString(),
            type: 'status',
            agent: 'system',
            content: `Reconnecting in ${Math.round(currentDelay/1000)}s (attempt ${nextAttempt}/${MAX_RETRY_ATTEMPTS})`,
            level: 'info'
          });

          // Schedule reconnection
          reconnectTimeoutRef.current = setTimeout(() => {
            setConnectionAttempts(nextAttempt);
            connectWebSocket();
          }, currentDelay);
        } else {
          setWsStatus('error');
          addLog({
            timestamp: new Date().toISOString(),
            type: 'status',
            agent: 'system',
            content: 'Maximum reconnection attempts reached. Please refresh the page.',
            level: 'error'
          });
        }
      };

      ws.onerror = (error) => {
        // Don't log WebSocket errors as they're followed by onclose events
        // Just update the status
        setWsStatus('error');
      };
    } catch (error) {
      console.error('Error connecting to WebSocket:', error);
      setWsStatus('error');
      addLog({
        timestamp: new Date().toISOString(),
        type: 'status',
        agent: 'system',
        content: `Failed to connect: ${error instanceof Error ? error.message : 'Unknown error'}`,
        level: 'error'
      });
    }
  }, [connectionAttempts, addLog]);

  // Initial connection
  useEffect(() => {
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWebSocket]);

  // Manual reconnect handler
  const handleReconnect = useCallback(() => {
    setConnectionAttempts(0); // Reset attempts
    connectWebSocket();
  }, [connectWebSocket]);

  // Convert backend log message to ActivityMessage
  const parseBackendLog = (log: string): ActivityMessage | null => {
    try {
      const timestamp = log.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0] || new Date().toISOString();
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
      
      // Parse agent logs
      const agentMatch = log.match(/agent_code_mon_(\w+)/);
      const agent = agentMatch ? agentMatch[1] : '';
      const message = log.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - /, '');
      
      return {
        timestamp,
        type: 'log',
        agent,
        content: message,
        level: isError ? 'error' : isWarning ? 'warning' : 'info'
      };
    } catch (error) {
      console.error('Error parsing log:', error);
      return null;
    }
  };

  const handleClear = () => {
    setLogs([]);
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
        className="flex-1 overflow-auto bg-slate-900/50 border border-slate-800 rounded-lg p-2 min-h-[300px] max-h-[500px]"
      >
        <div className="font-mono text-xs leading-4">
          {filteredLogs.map((log, index) => (
            <div key={index} className="flex items-start hover:bg-slate-800/30">
              <span className="text-slate-500 shrink-0 w-14 pl-1">
                {new Date(log.timestamp).toLocaleTimeString().split(':').slice(0, 2).join(':')}
              </span>
              <span className="text-slate-400 shrink-0 w-16 px-1">[{log.agent || 'sys'}]</span>
              <span className={`${
                log.level === 'error' ? 'text-red-300' :
                log.level === 'warning' ? 'text-yellow-300' :
                'text-slate-300'
              } break-all`}>
                {log.content}
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