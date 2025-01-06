'use client';

import { useEffect, useState } from 'react';
import { AgentState } from '@/types/agents';
import { agentsApi } from '@/lib/api';
import { useWebSocket } from '@/lib/websocket';
import { AgentCard } from '@/components/agents/AgentCard';
import { MonitorPathSelector } from '@/components/MonitorPathSelector';

export default function Home() {
  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [monitorPath, setMonitorPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial agents data
  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const data = await agentsApi.getAgents();
        const agentsMap = Object.fromEntries(
          Object.entries(data).map(([name, agent]) => [name, agent])
        );
        setAgents(agentsMap);
        // Set initial monitor path from any running agent
        const runningAgent = Object.values(agentsMap).find(agent => agent.monitor_path);
        if (runningAgent?.monitor_path) {
          setMonitorPath(runningAgent.monitor_path);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch agents');
      } finally {
        setIsLoading(false);
      }
    };
    fetchAgents();
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
    }
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
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold">Code Swarm</h1>
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
      </div>
    </main>
  );
}
