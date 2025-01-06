import { AgentState, AgentType } from '@/types/agents';
import { agentsApi } from '@/lib/api';
import { useState, useEffect } from 'react';

const agentInfo: Record<string, { title: string; description: string }> = {
  changelog: {
    title: 'Changelog Agent',
    description: 'Monitors file changes and generates detailed changelogs with AI analysis'
  },
  readme: {
    title: 'README Agent',
    description: 'Automatically generates and maintains README files for Python modules'
  },
  deps: {
    title: 'Dependency Agent',
    description: 'Creates visual dependency graphs of your Python project structure'
  }
};

interface AgentCardProps {
  agent: AgentState;
  onStatusChange?: (agent: AgentState) => void;
}

export function AgentCard({ agent, onStatusChange }: AgentCardProps) {
  const [isLoading, setIsLoading] = useState(false);
  const info = agentInfo[agent.name];

  const handleControl = async (action: 'start' | 'stop') => {
    try {
      setIsLoading(true);
      console.log(`${action}ing agent ${agent.name}...`);
      const response = await agentsApi.controlAgent(agent.name, action);
      console.log('Agent control response:', response);
      
      // Update local state with the response
      if (response) {
        onStatusChange?.(response);
      }
    } catch (error) {
      console.error('Error controlling agent:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Debug log when agent status changes
  useEffect(() => {
    console.log(`Agent ${agent.name} status:`, {
      running: agent.running,
      pid: agent.pid,
      error: agent.last_error
    });
  }, [agent]);

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-800/50 shadow-lg">
      <div className="p-6">
        <div className="flex items-center justify-between">
          <h3 className="text-2xl font-semibold leading-none tracking-tight text-white">
            {info.title}
          </h3>
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium
            ${agent.running ? 'bg-green-900/50 text-green-300' :
              agent.last_error ? 'bg-red-900/50 text-red-300' :
                'bg-slate-700 text-slate-300'}`}>
            {agent.running ? 'running' : agent.last_error ? 'error' : 'idle'}
          </span>
        </div>
        
        <p className="text-sm text-slate-300 mt-2">
          {info.description}
        </p>

        {agent.monitor_path && (
          <div className="mt-4 text-sm text-slate-400">
            <span className="font-medium text-slate-300">Monitoring:</span> {agent.monitor_path}
          </div>
        )}

        {agent.last_error && (
          <div className="mt-4 text-sm text-red-300">
            <span className="font-medium">Error:</span> {agent.last_error}
          </div>
        )}

        {agent.pid && (
          <div className="mt-4 text-sm text-slate-400">
            <span className="font-medium text-slate-300">PID:</span> {agent.pid}
          </div>
        )}

        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={() => handleControl(agent.running ? 'stop' : 'start')}
            disabled={isLoading}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors
              ${agent.running
                ? 'bg-red-900/50 text-red-300 hover:bg-red-900'
                : 'bg-green-900/50 text-green-300 hover:bg-green-900'
              } disabled:opacity-50`}
          >
            {isLoading ? 'Loading...' : agent.running ? 'Stop' : 'Start'}
          </button>
        </div>
      </div>
    </div>
  );
} 