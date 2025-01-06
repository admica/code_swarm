import { useEffect, useState } from 'react';
import { agentsApi } from '../lib/api';

export function LLMMonitoring() {
  const [metrics, setMetrics] = useState<{
    total_requests: number;
    successful_requests: number;
    failed_requests: number;
    success_rate: number;
    average_processing_time: number;
    average_queue_time: number;
    requests_by_agent: Record<string, number>;
  } | null>(null);
  const [status, setStatus] = useState<{
    available: boolean;
    model: string | null;
    error: string | null;
    models: string[] | null;
    response_time: number | null;
  } | null>(null);
  const [health, setHealth] = useState<{
    status: string;
    response_time: number;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [metricsData, statusData, healthData] = await Promise.all([
          agentsApi.getLLMMetrics(),
          agentsApi.getLLMStatus(),
          agentsApi.checkLLMHealth()
        ]);
        setMetrics(metricsData);
        setStatus(statusData);
        setHealth(healthData);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch LLM data');
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 5000); // Update every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const formatTime = (ms: number) => {
    return `${ms.toFixed(2)}ms`;
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  // Render a circular gauge
  const CircularGauge = ({ value, max, label }: { value: number; max: number; label: string }) => {
    const percentage = (value / max) * 100;
    const radius = 40;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percentage / 100) * circumference;

    return (
      <div className="flex flex-col items-center">
        <div className="relative w-32 h-32">
          <svg className="transform -rotate-90 w-32 h-32">
            <circle
              className="text-slate-700"
              strokeWidth="8"
              stroke="currentColor"
              fill="transparent"
              r={radius}
              cx="64"
              cy="64"
            />
            <circle
              className="text-green-500 transition-all duration-300"
              strokeWidth="8"
              strokeDasharray={circumference}
              strokeDashoffset={offset}
              strokeLinecap="round"
              stroke="currentColor"
              fill="transparent"
              r={radius}
              cx="64"
              cy="64"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-bold text-white">{formatPercentage(percentage)}</span>
          </div>
        </div>
        <span className="mt-2 text-sm text-slate-300">{label}</span>
      </div>
    );
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">LLM Monitoring</h1>
        <p className="mt-2 text-slate-400">
          Real-time metrics and status for the LLM service
        </p>
      </div>

      {error ? (
        <div className="rounded-lg bg-red-900/50 border border-red-700 p-4 text-red-300">
          {error}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Status Card */}
          <div className="rounded-lg border border-slate-800 bg-slate-800/50 p-6">
            <h2 className="text-xl font-semibold mb-4">Service Status</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="flex items-center space-x-3">
                <div className={`w-3 h-3 rounded-full ${status?.available ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-slate-300">
                  {status?.available ? 'Available' : 'Unavailable'}
                </span>
              </div>
              {status?.model && (
                <div className="text-slate-300">
                  <span className="text-slate-400">Model:</span> {status.model}
                </div>
              )}
              {health?.response_time && (
                <div className="text-slate-300">
                  <span className="text-slate-400">Response Time:</span> {formatTime(health.response_time)}
                </div>
              )}
            </div>
          </div>

          {/* Metrics Card */}
          {metrics && (
            <div className="rounded-lg border border-slate-800 bg-slate-800/50 p-6">
              <h2 className="text-xl font-semibold mb-6">Performance Metrics</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <CircularGauge
                  value={metrics.success_rate}
                  max={100}
                  label="Success Rate"
                />
                <div className="space-y-4">
                  <div>
                    <div className="text-sm text-slate-400 mb-1">Processing Time</div>
                    <div className="text-2xl font-bold text-white">
                      {formatTime(metrics.average_processing_time)}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-slate-400 mb-1">Queue Time</div>
                    <div className="text-2xl font-bold text-white">
                      {formatTime(metrics.average_queue_time)}
                    </div>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="text-sm text-slate-400 mb-1">Total Requests</div>
                    <div className="text-2xl font-bold text-white">
                      {metrics.total_requests}
                    </div>
                  </div>
                  <div className="flex space-x-4">
                    <div>
                      <div className="text-sm text-slate-400 mb-1">Successful</div>
                      <div className="text-xl font-bold text-green-500">
                        {metrics.successful_requests}
                      </div>
                    </div>
                    <div>
                      <div className="text-sm text-slate-400 mb-1">Failed</div>
                      <div className="text-xl font-bold text-red-500">
                        {metrics.failed_requests}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Agent Usage Card */}
          {metrics?.requests_by_agent && Object.keys(metrics.requests_by_agent).length > 0 && (
            <div className="rounded-lg border border-slate-800 bg-slate-800/50 p-6">
              <h2 className="text-xl font-semibold mb-4">Agent Usage</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(metrics.requests_by_agent).map(([agent, count]) => (
                  <div
                    key={agent}
                    className="flex items-center justify-between p-3 rounded bg-slate-700/50"
                  >
                    <span className="text-slate-300">{agent}</span>
                    <span className="text-slate-400">{count} requests</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Available Models */}
          {status?.models && status.models.length > 0 && (
            <div className="rounded-lg border border-slate-800 bg-slate-800/50 p-6">
              <h2 className="text-xl font-semibold mb-4">Available Models</h2>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                {status.models.map((model) => (
                  <div
                    key={model}
                    className="px-3 py-2 rounded bg-slate-700/50 text-slate-300 text-sm"
                  >
                    {model}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
} 