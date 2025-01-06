import { useEffect, useState, useRef } from 'react';
import { agentsApi } from '@/lib/api';

interface LogWindowProps {
  agents: string[];
  className?: string;
}

export function LogWindow({ agents, className = '' }: LogWindowProps) {
  const [logs, setLogs] = useState<string[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState<string | 'all'>('all');
  const logContainerRef = useRef<HTMLDivElement>(null);

  // Fetch logs for all agents periodically
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        // Get more lines of logs to ensure we don't miss anything
        const allLogs = await Promise.all(
          agents.map(agent => agentsApi.getAgentLogs(agent, 1000))
        );
        
        // Combine and sort logs by timestamp (assuming format: "YYYY-MM-DD HH:mm:ss")
        const combinedLogs = allLogs
          .flat()
          .sort((a, b) => {
            const timeA = a.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0] || '';
            const timeB = b.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0] || '';
            return timeB.localeCompare(timeA);
          });

        // Filter logs if an agent is selected
        const filteredLogs = selectedAgent === 'all' 
          ? combinedLogs
          : combinedLogs.filter(log => log.includes(`${selectedAgent}.py`));

        setLogs(filteredLogs);

        // Auto-scroll to bottom if enabled
        if (autoScroll && logContainerRef.current) {
          logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight;
        }
      } catch (error) {
        console.error('Error fetching logs:', error);
      }
    };

    // Initial fetch
    fetchLogs();

    // Set up polling with shorter interval
    const interval = setInterval(fetchLogs, 1000);
    return () => clearInterval(interval);
  }, [agents, autoScroll, selectedAgent]);

  const handleClear = () => {
    setLogs([]);
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
          {logs.map((log, index) => {
            // Parse log level and agent from the message
            const isError = log.includes(' ERROR ');
            const isWarning = log.includes(' WARNING ');
            const isInfo = log.includes(' INFO ');
            
            // Extract agent name for highlighting
            const agentMatch = log.match(/agent_code_mon_(\w+)\.py/);
            const agentName = agentMatch ? agentMatch[1] : '';
            
            // Extract timestamp for better formatting
            const timestamp = log.match(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}/)?.[0];
            const message = log.replace(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - /, '');
            
            return (
              <pre
                key={index}
                className={`whitespace-pre-wrap break-all font-mono text-xs
                  ${isError ? 'text-red-300' :
                    isWarning ? 'text-yellow-300' :
                      isInfo ? 'text-green-300' :
                        'text-slate-300'}`}
              >
                {/* Timestamp */}
                <span className="text-slate-500">{timestamp}</span>
                {' '}
                {/* Agent name highlight */}
                {agentName && (
                  <span className={`font-semibold ${
                    isError ? 'text-red-200' :
                    isWarning ? 'text-yellow-200' :
                    isInfo ? 'text-green-200' :
                    'text-slate-200'
                  }`}>
                    [{agentName}]
                  </span>
                )}
                {' '}
                {/* Message content */}
                {message}
              </pre>
            );
          })}
        </div>
      </div>
    </div>
  );
} 