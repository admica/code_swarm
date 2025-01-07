export interface LLMStatus {
  available: boolean;
  model: string | null;
  error: string | null;
  models: string[] | null;
  response_time: number | null;
}

export interface LLMMetrics {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate: number;
  average_processing_time: number;
  average_queue_time: number;
  requests_by_agent: Record<string, number>;
}

export interface LLMRequest {
  prompt: string;
  model: string;
  agent: string;
  max_tokens?: number;
  temperature?: number;
}

export interface LLMResponse {
  response?: string;
  error?: string;
  processing_time: number;
  queue_time: number;
  timestamp: string;
} 