import { AgentState } from '@/types/agents';
import { AgentCard } from '@/components/agents/AgentCard';
import { MonitorPathSelector } from '@/components/MonitorPathSelector';
import { ControllerOutput } from '@/components/ControllerOutput';
import { SwarmActivity } from '@/components/SwarmActivity';
import { DetailedLogs } from '@/components/DetailedLogs';
import { ConnectionStatus } from '@/lib/websocket';
import { useState } from 'react';

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
  const [showActivity, setShowActivity] = useState(true);
  const [showLogs, setShowLogs] = useState(true);

  return (
    <div className="p-6 space-y-6">
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Activity Pane */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">Activity</h2>
            <button
              onClick={() => setShowActivity(!showActivity)}
              className="px-3 py-1 rounded text-sm font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
            >
              {showActivity ? 'Hide' : 'Show'}
            </button>
          </div>
          {showActivity && (
            <>
              <ControllerOutput className="mb-4" />
              <SwarmActivity />
            </>
          )}
        </div>

        {/* Logs Pane */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold text-white">Logs</h2>
            <button
              onClick={() => setShowLogs(!showLogs)}
              className="px-3 py-1 rounded text-sm font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
            >
              {showLogs ? 'Hide' : 'Show'}
            </button>
          </div>
          {showLogs && (
            <DetailedLogs agents={Object.keys(agents)} />
          )}
        </div>
      </div>
    </div>
  );
} 