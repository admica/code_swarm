'use client';

import { useEffect, useState } from 'react';
import { AgentState } from '@/types/agents';
import { agentsApi } from '@/lib/api';
import { useWebSocket, ConnectionStatus } from '@/lib/websocket';
import { TabNavigation } from '@/components/TabNavigation';
import { Dashboard } from '@/components/Dashboard';
import { Settings } from '@/components/Settings';

export default function Home() {
  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [monitorPath, setMonitorPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<ConnectionStatus>('disconnected');
  const [activeTab, setActiveTab] = useState('dashboard');

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
      console.log('WebSocket message received:', data);
      if (data.type === 'agent_update') {
        console.log('Updating agent status:', data.data);
        setAgents(prev => {
          const newAgents = {
            ...prev,
            [data.data.name]: {
              ...prev[data.data.name],
              ...data.data
            }
          };
          console.log('New agents state:', newAgents);
          return newAgents;
        });
      }
    },
    onStatusChange: (status) => {
      console.log('WebSocket status changed:', status);
      setWsStatus(status);
    }
  });

  const handleAgentStatusChange = (updatedAgent: AgentState) => {
    console.log('Agent status change handler called:', updatedAgent);
    setAgents(prev => {
      const newAgents = {
        ...prev,
        [updatedAgent.name]: {
          ...prev[updatedAgent.name],
          ...updatedAgent
        }
      };
      console.log('New agents state after manual update:', newAgents);
      return newAgents;
    });
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

  if (error || wsStatus === 'error') {
    return (
      <div className="min-h-screen bg-slate-900 text-white p-8">
        <div className="max-w-6xl mx-auto">
          <div className="rounded-lg border border-red-900/50 bg-red-900/10 p-8 text-center">
            <h2 className="text-2xl font-bold text-red-300 mb-4">
              Connection Error
            </h2>
            <p className="text-red-200 mb-6">
              {error || "Unable to connect to the backend server. Please ensure:"}
            </p>
            <ul className="text-red-200 text-left max-w-md mx-auto space-y-2 mb-8">
              <li>1. The backend server is running (<code className="bg-red-900/50 px-2 py-0.5 rounded">python agent_swarm_controller.py</code>)</li>
              <li>2. The server is accessible at <code className="bg-red-900/50 px-2 py-0.5 rounded">http://localhost:8000</code></li>
              <li>3. There are no firewall restrictions blocking the connection</li>
            </ul>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded bg-red-900/50 text-red-200 hover:bg-red-900 transition-colors"
            >
              Retry Connection
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-slate-900 text-white p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <TabNavigation
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />

        {activeTab === 'dashboard' ? (
          <Dashboard
            agents={agents}
            monitorPath={monitorPath}
            wsStatus={wsStatus}
            onAgentStatusChange={handleAgentStatusChange}
            onPathChange={handlePathChange}
          />
        ) : (
          <Settings />
        )}
      </div>
    </main>
  );
}
