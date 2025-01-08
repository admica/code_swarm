// Base message interface
export interface BaseMessage {
  type: string;
  timestamp: string;
  agent: string;
}

// Agent connection message
export interface AgentConnectMessage extends BaseMessage {
  type: 'agent_connect';
  data: {
    name: string;
    status: {
      running: boolean;
      current_task: string | null;
      last_activity: string;
      monitor_path: string | null;
      health: {
        status: 'healthy' | 'stopped';
        last_activity_age: number;
        websocket_connected: boolean;
      }
    }
  }
}

// Agent status update message
export interface AgentStatusMessage extends BaseMessage {
  type: 'agent_status';
  data: {
    name: string;
    running: boolean;
    current_task: string | null;
    last_activity: string;
    monitor_path: string | null;
    health: {
      status: 'healthy' | 'stopped';
      last_activity_age: number;
      websocket_connected: boolean;
    }
  }
}

// Agent activity message (for high-visibility actions)
export interface AgentActivityMessage extends BaseMessage {
  type: 'agent_activity';
  category: 'activity';
  data: {
    action: string;
    file_path: string;
    details?: any;
  }
}

// System message
export interface SystemMessage extends Omit<BaseMessage, 'agent'> {
  type: 'system';
  message: string;
  agent?: string;  // Optional for system messages
}

// Log message
export interface LogMessage extends BaseMessage {
  type: 'log';
  level: 'info' | 'warning' | 'error' | 'debug';
  category: string;
  message: string;
  data?: any;
}

// AI Analysis message
export interface AIAnalysisMessage extends BaseMessage {
  type: 'ai_analysis';
  data: {
    file_path: string;
    analysis: string;
    metrics?: any;
  }
}

// Union type of all possible messages
export type AgentMessage = 
  | AgentConnectMessage 
  | AgentStatusMessage 
  | AgentActivityMessage 
  | SystemMessage 
  | LogMessage 
  | AIAnalysisMessage; 