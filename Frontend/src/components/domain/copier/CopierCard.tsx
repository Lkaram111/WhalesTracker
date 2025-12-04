import { useMemo } from 'react';
import { Activity, AlertTriangle, Radio, Square, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatAddress, formatDate, formatTimeAgo, formatUSDExact } from '@/lib/formatters';
import { useCopierStore, type CopierInstance } from '@/stores/copierStore';

interface CopierCardProps {
  copier: CopierInstance;
  compact?: boolean;
  isFocused?: boolean;
  onFocus?: (sessionId: number) => void;
  allowRemove?: boolean;
}

export function CopierCard({ copier, compact = false, isFocused = false, onFocus, allowRemove = true }: CopierCardProps) {
  const stopCopier = useCopierStore((s) => s.stopCopier);
  const removeCopier = useCopierStore((s) => s.removeCopier);

  const lastTrade = useMemo(() => (copier.feed.length ? copier.feed[copier.feed.length - 1] : null), [copier.feed]);
  const lastError = copier.status.errors.length ? copier.status.errors[copier.status.errors.length - 1] : null;
  const lastNote = copier.status.notifications.length ? copier.status.notifications[copier.status.notifications.length - 1] : null;
  const createdLabel = useMemo(() => formatDate(new Date(copier.createdAt).toISOString()), [copier.createdAt]);

  return (
    <div
      className={cn(
        'rounded-xl border border-border/70 bg-background/85 shadow-lg backdrop-blur supports-[backdrop-filter]:bg-background/70',
        compact ? 'p-3 space-y-2' : 'p-4 space-y-3',
        isFocused && 'ring-2 ring-primary/60'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Radio className={cn('h-4 w-4', copier.active ? 'text-primary animate-pulse' : 'text-muted-foreground')} />
            <span className="text-sm font-semibold text-foreground">
              {copier.label || formatAddress(copier.address)}
            </span>
            <span className="rounded-full border border-border px-2 py-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
              {copier.chain}
            </span>
            <span className="text-[11px] text-muted-foreground">Session #{copier.sessionId}</span>
          </div>
          <div className="text-xs text-muted-foreground">
            Run #{copier.runId} • Started {createdLabel}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {onFocus && (
            <button
              type="button"
              onClick={() => onFocus(copier.sessionId)}
              className={cn(
                'rounded-full border px-2 py-1 text-[11px] font-semibold transition-colors',
                isFocused ? 'border-primary text-primary' : 'border-border text-muted-foreground hover:text-foreground'
              )}
            >
              Focus
            </button>
          )}
          <button
            type="button"
            onClick={() => void stopCopier(copier.sessionId)}
            disabled={!copier.active}
            className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-semibold text-foreground transition-colors hover:bg-muted disabled:opacity-50"
          >
            <Square className="h-3 w-3" />
            Stop
          </button>
          {allowRemove && !copier.active && (
            <button
              type="button"
              aria-label="Remove copier card"
              onClick={() => removeCopier(copier.sessionId)}
              className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted"
            >
              <X className="h-4 w-4 text-muted-foreground" />
            </button>
          )}
        </div>
      </div>

      <div className={cn('rounded-lg border border-border/70 bg-muted/30 px-3 py-2', compact ? 'text-xs' : 'text-sm')}>
        <div className="flex items-center gap-2 text-foreground">
          <Activity className="h-4 w-4 text-primary" />
          <span className="font-semibold">{copier.status.processed} trades copied</span>
        </div>
        <div className="mt-1 text-muted-foreground text-xs">
          {lastNote || (copier.active ? 'Live and polling every second' : 'Inactive')}
        </div>
      </div>

      {lastTrade ? (
        <div className={cn('rounded-lg border border-border/60 bg-background/60 px-3 py-2', compact ? 'text-xs' : 'text-sm')}>
          <div className="flex items-center justify-between gap-2">
            <div className="flex flex-col">
              <span className="text-xs text-muted-foreground">Last trade {formatTimeAgo(lastTrade.timestamp)}</span>
              <span className="font-semibold text-foreground">
                {lastTrade.direction.toLowerCase()} {lastTrade.base_asset || 'asset'}
              </span>
            </div>
            <div className="text-xs font-semibold text-foreground">
              {lastTrade.value_usd != null ? formatUSDExact(lastTrade.value_usd) : 'n/a'}
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-border/60 bg-background/40 px-3 py-2 text-xs text-muted-foreground">
          Waiting for first live trade...
        </div>
      )}

      {(lastError || lastNote) && (
        <div
          className={cn(
            'flex items-start gap-2 rounded-lg px-3 py-2 text-xs',
            lastError ? 'border border-destructive/40 bg-destructive/10 text-destructive' : 'border border-primary/30 bg-primary/5 text-foreground'
          )}
        >
          <AlertTriangle className="h-4 w-4" />
          <div className="flex-1">
            <div className="font-semibold">{lastError ? 'Issue' : 'Note'}</div>
            <div className="text-xs leading-snug">{lastError || lastNote}</div>
          </div>
        </div>
      )}
    </div>
  );
}
