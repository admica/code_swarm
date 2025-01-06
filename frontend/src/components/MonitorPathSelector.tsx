import { useState } from 'react';
import { agentsApi } from '@/lib/api';

interface MonitorPathSelectorProps {
  currentPath?: string;
  onPathChange: (path: string) => void;
}

export function MonitorPathSelector({ currentPath, onPathChange }: MonitorPathSelectorProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [path, setPath] = useState(currentPath || '');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async () => {
    try {
      setIsLoading(true);
      await agentsApi.setMonitorPath(path);
      onPathChange(path);
      setIsEditing(false);
    } catch (error) {
      console.error('Error setting monitor path:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isEditing) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <span className="text-slate-400">
          {currentPath ? (
            <>
              <span className="text-slate-300">Monitoring:</span> {currentPath}
            </>
          ) : (
            'No path set'
          )}
        </span>
        <button
          onClick={() => setIsEditing(true)}
          className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
        >
          Change
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <input
        type="text"
        value={path}
        onChange={(e) => setPath(e.target.value)}
        placeholder="/path/to/monitor"
        className="rounded-md bg-slate-900 border border-slate-700 px-3 py-1 text-sm text-slate-300 placeholder-slate-500"
      />
      <button
        onClick={handleSubmit}
        disabled={isLoading || !path}
        className="px-3 py-1 rounded-md text-sm font-medium bg-green-900/50 text-green-300 hover:bg-green-900 disabled:opacity-50"
      >
        Save
      </button>
      <button
        onClick={() => setIsEditing(false)}
        className="px-3 py-1 rounded-md text-sm font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
      >
        Cancel
      </button>
    </div>
  );
} 