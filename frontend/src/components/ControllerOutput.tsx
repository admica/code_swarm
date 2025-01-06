import { useEffect, useRef, useState } from 'react';
import { useWebSocket } from '../lib/websocket';

interface ControllerOutputProps {
  className?: string;
}

interface StdoutMessage {
  timestamp: string;
  content: string;
}

export function ControllerOutput({ className = '' }: ControllerOutputProps) {
  const [messages, setMessages] = useState<StdoutMessage[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMessage = (message: any) => {
    if (message.type === 'stdout') {
      const now = new Date().toISOString().replace('T', ' ').slice(0, 19);
      setMessages(prev => [...prev, {
        timestamp: now,
        content: message.data
      }]);

      if (autoScroll && containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    }
  };

  useWebSocket({ onMessage: handleMessage });

  const handleClear = () => {
    setMessages([]);
  };

  return (
    <div className={`flex flex-col h-64 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-4">
          <h2 className="text-lg font-semibold text-white">Controller Output</h2>
          <button
            onClick={handleClear}
            className="px-2 py-1 rounded text-xs font-medium bg-slate-700 text-slate-300 hover:bg-slate-600"
          >
            Clear
          </button>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-slate-400">
            {messages.length} messages
          </span>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded border-slate-700 bg-slate-900 text-green-500 focus:ring-0"
            />
            <span className="text-sm text-slate-300">Auto-scroll</span>
          </label>
        </div>
      </div>

      <div
        ref={containerRef}
        className="flex-1 overflow-auto rounded-lg border border-slate-800 bg-slate-900/50 font-mono text-sm"
      >
        <div className="p-4 space-y-1">
          {messages.map((message, index) => (
            <pre
              key={index}
              className="whitespace-pre-wrap break-all font-mono text-xs text-slate-300"
            >
              <span className="text-slate-500">{message.timestamp}</span>
              {' '}
              {message.content}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
} 