'use client';

import { useEffect, useState } from 'react';
import { AgentState } from '@/types/agents';
import { agentsApi } from '@/lib/api';
import { useWebSocket, ConnectionStatus } from '@/lib/websocket';
import { AgentCard } from '@/components/agents/AgentCard';
import { MonitorPathSelector } from '@/components/MonitorPathSelector';
import { LogWindow } from '@/components/LogWindow';

export default function Home() {
  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [monitorPath, setMonitorPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<ConnectionStatus>('disconnected');

  // Load initial configuration and agents
  useEffect(() => {
    const initialize = async () => {
      try {
        // Get initial configuration
        const config = await agentsApi.getConfig();
        if (config.monitor_path) {
          setMonitorPath(config.monitor_path);
        }

        // Get agent statuses
        const data = await agentsApi.getAgents();
        const agentsMap = Object.fromEntries(
          Object.entries(data).map(([name, agent]) => [name, agent])
        );
        setAgents(agentsMap);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to initialize');
      } finally {
        setIsLoading(false);
      }
    };

    initialize();
  }, []);

  // Handle WebSocket messages
  useWebSocket({
    onMessage: (data) => {
      if (data.type === 'agent_update') {
        setAgents(prev => ({
          ...prev,
          [data.data.name]: data.data
        }));
      }
    },
    onStatusChange: setWsStatus
  });

  const handleAgentStatusChange = (updatedAgent: AgentState) => {
    setAgents(prev => ({
      ...prev,
      [updatedAgent.name]: updatedAgent
    }));
  };

  const handlePathChange = (newPath: string) => {
    setMonitorPath(newPath);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-slate-300">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-red-300">Error: {error}</div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-900 text-white p-8">
      <div className="max-w-6xl mx-auto space-y-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Code Swarm</h1>
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-slate-400">
                WebSocket:
              </span>
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                ${wsStatus === 'connected' ? 'bg-green-900/50 text-green-300' :
                  wsStatus === 'connecting' ? 'bg-yellow-900/50 text-yellow-300' :
                    wsStatus === 'error' ? 'bg-red-900/50 text-red-300' :
                      'bg-slate-700 text-slate-300'}`}>
                {wsStatus}
              </span>
            </div>
          </div>
          <MonitorPathSelector
            currentPath={monitorPath}
            onPathChange={handlePathChange}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Object.entries(agents).map(([name, agent]) => (
            <AgentCard
              key={name}
              agent={agent}
              onStatusChange={handleAgentStatusChange}
            />
          ))}
        </div>

        <LogWindow
          agents={Object.keys(agents)}
          className="mt-8"
        />
      </div>
    </main>
  );
}
