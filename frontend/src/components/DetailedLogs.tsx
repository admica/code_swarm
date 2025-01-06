import { useEffect, useRef, useState } from 'react';
import { agentsApi } from '../lib/api';

interface DetailedLogsProps {
  className?: string;
  agents: string[];
}

interface LogMessage {
  timestamp: string;
  agent: string;
  content: string;
  level: 'info' | 'warning' | 'error';
}

export function DetailedLogs({ className = '', agents }: DetailedLogsProps) {
  const [logs, setLogs] = useState<LogMessage[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string | 'all'>('all');
  const containerRef = useRef<HTMLDivElement>(null);

  // Convert backend log message to LogMessage
  const parseBackendLog = (log: string): LogMessage => {
    const timestamp = log.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0] || '';
    const isError = log.includes(' ERROR ');
    const isWarning = log.includes(' WARNING ');
    
    // Parse agent logs
    const agentMatch = log.match(/agent_code_mon_(\w+)\.py/);
    const agent = agentMatch ? agentMatch[1] : '';
    const message = log.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - /, '');
    
    return {
      timestamp,
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
          const logs = await agentsApi.getAgentLogs(agent, 100);
          allLogs.push(...logs);
        }
        
        if (!isMounted) return;

        // Convert log strings to LogMessage format
        const logMessages: LogMessage[] = allLogs.map(parseBackendLog);

        // Filter logs if an agent is selected
        const filteredLogs = selectedAgent === 'all' 
          ? logMessages
          : logMessages.filter(log => log.agent === selectedAgent);

        setLogs(filteredLogs);

        // Auto-scroll to bottom if enabled
        if (autoScroll && containerRef.current) {
          containerRef.current.scrollTop = containerRef.current.scrollHeight;
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

  const getMessageColor = (level: 'info' | 'warning' | 'error') => {
    switch (level) {
      case 'error': return 'text-red-300';
      case 'warning': return 'text-yellow-300';
      default: return 'text-slate-300';
    }
  };

  return (
    <div className={`flex flex-col h-64 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white">Detailed Logs</h2>
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
            Clear
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
        ref={containerRef}
        className="flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-900/50 font-mono text-sm"
      >
        <div className="p-4 space-y-1">
          {logs.map((log, index) => (
            <pre
              key={index}
              className={`whitespace-pre-wrap break-all font-mono text-xs ${getMessageColor(log.level)}`}
            >
              <span className="text-slate-500">{log.timestamp}</span>
              {' '}
              <span className="font-semibold">[{log.agent}]</span>
              {' '}
              {log.content}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
} 