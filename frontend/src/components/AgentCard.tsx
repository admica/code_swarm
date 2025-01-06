// src/components/AgentCard.tsx
'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  Play, Stop, RefreshCw, RotateCcw, 
  Cpu, Memory, Calendar, Folder 
} from "lucide-react";
import type { AgentStatus, AgentLogs, AgentControls } from '@/types/api';
import { cn } from '@/lib/utils';

interface AgentCardProps {
  status: AgentStatus;
  logs: AgentLogs[];
  controls: AgentControls;
  className?: string;
}

export default function AgentCard({ status, logs, controls, className }: AgentCardProps) {
  const [path, setPath] = useState(status.monitor_path || "/your/project/path");
  const [isLoading, setIsLoading] = useState(false);

  const handleAction = async (action: () => Promise<void>) => {
    setIsLoading(true);
    try {
      await action();
    } catch (error) {
      console.error('Action failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getLogColor = (level: string) => {
    switch (level) {
      case 'ERROR': return 'text-red-400';
      case 'WARNING': return 'text-yellow-400';
      default: return 'text-gray-300';
    }
  };

  return (
    <Card className={cn("bg-gray-900 border-gray-800", className)}>
      <CardHeader className="flex flex-row items-center justify-between border-b border-gray-800">
        <CardTitle className="text-xl font-semibold text-gray-100 capitalize">
          {status.name} Agent
        </CardTitle>
        <Badge 
          variant="outline"
          className={cn(
            "px-4 py-1 text-sm font-medium",
            status.running 
              ? "bg-green-900/20 text-green-400 border-green-800"
              : "bg-red-900/20 text-red-400 border-red-800"
          )}
        >
          {status.running ? 'Running' : 'Stopped'}
        </Badge>
      </CardHeader>

      <CardContent className="space-y-4 pt-4">
        {/* Metrics Grid */}
        <div className="grid grid-cols-2 gap-4">
          <div className="flex items-center space-x-2 bg-gray-800/50 p-3 rounded-lg">
            <Cpu className="w-4 h-4 text-blue-400" />
            <div>
              <p className="text-xs text-gray-400">CPU Usage</p>
              <p className="text-sm font-medium text-gray-200">
                {status.cpu_usage?.toFixed(1) || 0}%
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2 bg-gray-800/50 p-3 rounded-lg">
            <Memory className="w-4 h-4 text-purple-400" />
            <div>
              <p className="text-xs text-gray-400">Memory</p>
              <p className="text-sm font-medium text-gray-200">
                {status.memory_usage?.toFixed(1) || 0} MB
              </p>
            </div>
          </div>
        </div>

        {/* Path Input */}
        <div className="space-y-2">
          <label className="text-xs text-gray-400">Monitor Path</label>
          <div className="flex space-x-2">
            <div className="relative flex-1">
              <Folder className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
              <input
                type="text"
                value={path}
                onChange={(e) => setPath(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-gray-800 border border-gray-700 rounded-md text-sm text-gray-200 
                         focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Project path"
              />
            </div>
            <Button
              variant="outline"
              size="icon"
              onClick={() => handleAction(() => controls.onRestart())}
              disabled={isLoading || !status.running}
              className="shrink-0 bg-gray-800 border-gray-700 hover:bg-gray-700"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Controls */}
        <div className="flex space-x-2">
          <Button
            variant={status.running ? "destructive" : "default"}
            onClick={() => handleAction(() => 
              status.running ? controls.onStop() : controls.onStart(path)
            )}
            disabled={isLoading}
            className="flex-1"
          >
            {isLoading ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : status.running ? (
              <><Stop className="w-4 h-4 mr-2" /> Stop</>
            ) : (
              <><Play className="w-4 h-4 mr-2" /> Start</>
            )}
          </Button>
        </div>

        {/* Error Alert */}
        {status.last_error && (
          <Alert variant="destructive" className="bg-red-900/20 border-red-800">
            <AlertDescription className="text-red-400">
              {status.last_error}
            </AlertDescription>
          </Alert>
        )}

        {/* Logs */}
        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h4 className="text-sm font-medium text-gray-200">Recent Logs</h4>
            <span className="text-xs text-gray-400">
              Last update: {new Date(status.last_update || '').toLocaleTimeString()}
            </span>
          </div>
          <ScrollArea className="h-48 rounded-md border border-gray-800 bg-gray-950 p-2">
            {logs.map((log, i) => (
              <div key={i} className="flex space-x-2 text-xs font-mono mb-1">
                <span className="text-gray-500">{log.timestamp}</span>
                <span className={getLogColor(log.level)}>[{log.level}]</span>
                <span className="text-gray-300">{log.message}</span>
              </div>
            ))}
          </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}
