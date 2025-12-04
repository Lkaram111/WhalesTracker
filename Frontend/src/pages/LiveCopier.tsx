import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from '@/lib/apiClient';
import type { BacktestRunSummary, ChainId, LiveTrade, WhaleSummary } from '@/types/api';
import { formatUSDExact, formatPercent, formatDate, formatAddress } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { Loader2, Play, Square, Radio, ArrowRight } from 'lucide-react';

const chainOptions: ChainId[] = ['hyperliquid', 'ethereum', 'bitcoin'];

export default function LiveCopier() {
  const [chain, setChain] = useState<ChainId>('hyperliquid');
  const [address, setAddress] = useState('');
  const [whales, setWhales] = useState<WhaleSummary[]>([]);
  const [runs, setRuns] = useState<BacktestRunSummary[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [live, setLive] = useState(false);
  const [feed, setFeed] = useState<LiveTrade[]>([]);
  const [positionPctOverride, setPositionPctOverride] = useState<number | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastTsRef = useRef<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [status, setStatus] = useState<{ processed: number; errors: string[]; notifications: string[] }>({
    processed: 0,
    errors: [],
    notifications: [],
  });
  const sessionStorageKey = 'liveCopierSession';

  useEffect(() => {
    const params = new URLSearchParams();
    params.set('limit', '200');
    api.getWhales(params)
      .then((res) => setWhales(res.items || []))
      .catch(() => setWhales([]));
  }, []);

  const selectedRun = useMemo(() => runs.find((r) => r.id === selectedRunId) || null, [runs, selectedRunId]);

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

  // Restore an active copier session if it exists (after refresh/navigation)
  useEffect(() => {
    const restore = async () => {
      if (!chain || !address) return;
      try {
        const active = await api.listActiveCopierSessions(chain, address);
        if (active && active.length > 0) {
          const sess = active[0];
          setSessionId(sess.session_id);
          setLive(sess.active);
          setStatus({
            processed: sess.processed,
            errors: sess.errors || [],
            notifications: sess.notifications || [],
          });
          // restart polling from scratch
          lastTsRef.current = undefined;
        }
      } catch (err) {
        // ignore restore errors
      }
    };
    restore();
  }, [chain, address]);

  const startLive = () => {
    if (!selectedRun || !address) return;
    setError(null);
    setFeed([]);
    lastTsRef.current = undefined;
    api.startCopierSession({
      chain,
      address,
      run_id: selectedRun.id,
      execute: false,
      position_size_pct: positionPctOverride,
    })
      .then((res) => {
        setSessionId(res.session_id);
        setLive(true);
        setStatus({ processed: res.processed, errors: res.errors || [], notifications: res.notifications || [] });
        try {
          const payload = { session_id: res.session_id, chain, address };
          localStorage.setItem(sessionStorageKey, JSON.stringify(payload));
        } catch (_) {
          // ignore storage issues
        }
      })
      .catch((err: any) => {
        setError(err?.message || 'Failed to start session');
        setLive(false);
      });
  };

  const stopLive = () => {
    setLive(false);
    if (pollRef.current) clearInterval(pollRef.current);
    if (sessionId !== null) {
        api.stopCopierSession(sessionId).catch(() => {});
    }
    lastTsRef.current = undefined;
    try {
      localStorage.removeItem(sessionStorageKey);
    } catch (_) {
      // ignore storage issues
    }
  };

  // poll trades every second when live
  useEffect(() => {
    if (!live || !selectedRun || !chain || !address) {
      if (pollRef.current) clearInterval(pollRef.current);
      return;
    }
    const tick = async () => {
      try {
        const res = await api.getLiveTrades(chain, address, lastTsRef.current);
        const newTrades = res.trades || [];
        if (newTrades.length) {
          setFeed((prev) => [...prev, ...newTrades]);
          const last = newTrades[newTrades.length - 1];
          lastTsRef.current = last.timestamp;
        }
        if (sessionId !== null) {
          try {
            const st = await api.getCopierSessionStatus(sessionId);
            setStatus({ processed: st.processed, errors: st.errors || [], notifications: st.notifications || [] });
            if (!st.active) setLive(false);
          } catch (_) {
            // ignore status errors
          }
        }
      } catch (err) {
        // ignore for now
      }
    };
    tick();
    pollRef.current = setInterval(tick, 1000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [live, selectedRun, chain, address, sessionId]);

  // On first render, attempt to reattach to a stored session id
  useEffect(() => {
    try {
      const raw = localStorage.getItem(sessionStorageKey);
      if (!raw) return;
      const stored = JSON.parse(raw);
      if (stored?.session_id && stored.chain === chain && stored.address === address) {
        setSessionId(stored.session_id);
        setLive(true);
      } else {
        localStorage.removeItem(sessionStorageKey);
      }
    } catch (_) {
      // ignore storage errors
    }
  }, [chain, address]);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Live Copier</h1>
          <p className="text-muted-foreground">Pick a backtested preset and shadow the whale in real-time.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Radio className={cn('h-4 w-4', live ? 'text-success animate-pulse' : 'text-muted-foreground')} />
          {live ? 'Polling every second' : 'Idle'}
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
              onClick={live ? stopLive : startLive}
              disabled={!selectedRun || loadingRuns}
              className={cn(
                'inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors',
                live
                  ? 'bg-destructive/10 text-destructive border border-destructive/40'
                  : 'bg-primary text-primary-foreground hover:bg-primary/90'
              )}
            >
              {live ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
              {live ? 'Stop' : 'Start Live Copy'}
            </button>
            {loadingRuns && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
          </div>

          {error && <div className="text-sm text-destructive">{error}</div>}
          {sessionId && (
            <div className="text-xs text-muted-foreground">
              Session #{sessionId} - processed {status.processed} trades
              {status.errors.length > 0 && (
                <div className="text-destructive mt-1">Last error: {status.errors[status.errors.length - 1]}</div>
              )}
              {status.notifications.length > 0 && (
                <div className="mt-1 text-foreground">Note: {status.notifications[status.notifications.length - 1]}</div>
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
                        <div>Leverage: {r.leverage ? `${r.leverage.toFixed(2)}x` : 'n/a'}</div>
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
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-md font-semibold text-foreground">Live feed</h3>
              <span className="text-xs text-muted-foreground">Updates every second</span>
            </div>
            {feed.length === 0 ? (
              <div className="text-sm text-muted-foreground">No trades yet. Start live copy to begin tracking.</div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {feed.slice(-100).reverse().map((t) => (
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
    </div>
  );
}

