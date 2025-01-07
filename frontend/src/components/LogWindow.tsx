import { useEffect, useState, useRef } from 'react';
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
  const logContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const pollInterval = setInterval(async () => {
      try {
        // Poll agent logs
        for (const agent of agents) {
          const agentLogs = await agentsApi.getAgentLogs(agent);
          agentLogs.forEach(log => {
            const parsedLog = parseBackendLog(log);
            if (parsedLog) {
              setLogs(prev => [...prev, parsedLog]);
            }
          });
        }
      } catch (error) {
        console.error('Error polling logs:', error);
      }
    }, 5000);

    return () => clearInterval(pollInterval);
  }, [agents]);

  useEffect(() => {
    if (autoScroll && logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  // Convert backend log message to ActivityMessage
  const parseBackendLog = (log: string): ActivityMessage | null => {
    try {
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
        };
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
            {filteredLogs.length} logs
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
        className="flex-1 overflow-auto bg-slate-900 rounded p-4"
      >
        {filteredLogs.map((log, index) => (
          <div key={index} className="mb-2">
            <span className="text-xs text-slate-500">
              {new Date(log.timestamp).toLocaleTimeString()}
            </span>
            <span className="ml-2 text-sm">
              <span className="text-slate-400">[{log.agent || 'unknown'}]</span>
              <span className={`ml-2 ${
                log.level === 'error' ? 'text-red-300' :
                log.level === 'warning' ? 'text-yellow-300' :
                'text-slate-300'
              }`}>
                {log.content}
              </span>
              {log.details && (
                <span className="ml-2 text-slate-500">({log.details})</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
} 