'use client';

import { useEffect, useState } from 'react';
import { AgentState } from '../types/agents';
import { Dashboard } from '../components/Dashboard';
import { LLMMonitoring } from '../components/LLMMonitoring';
import { Settings } from '../components/Settings';
import { TabNavigation } from '../components/TabNavigation';
import { agentsApi } from '../lib/api';

export default function Home() {
  const [agents, setAgents] = useState<Record<string, AgentState>>({});
  const [monitorPath, setMonitorPath] = useState<string>('');
  const [activeTab, setActiveTab] = useState('dashboard');

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [configData, agentsData] = await Promise.all([
          agentsApi.getConfig(),
          agentsApi.getAgents()
        ]);

        setMonitorPath(configData.monitor_path || '');
        setAgents(agentsData);
      } catch (error) {
        console.error('Error fetching initial data:', error);
      }
    };

    fetchData();
  }, []);

  // Handle agent status changes
  const handleAgentStatusChange = async (agent: AgentState) => {
    try {
      await agentsApi.controlAgent(agent.name, agent.running ? 'start' : 'stop');
      setAgents(prev => ({
        ...prev,
        [agent.name]: agent
      }));
    } catch (error) {
      console.error('Error controlling agent:', error);
    }
  };

  // Handle monitor path changes
  const handlePathChange = async (path: string) => {
    try {
      await agentsApi.setMonitorPath(path);
      setMonitorPath(path);
    } catch (error) {
      console.error('Error setting monitor path:', error);
    }
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return (
          <Dashboard
            agents={agents}
            monitorPath={monitorPath}
            onAgentStatusChange={handleAgentStatusChange}
            onPathChange={handlePathChange}
          />
        );
      case 'llm':
        return <LLMMonitoring />;
      case 'settings':
        return <Settings />;
      default:
        return null;
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <TabNavigation activeTab={activeTab} onTabChange={setActiveTab} />
      {renderContent()}
    </main>
  );
}
