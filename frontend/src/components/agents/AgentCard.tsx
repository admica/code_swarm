import { AgentState } from '../../types/agents';

interface AgentCardProps {
  name: string;
  agent: AgentState;
  onControl: (action: 'start' | 'stop') => void;
}

export function AgentCard({ name, agent, onControl }: AgentCardProps) {
  const getTitle = () => {
    switch (name) {
      case 'agent_code_mon_changelog':
        return 'Changelog Agent';
      case 'agent_code_mon_readme':
        return 'README Agent';
      case 'agent_code_mon_deps':
        return 'Dependency Agent';
      default:
        return `${name} Agent`;
    }
  };

  const getDescription = () => {
    switch (name) {
      case 'agent_code_mon_changelog':
        return 'Monitors code changes and generates changelogs';
      case 'agent_code_mon_readme':
        return 'Keeps README files up to date';
      case 'agent_code_mon_deps':
        return 'Analyzes project dependencies';
      default:
        return 'Monitors and analyzes code';
    }
  };

  const getStatusColor = () => {
    if (agent.last_error) return 'bg-red-500';
    return agent.running ? 'bg-green-500' : 'bg-gray-500';
  };

  const handleControl = () => {
    onControl(agent.running ? 'stop' : 'start');
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-800/50 shadow-lg">
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">{getTitle()}</h3>
          <div className={`w-3 h-3 rounded-full ${getStatusColor()}`} />
        </div>
        <p className="text-slate-300 mb-4">{getDescription()}</p>
        <div className="flex items-center justify-between">
          <button
            onClick={handleControl}
            className={`px-4 py-2 rounded ${
              agent.running
                ? 'bg-red-900/50 text-red-300 hover:bg-red-900'
                : 'bg-green-900/50 text-green-300 hover:bg-green-900'
            }`}
          >
            {agent.running ? 'Stop' : 'Start'}
          </button>
          {agent.last_error && (
            <span className="text-red-300 text-sm">{agent.last_error}</span>
          )}
        </div>
      </div>
    </div>
  );
} 