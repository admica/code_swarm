import axios, { AxiosError } from 'axios';
import { AgentState, ChangelogEntry, ReadmeUpdate, DependencyGraph } from '@/types/agents';

interface ApiErrorResponse {
  message: string;
  [key: string]: any;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode?: number,
    public originalError?: Error
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 10000, // 10 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

async function handleApiError(error: unknown): Promise<never> {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;
    throw new ApiError(
      axiosError.response?.data?.message || axiosError.message,
      axiosError.response?.status,
      error
    );
  }
  throw new ApiError('An unexpected error occurred', undefined, error as Error);
}

export const agentsApi = {
  // Get status of all agents
  getAgents: async (): Promise<AgentState[]> => {
    try {
      const response = await api.get('/agents');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  },

  // Get recent changelog entries
  getChangelogs: async (limit: number = 10): Promise<ChangelogEntry[]> => {
    try {
      const response = await api.get(`/changelogs?limit=${limit}`);
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  },

  // Get recent README updates
  getReadmes: async (limit: number = 10): Promise<ReadmeUpdate[]> => {
    try {
      const response = await api.get(`/readmes?limit=${limit}`);
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  },

  // Get latest dependency graph
  getDependencyGraph: async (): Promise<DependencyGraph> => {
    try {
      const response = await api.get('/dependency-graph');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  },

  // Start/stop agents
  controlAgent: async (agentId: string, action: 'start' | 'stop', path?: string) => {
    try {
      const params = new URLSearchParams();
      if (path && action === 'start') {
        params.append('path', path);
      }
      const response = await api.post(
        `/agents/${agentId}/${action}${params.toString() ? `?${params.toString()}` : ''}`
      );
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  },

  // Set global monitor path
  setMonitorPath: async (path: string) => {
    try {
      const response = await api.post('/config/monitor-path', null, {
        params: { path }
      });
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  },

  // Get initial configuration
  getConfig: async () => {
    try {
      const response = await api.get('/info');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  },

  // Get agent logs
  getAgentLogs: async (agentName: string, lines: number = 100) => {
    try {
      const response = await api.get(`/agents/${agentName}/logs?lines=${lines}`);
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }
}; 