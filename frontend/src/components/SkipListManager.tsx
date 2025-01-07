import { useState, useEffect, useCallback } from 'react';
import { agentsApi } from '../lib/api';

interface SkipListManagerProps {
  className?: string;
}

export function SkipListManager({ className = '' }: SkipListManagerProps) {
  const [skipList, setSkipList] = useState<string[]>([]);
  const [newPattern, setNewPattern] = useState('');
  const [error, setError] = useState<string | null>(null);

  const loadSkipList = useCallback(async () => {
    try {
      const info = await agentsApi.getConfig();
      setSkipList(info.skip_list);
      setError(null);
    } catch (error) {
      console.error('Error loading skip list:', error);
      setError('Failed to load skip list');
    }
  }, []);

  useEffect(() => {
    loadSkipList();
    const interval = setInterval(loadSkipList, 5000);
    return () => clearInterval(interval);
  }, [loadSkipList]);

  const handleAdd = async () => {
    if (!newPattern.trim()) return;

    try {
      const pattern = newPattern.trim();
      const updatedList = [...skipList, pattern];
      await agentsApi.updateSkipList(updatedList);
      setSkipList(updatedList);
      setNewPattern('');
      setError(null);
    } catch (error) {
      console.error('Error adding pattern:', error);
      setError('Failed to add pattern');
    }
  };

  const handleRemove = async (pattern: string) => {
    try {
      const updatedList = skipList.filter(p => p !== pattern);
      await agentsApi.updateSkipList(updatedList);
      setSkipList(updatedList);
      setError(null);
    } catch (error) {
      console.error('Error removing pattern:', error);
      setError('Failed to remove pattern');
    }
  };

  return (
    <div className={`p-4 bg-slate-800 rounded-lg ${className}`}>
      <h2 className="text-lg font-semibold text-white mb-4">Skip List</h2>
      
      {error && (
        <div className="text-red-400 text-sm mb-4">
          {error}
        </div>
      )}
      
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={newPattern}
          onChange={(e) => setNewPattern(e.target.value)}
          placeholder="Add pattern (e.g., node_modules/)"
          className="flex-1 bg-slate-900 text-slate-300 rounded px-3 py-2 text-sm"
        />
        <button
          onClick={handleAdd}
          disabled={!newPattern.trim()}
          className="px-4 py-2 bg-green-600 text-white rounded text-sm font-medium hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add
        </button>
      </div>
      
      <div className="space-y-2">
        {skipList.map((pattern) => (
          <div
            key={pattern}
            className="flex items-center justify-between bg-slate-900 rounded px-3 py-2"
          >
            <span className="text-slate-300 text-sm font-mono">
              {pattern}
            </span>
            <button
              onClick={() => handleRemove(pattern)}
              className="text-red-400 hover:text-red-300"
            >
              Remove
            </button>
          </div>
        ))}
        {skipList.length === 0 && (
          <div className="text-slate-500 text-sm">
            No patterns in skip list
          </div>
        )}
      </div>
    </div>
  );
} 