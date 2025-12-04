import { useEffect } from 'react';
import { Radio, RefreshCw } from 'lucide-react';
import { CopierCard } from './CopierCard';
import { useCopierStore } from '@/stores/copierStore';

export function CopierDock() {
  const copiers = useCopierStore((s) => Object.values(s.copiers));
  const restoreSessions = useCopierStore((s) => s.restoreSessions);
  const pollActiveCopiers = useCopierStore((s) => s.pollActiveCopiers);

  const activeCopiers = copiers
    .filter((c) => c.active)
    .sort((a, b) => b.createdAt - a.createdAt);

  useEffect(() => {
    void restoreSessions();
  }, [restoreSessions]);

  useEffect(() => {
    if (!activeCopiers.length) return;
    const id = setInterval(() => void pollActiveCopiers(), 1000);
    void pollActiveCopiers();
    return () => clearInterval(id);
  }, [activeCopiers.length, pollActiveCopiers]);

  if (!activeCopiers.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-40 w-full max-w-sm">
      <div className="rounded-2xl border border-primary/30 bg-background/95 shadow-2xl backdrop-blur-lg supports-[backdrop-filter]:bg-background/80">
        <div className="flex items-center justify-between border-b border-border/70 px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Radio className="h-4 w-4 text-primary" />
            Active Copiers ({activeCopiers.length})
          </div>
          <button
            type="button"
            onClick={() => void pollActiveCopiers()}
            className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-1 text-xs font-semibold text-foreground transition-colors hover:bg-muted"
          >
            <RefreshCw className="h-3 w-3" />
            Sync
          </button>
        </div>
        <div className="max-h-[320px] space-y-3 overflow-y-auto px-4 py-3">
          {activeCopiers.map((c) => (
            <CopierCard key={c.sessionId} copier={c} compact allowRemove={false} />
          ))}
        </div>
      </div>
    </div>
  );
}
