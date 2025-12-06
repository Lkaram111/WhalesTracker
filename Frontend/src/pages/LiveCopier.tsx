import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/apiClient';
import type { BacktestRunSummary, ChainId, WhaleSummary } from '@/types/api';
import { formatUSDExact, formatPercent, formatDate, formatAddress } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { Loader2, Play, Square, Radio, ArrowRight } from 'lucide-react';
import { useCopierStore } from '@/stores/copierStore';
import { CopierCard } from '@/components/domain/copier/CopierCard';

const chainOptions: ChainId[] = ['hyperliquid', 'ethereum', 'bitcoin'];

export default function LiveCopier() {
  const [chain, setChain] = useState<ChainId>('hyperliquid');
  const [address, setAddress] = useState('');
  const [whales, setWhales] = useState<WhaleSummary[]>([]);
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [positionPctOverride, setPositionPctOverride] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const { startCopier, stopCopier, copiers } = useCopierStore((s) => ({
    startCopier: s.startCopier,
    stopCopier: s.stopCopier,
    copiers: s.copiers,
  }));

  const copierList = useMemo(() => Object.values(copiers).sort((a, b) => b.createdAt - a.createdAt), [copiers]);
  const activeCount = copierList.filter((c) => c.active).length;
  const [focusedSessionId, setFocusedSessionId] = useState<number | null>(null);

  const selectedRun = useMemo(() => runs.find((r) => r.id === selectedRunId) || null, [runs, selectedRunId]);
  const focusedCopier = focusedSessionId ? copiers[focusedSessionId] : null;

  useEffect(() => {
    const params = new URLSearchParams();
    params.set('limit', '200');
    api
      .getWhales(params)
      .then((res) => setWhales(res.items || []))
      .catch(() => setWhales([]));
  }, []);

  const loadRuns = async (c: ChainId, addr: string) => {
    setLoadingRuns(true);
    setError(null);
    try {
      const data = await api.getBacktestRuns(c, addr, 50);
      setRuns(data || []);
      if (data?.length) {
        setSelectedRunId(data[0].id);
      } else {
        setSelectedRunId(null);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load backtests');
      setRuns([]);
    } finally {
      setLoadingRuns(false);
    }
  };

  useEffect(() => {
    if (chain && address) {
      loadRuns(chain, address);
    } else {
      setRuns([]);
      setSelectedRunId(null);
    }
  }, [chain, address]);

  useEffect(() => {
    if (focusedSessionId && copiers[focusedSessionId]) return;
    if (!focusedSessionId && copierList.length) {
      setFocusedSessionId(copierList[0].sessionId);
      return;
    }
    if (focusedSessionId && !copiers[focusedSessionId]) {
      if (copierList.length) {
        setFocusedSessionId(copierList[0].sessionId);
      } else {
        setFocusedSessionId(null);
      }
    }
  }, [focusedSessionId, copiers, copierList]);

  const handleStart = async () => {
    if (!selectedRun || !address) return;
    setError(null);
    setStarting(true);
    try {
      const whaleLabel = whales.find((w) => w.address === address)?.labels?.[0] ?? null;
      const session = await startCopier({
        chain,
        address,
        runId: selectedRun.id,
        positionSizePct: positionPctOverride,
        execute: false,
        label: whaleLabel,
      });
      setFocusedSessionId(session.sessionId);
    } catch (err: any) {
      setError(err?.message || 'Failed to start session');
    } finally {
      setStarting(false);
    }
  };

  const handleStopFocused = () => {
    if (focusedSessionId) {
      void stopCopier(focusedSessionId);
    }
  };

  const liveFeed = focusedCopier?.feed ?? [];

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Live Copier</h1>
          <p className="text-muted-foreground">Pick a backtested preset and shadow the whale in real-time.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Radio className={cn('h-4 w-4', activeCount ? 'text-success animate-pulse' : 'text-muted-foreground')} />
          {activeCount ? `${activeCount} active copier${activeCount > 1 ? 's' : ''}` : 'Idle'}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card-glass rounded-xl p-4 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            <Play className="h-4 w-4 text-primary" />
            Copier Inputs
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">Chain</label>
              <div className="flex gap-2">
                {chainOptions.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    onClick={() => setChain(opt)}
                    className={cn(
                      'flex-1 rounded-lg border px-3 py-2 text-sm font-medium transition-all',
                      chain === opt
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            <div className="sm:col-span-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">Select Whale</label>
              <select
                value={address}
                onChange={(e) => {
                  const selected = whales.find((w) => w.address === e.target.value);
                  setAddress(e.target.value);
                  if (selected) {
                    setChain(selected.chain as ChainId);
                  }
                }}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="">-- Choose from tracked whales --</option>
                {whales.map((w) => (
                  <option key={w.id} value={w.address}>
                    {w.labels && w.labels.length ? w.labels[0] : formatAddress(w.address)} - {w.chain}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">Whale Address</label>
              <input
                required
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="0x..."
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">Position Size % (override)</label>
              <input
                type="number"
                min={0}
                max={200}
                step={0.0001}
                value={positionPctOverride ?? ''}
                onChange={(e) => {
                  const v = e.target.value === '' ? null : Number(e.target.value);
                  setPositionPctOverride(v);
                }}
                placeholder="Use backtest value"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleStart}
              disabled={!selectedRun || loadingRuns || starting}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors',
                'bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50'
              )}
            >
              <Play className="h-4 w-4" />
              Start Whale Copier
            </button>
            {focusedCopier && (
              <button
                type="button"
                onClick={handleStopFocused}
                disabled={!focusedCopier.active}
                className={cn(
                  'inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold transition-colors',
                  focusedCopier.active
                    ? 'border-destructive/40 text-destructive hover:bg-destructive/10'
                    : 'border-border text-muted-foreground'
                )}
              >
                <Square className="h-4 w-4" />
                Stop Focused
              </button>
            )}
            {(loadingRuns || starting) && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          </div>

          {error && <div className="text-sm text-destructive">{error}</div>}
          {focusedCopier && (
            <div className="text-xs text-muted-foreground">
              Session #{focusedCopier.sessionId} - processed {focusedCopier.status.processed} trades
              {focusedCopier.status.errors.length > 0 && (
                <div className="text-destructive mt-1">
                  Last error: {focusedCopier.status.errors[focusedCopier.status.errors.length - 1]}
                </div>
              )}
              {focusedCopier.status.notifications.length > 0 && (
                <div className="mt-1 text-foreground">
                  Note: {focusedCopier.status.notifications[focusedCopier.status.notifications.length - 1]}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="lg:col-span-2 space-y-4">
          <div className="card-glass rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-md font-semibold text-foreground">Backtested presets</h3>
              <span className="text-xs text-muted-foreground">Newest first</span>
            </div>
            {loadingRuns ? (
              <div className="flex items-center gap-2 text-muted-foreground text-sm"><Loader2 className="h-4 w-4 animate-spin" /> Loading presets...</div>
            ) : runs.length === 0 ? (
              <div className="text-sm text-muted-foreground">No saved backtests for this wallet yet.</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {runs.map((r) => {
                  const active = selectedRunId === r.id;
                  return (
                    <button
                      key={r.id}
                      onClick={() => setSelectedRunId(r.id)}
                      className={cn(
                        'text-left rounded-lg border p-3 transition-all',
                        active ? 'border-primary bg-primary/10 shadow-lg' : 'border-border hover:bg-muted'
                      )}
                    >
                      <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
                        <span>{formatDate(r.created_at)}</span>
                        {active && <span className="text-primary font-semibold">Selected</span>}
                      </div>
                      <div className="text-sm font-semibold text-foreground flex items-center gap-2">
                        {r.asset_symbols && r.asset_symbols.length ? r.asset_symbols.join(', ') : 'All assets'}
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        {r.position_size_pct != null ? `${r.position_size_pct.toFixed(1)}% size` : 'auto size'}
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground space-y-1">
                        <div>Leverage: {r.leverage != null ? `${r.leverage.toFixed(2)}x` : 'auto'}</div>
                        <div>Win rate: {r.win_rate_percent != null ? formatPercent(r.win_rate_percent) : 'n/a'}</div>
                        <div>Trades: {r.trades_copied ?? 'n/a'}</div>
                        <div>Max DD: {r.max_drawdown_percent != null ? formatPercent(r.max_drawdown_percent) : 'n/a'}</div>
                        <div>ROI: {r.roi_percent != null ? formatPercent(r.roi_percent) : 'n/a'}</div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="card-glass rounded-xl p-4">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <div className="flex items-center gap-2">
                <h3 className="text-md font-semibold text-foreground">Live feed</h3>
                {focusedCopier && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                    Session #{focusedCopier.sessionId}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Viewing</span>
                <select
                  value={focusedSessionId ?? ''}
                  onChange={(e) => setFocusedSessionId(e.target.value ? Number(e.target.value) : null)}
                  className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <option value="">-- choose copier --</option>
                  {copierList.map((c) => (
                    <option key={c.sessionId} value={c.sessionId}>
                      Session #{c.sessionId} · {formatAddress(c.address)} · {c.chain}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {liveFeed.length === 0 ? (
              <div className="text-sm text-muted-foreground">
                {focusedCopier ? 'No trades yet for this session.' : 'Start a whale copier and select it to see trades here.'}
              </div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {liveFeed.slice(-100).reverse().map((t) => (
                  <div key={t.id} className="flex items-center justify-between rounded-lg border border-border/50 px-3 py-2">
                    <div className="flex flex-col">
                      <span className="text-xs text-muted-foreground">{formatDate(t.timestamp)}</span>
                      <span className="text-sm font-semibold text-foreground">
                        {t.direction.toLowerCase()} {t.base_asset || 'asset'}
                      </span>
                    </div>
                    <div className="text-sm text-foreground">{t.value_usd != null ? formatUSDExact(t.value_usd) : 'n/a'}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="card-glass rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-md font-semibold text-foreground">Active copier sessions</h3>
          <span className="text-xs text-muted-foreground">
            {activeCount} live · {copierList.length} total
          </span>
        </div>
        {copierList.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            Start a whale copier to spin up a card. Sessions keep running while you browse other pages.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {copierList.map((c) => (
              <CopierCard
                key={c.sessionId}
                copier={c}
                onFocus={setFocusedSessionId}
                isFocused={focusedSessionId === c.sessionId}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
