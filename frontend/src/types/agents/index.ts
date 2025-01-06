export type AgentStatus = 'idle' | 'running' | 'error';

export type AgentType = 'changelog' | 'readme' | 'deps';

export interface AgentState {
  name: string;
  pid: number | null;
  running: boolean;
  monitor_path: string | null;
  last_error: string | null;
}

export interface ControllerInfo {
  monitor_path: string | null;
  skip_list: string[];
  ollama_available: boolean;
  ollama_model: string | null;
}

export interface ChangelogEntry {
  timestamp: string;
  file: string;
  summary: string;
  scores: {
    syntax?: number;
    style?: number;
    complexity?: number;
    standards?: number;
  };
  aiAnalysis?: string;
}

export interface ReadmeUpdate {
  timestamp: string;
  file: string;
  content: string;
  aiSummary?: string;
}

export interface DependencyGraph {
  timestamp: string;
  mermaidDefinition: string;
  aiInsights?: string;
} 