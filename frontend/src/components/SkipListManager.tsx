import { useState, useEffect, useCallback } from 'react';
import { agentsApi } from '../lib/api';
import { useWebSocket } from '@/lib/websocket';

interface WebSocketMessage {
  type: string;
  data: any;
}

interface SkipListManagerProps {
  className?: string;
}

export function SkipListManager({ className = '' }: SkipListManagerProps) {
  const [skipList, setSkipList] = useState<string[]>([]);
  const [newEntry, setNewEntry] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'skip_list_update') {
      setSkipList(message.data);
    }
  }, []);

  useWebSocket({ onMessage: handleMessage });

  // Load initial skip list
  useEffect(() => {
    const loadSkipList = async () => {
      try {
        setIsLoading(true);
        const config = await agentsApi.getConfig();
        if (config.skip_list) {
          setSkipList(config.skip_list);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load skip list');
      } finally {
        setIsLoading(false);
      }
    };

    loadSkipList();
  }, []);

  const handleAdd = async () => {
    if (!newEntry.trim()) return;

    try {
      setIsLoading(true);
      const updatedList = [...skipList, newEntry.trim()];
      await agentsApi.updateSkipList(updatedList);
      setNewEntry('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update skip list');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRemove = async (entry: string) => {
    try {
      setIsLoading(true);
      const updatedList = skipList.filter(item => item !== entry);
      await agentsApi.updateSkipList(updatedList);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update skip list');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`rounded-lg border border-slate-800 bg-slate-800/50 p-6 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white">Skip List</h3>
        <div className="flex gap-2">
          <input
            type="text"
            value={newEntry}
            onChange={(e) => setNewEntry(e.target.value)}
            placeholder="e.g., node_modules/, venv/"
            className="px-3 py-1 rounded bg-slate-700 text-white placeholder:text-slate-400 text-sm"
          />
          <button
            onClick={handleAdd}
            disabled={isLoading || !newEntry.trim()}
            className="px-3 py-1 rounded bg-blue-900/50 text-blue-300 hover:bg-blue-900 transition-colors disabled:opacity-50 text-sm"
          >
            Add
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-2 rounded bg-red-900/50 text-red-300 text-sm">
          {error}
        </div>
      )}

      <div className="space-y-2">
        {skipList.map((entry) => (
          <div
            key={entry}
            className="flex items-center justify-between p-2 rounded bg-slate-700/50"
          >
            <code className="text-slate-300 text-sm">{entry}</code>
            <button
              onClick={() => handleRemove(entry)}
              disabled={isLoading}
              className="px-2 py-1 rounded bg-red-900/50 text-red-300 hover:bg-red-900 transition-colors disabled:opacity-50 text-sm"
            >
              Remove
            </button>
          </div>
        ))}
        {skipList.length === 0 && (
          <div className="text-slate-400 text-sm text-center py-4">
            No paths in skip list. Add paths to exclude them from monitoring.
          </div>
        )}
      </div>
    </div>
  );
} 