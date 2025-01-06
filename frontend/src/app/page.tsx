'use client';

import { useEffect, useState } from 'react';
import { AgentState } from '../types/agents';
import { AgentCard } from '../components/agents/AgentCard';
import { MonitorPathSelector } from '../components/MonitorPathSelector';
import { LogWindow } from '../components/LogWindow';
import { agentsApi } from '../lib/api';
import { TabNavigation } from '../components/TabNavigation';
import { SkipListManager } from '../components/SkipListManager';
import { LLMMonitoring } from '../components/LLMMonitoring';

export default function Home() {
  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [monitorPath, setMonitorPath] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('dashboard');

  // Load initial configuration and agents
  useEffect(() => {
    const initialize = async () => {
      try {
        setIsLoading(true);
        
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

  // Handle monitor path changes
  const handleMonitorPathChange = async (path: string) => {
    try {
      await agentsApi.setMonitorPath(path);
      setMonitorPath(path);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to set monitor path');
    }
  };

  // Handle agent control
  const handleAgentControl = async (agentName: string, action: 'start' | 'stop') => {
    try {
      const updatedAgent = await agentsApi.controlAgent(agentName, action);
      setAgents(prev => ({
        ...prev,
        [agentName]: updatedAgent
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} agent`);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-900 text-slate-300">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-900 text-red-300">
        Error: {error}
      </div>
    );
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return (
          <>
            <div className="mb-8">
              <MonitorPathSelector
                currentPath={monitorPath}
                onPathChange={handleMonitorPathChange}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
              {Object.entries(agents).map(([name, agent]) => (
                <AgentCard
                  key={name}
                  name={name}
                  agent={agent}
                  onControl={(action) => handleAgentControl(name, action)}
                />
              ))}
            </div>

            <div className="mt-8">
              <LogWindow agents={Object.keys(agents)} />
            </div>
          </>
        );
      case 'llm':
        return <LLMMonitoring />;
      case 'settings':
        return <SkipListManager />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-300 p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        <TabNavigation
          activeTab={activeTab}
          onTabChange={setActiveTab}
        />
        <div className="mt-8">
          {renderContent()}
        </div>
      </div>
    </div>
  );
}
