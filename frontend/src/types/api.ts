// src/types/api.ts
export interface AgentStatus {
  name: string;
  pid: number | null;
  running: boolean;
  monitor_path: string | null;
  last_error: string | null;
  last_update?: string;
  cpu_usage?: number;
  memory_usage?: number;
}

export interface AgentLogs {
  timestamp: string;
  level: 'INFO' | 'WARNING' | 'ERROR';
  message: string;
}

export interface AgentControls {
  onStart: (path: string) => Promise<void>;
  onStop: () => Promise<void>;
  onRestart: () => Promise<void>;
}

export interface AgentMetrics {
  filesWatched?: number;
  lastChangeDetected?: string;
  eventsProcessed?: number;
}
