import { AgentState } from '@/types/agents';
import { AgentCard } from '@/components/agents/AgentCard';
import { MonitorPathSelector } from '@/components/MonitorPathSelector';
import { LogWindow } from '@/components/LogWindow';
import { ConnectionStatus } from '@/lib/websocket';

interface DashboardProps {
  agents: Record<string, AgentState>;
  monitorPath: string;
  wsStatus: ConnectionStatus;
  onAgentStatusChange: (agent: AgentState) => void;
  onPathChange: (path: string) => void;
}

export function Dashboard({
  agents,
  monitorPath,
  wsStatus,
  onAgentStatusChange,
  onPathChange
}: DashboardProps) {
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Code Swarm</h1>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-sm text-slate-400">
              WebSocket:
            </span>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
              wsStatus === 'connected' ? 'bg-green-900/50 text-green-300' :
              wsStatus === 'connecting' ? 'bg-yellow-900/50 text-yellow-300' :
              wsStatus === 'disconnected' ? 'bg-slate-700 text-slate-300' :
              'bg-red-900/50 text-red-300'
            }`}>
              {wsStatus}
            </span>
          </div>
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
            agent={agent}
            onStatusChange={onAgentStatusChange}
          />
        ))}
      </div>

      <LogWindow
        agents={Object.keys(agents)}
      />
    </div>
  );
} 