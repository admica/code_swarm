'use client';

import { useState } from 'react';
import useSWR from 'swr';
import axios from 'axios';
import { Button } from "@/components/ui/button";
import AgentCard from '@/components/AgentCard';
import type { AgentStatus, AgentLogs } from '@/types/api';
import { RefreshCw, PlayCircle, StopCircle, Folder, ServerCrash } from 'lucide-react';
import { Alert, AlertDescription } from "@/components/ui/alert";

const API_BASE = 'http://localhost:8000';
const fetcher = (url: string) => axios.get(url).then(res => res.data);

export default function Dashboard() {
  const [projectPath, setProjectPath] = useState("/your/project/path");
  const [isLoading, setIsLoading] = useState(false);
  
  // Fetch agent statuses
  const { data: statuses, error: statusError, mutate: mutateStatuses } = useSWR<
    Record<string, AgentStatus>
  >(`${API_BASE}/agents`, fetcher, {
    refreshInterval: 5000
  });

  // Fetch logs for each agent
  const { data: logsData } = useSWR<Record<string, AgentLogs[]>>(
    statuses ? 
      Object.keys(statuses).map(name => `${API_BASE}/agents/${name}/logs`) : 
      null,
    async (urls: string[]) => {
      const results = await Promise.all(
        urls.map(url => fetcher(url))
      );
      return Object.fromEntries(
        urls.map((url, i) => [url.split('/')[5], results[i]])
      );
    },
    { refreshInterval: 5000 }
  );

  // Actions
  const handleAction = async (action: () => Promise<void>) => {
    setIsLoading(true);
    try {
      await action();
      await mutateStatuses();
    } catch (error) {
      console.error('Action failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getAgentControls = (name: string) => ({
    onStart: async (path: string) => {
      await axios.post(`${API_BASE}/agents/${name}/start?path=${encodeURIComponent(path)}`);
      await mutateStatuses();
    },
    onStop: async () => {
      await axios.post(`${API_BASE}/agents/${name}/stop`);
      await mutateStatuses();
    },
    onRestart: async () => {
      const agent = statuses?.[name];
      if (agent?.monitor_path) {
        await axios.post(`${API_BASE}/agents/${name}/stop`);
        await axios.post(`${API_BASE}/agents/${name}/start?path=${encodeURIComponent(agent.monitor_path)}`);
        await mutateStatuses();
      }
    }
  });

  const startAll = () => handleAction(async () => {
    await axios.post(`${API_BASE}/agents/start-all?path=${encodeURIComponent(projectPath)}`);
  });

  const stopAll = () => handleAction(async () => {
    await axios.post(`${API_BASE}/agents/stop-all`);
  });

  const isAllRunning = statuses && Object.values(statuses).every(s => s.running);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="container mx-auto p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col space-y-4 md:flex-row md:justify-between md:items-center">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              Code Swarm Dashboard
            </h1>
            <p className="text-gray-400 mt-1">Monitor and control your code swarm agents</p>
          </div>
          
          <div className="flex flex-col space-y-2 md:flex-row md:space-y-0 md:space-x-4">
            <div className="relative">
              <Folder className="absolute left-3 top-2.5 h-5 w-5 text-gray-400" />
              <input
                type="text"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                className="pl-10 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-200 
                         focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent w-full md:w-80"
                placeholder="Project path"
              />
            </div>
            
            <div className="flex space-x-2">
              <Button
                variant="outline"
                onClick={() => mutateStatuses()}
                className="bg-gray-800 border-gray-700 hover:bg-gray-700"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
              <Button
                variant={isAllRunning ? "destructive" : "default"}
                onClick={isAllRunning ? stopAll : startAll}
                disabled={isLoading}
                className="flex-1 md:flex-none"
              >
                {isLoading ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : isAllRunning ? (
                  <><StopCircle className="w-4 h-4 mr-2" /> Stop All</>
                ) : (
                  <><PlayCircle className="w-4 h-4 mr-2" /> Start All</>
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Error State */}
        {statusError && (
          <Alert variant="destructive" className="bg-red-900/20 border-red-800">
            <ServerCrash className="h-4 w-4" />
            <AlertDescription className="text-red-400">
              Error connecting to swarm controller
            </AlertDescription>
          </Alert>
        )}

        {/* Agent Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {statuses && Object.entries(statuses).map(([name, status]) => (
            <AgentCard
              key={name}
              status={status}
              logs={logsData?.[name] || []}
              controls={getAgentControls(name)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
