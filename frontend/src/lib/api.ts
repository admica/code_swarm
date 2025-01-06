import axios, { AxiosInstance, AxiosError } from 'axios';
import { AgentState, ChangelogEntry, ReadmeUpdate, DependencyGraph, ControllerInfo } from '../types/agents';

interface ApiErrorResponse {
  detail: string;
}

interface LLMMetrics {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate: number;
  average_processing_time: number;
  average_queue_time: number;
  requests_by_agent: Record<string, number>;
}

interface LLMStatus {
  available: boolean;
  model: string | null;
  error: string | null;
  models: string[] | null;
  response_time: number | null;
}

class ApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

function handleApiError(error: unknown): never {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;
    if (axiosError.response?.data?.detail) {
      throw new ApiError(axiosError.response.data.detail);
    }
    throw new ApiError(axiosError.message);
  }
  throw new ApiError('An unexpected error occurred');
}

class AgentsApi {
  private axiosInstance: AxiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: 'http://localhost:8000/api',
      timeout: 10000,
    });
  }

  async getConfig(): Promise<ControllerInfo> {
    try {
      const response = await this.axiosInstance.get('/info');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getAgents(): Promise<Record<string, AgentState>> {
    try {
      const response = await this.axiosInstance.get('/agents');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getChangelogs(limit: number = 10): Promise<ChangelogEntry[]> {
    try {
      const response = await this.axiosInstance.get(`/changelogs?limit=${limit}`);
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getReadmes(limit: number = 10): Promise<ReadmeUpdate[]> {
    try {
      const response = await this.axiosInstance.get(`/readmes?limit=${limit}`);
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getDependencyGraph(): Promise<DependencyGraph> {
    try {
      const response = await this.axiosInstance.get('/dependency-graph');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async controlAgent(agentName: string, action: 'start' | 'stop'): Promise<AgentState> {
    try {
      const response = await this.axiosInstance.post(`/agents/${agentName}/${action}`);
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async setMonitorPath(path: string) {
    try {
      const response = await this.axiosInstance.post('/config/monitor-path', null, {
        params: { path }
      });
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getAgentLogs(agentName: string, lines: number = 100): Promise<string[]> {
    try {
      const response = await this.axiosInstance.get(`/agents/${agentName}/logs`, {
        params: { lines },
        timeout: 30000,
        signal: AgentsApi.getAbortSignal('getAgentLogs'),
      });
      return response.data;
    } catch (error) {
      if (axios.isCancel(error)) {
        return [];
      }
      return handleApiError(error);
    }
  }

  async updateSkipList(skipList: string[]) {
    try {
      const response = await this.axiosInstance.post('/config/skip-list', { skip_list: skipList });
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getLLMMetrics(): Promise<LLMMetrics> {
    try {
      const response = await this.axiosInstance.get('/llm/metrics');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getLLMStatus(): Promise<LLMStatus> {
    try {
      const response = await this.axiosInstance.get('/llm/status');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async checkLLMHealth(): Promise<{ status: string; response_time: number }> {
    try {
      const response = await this.axiosInstance.get('/llm/health');
      return response.data;
    } catch (error) {
      return handleApiError(error);
    }
  }

  async getAIMarkers(): Promise<{ begin: string; end: string }> {
    const response = await this.axiosInstance.get('/config/ai-markers');
    return response.data;
  }

  async setAIMarkers(begin: string, end: string): Promise<{ success: boolean }> {
    const response = await this.axiosInstance.post('/config/ai-markers', null, {
      params: { begin, end }
    });
    return response.data;
  }

  private static abortControllers: Record<string, AbortController> = {};

  private static getAbortSignal(key: string): AbortSignal {
    if (this.abortControllers[key]) {
      this.abortControllers[key].abort();
    }
    this.abortControllers[key] = new AbortController();
    return this.abortControllers[key].signal;
  }
}

// Export a singleton instance
export const agentsApi = new AgentsApi();
// Export the class for testing purposes
export { AgentsApi };