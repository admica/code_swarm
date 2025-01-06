import { useState, useEffect } from 'react';
import { agentsApi } from '../lib/api';

export function AIMarkerConfig() {
  const [beginMarker, setBeginMarker] = useState('');
  const [endMarker, setEndMarker] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadMarkers = async () => {
      try {
        const markers = await agentsApi.getAIMarkers();
        setBeginMarker(markers.begin);
        setEndMarker(markers.end);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load AI markers');
      } finally {
        setIsLoading(false);
      }
    };

    loadMarkers();
  }, []);

  const handleSaveBegin = async () => {
    try {
      await agentsApi.setAIMarkers(beginMarker, endMarker);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save begin marker');
    }
  };

  const handleSaveEnd = async () => {
    try {
      await agentsApi.setAIMarkers(beginMarker, endMarker);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save end marker');
    }
  };

  if (isLoading) {
    return <div className="text-slate-400">Loading...</div>;
  }

  if (error) {
    return <div className="text-red-400">Error: {error}</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold mb-4">AI Content Markers</h2>
      <p className="text-slate-400 mb-4">
        Configure the markers used to identify AI-generated content in README files.
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Begin Marker
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={beginMarker}
              onChange={(e) => setBeginMarker(e.target.value)}
              className="flex-1 rounded-md bg-slate-900 border border-slate-700 px-3 py-2 text-sm text-slate-300 placeholder-slate-500"
              placeholder="(BEGIN AI Generated)"
            />
            <button
              onClick={handleSaveBegin}
              className="px-3 py-2 rounded-md text-sm font-medium bg-green-900/50 text-green-300 hover:bg-green-900 disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            End Marker
          </label>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={endMarker}
              onChange={(e) => setEndMarker(e.target.value)}
              className="flex-1 rounded-md bg-slate-900 border border-slate-700 px-3 py-2 text-sm text-slate-300 placeholder-slate-500"
              placeholder="(END AI Generated)"
            />
            <button
              onClick={handleSaveEnd}
              className="px-3 py-2 rounded-md text-sm font-medium bg-green-900/50 text-green-300 hover:bg-green-900 disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
} 