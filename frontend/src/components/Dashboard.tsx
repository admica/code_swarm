import { AgentState } from '@/types/agents';
import { AgentCard } from '@/components/agents/AgentCard';
import { MonitorPathSelector } from '@/components/MonitorPathSelector';
import { LogWindow } from '@/components/LogWindow';
import { AgentMessages } from '@/components/AgentMessages';
import { useState } from 'react';

interface DashboardProps {
  agents: Record<string, AgentState>;
  monitorPath: string;
  onAgentStatusChange: (agent: AgentState) => void;
  onPathChange: (path: string) => void;
}

export function Dashboard({
  agents,
  monitorPath,
  onAgentStatusChange,
  onPathChange
}: DashboardProps) {
  const [showLogs, setShowLogs] = useState(true);

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Code Swarm</h1>
        </div>
        <MonitorPathSelector
          currentPath={monitorPath}
          onPathChange={onPathChange}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {Object.entries(agents).map(([name, agent]) => (
          <AgentCard
            key={name}
            name={name}
            agent={agent}
            onControl={(action) => {
              const updatedAgent = {
                ...agent,
                running: action === 'start'
              };
              onAgentStatusChange(updatedAgent);
            }}
          />
        ))}
      </div>

      <div className="space-y-6">
        {showLogs && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <LogWindow agents={Object.keys(agents)} />
            <AgentMessages />
          </div>
        )}
      </div>
    </div>
  );
} 