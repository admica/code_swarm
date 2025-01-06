import { SkipListManager } from '@/components/SkipListManager';

export function Settings() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="mt-2 text-slate-400">
          Configure monitoring and agent behavior
        </p>
      </div>

      <div className="space-y-6">
        <section>
          <h2 className="text-xl font-semibold mb-4">Skip List Configuration</h2>
          <p className="text-slate-400 mb-4">
            Add paths or patterns to exclude from monitoring. Common examples include:
            <code className="ml-2 text-slate-300">node_modules/</code>,
            <code className="ml-2 text-slate-300">venv/</code>,
            <code className="ml-2 text-slate-300">.git/</code>
          </p>
          <SkipListManager />
        </section>
      </div>
    </div>
  );
} 