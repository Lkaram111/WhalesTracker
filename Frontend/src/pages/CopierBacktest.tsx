import { useEffect, useState } from 'react';
import { api } from '@/lib/apiClient';
import type { ChainId, CopierBacktestResponse, WhaleSummary } from '@/types/api';
import { formatUSDExact, formatPercent, formatDate, formatAddress } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import { Loader2, Play, SlidersHorizontal, CheckSquare, Square } from 'lucide-react';

const chainOptions: ChainId[] = ['hyperliquid', 'ethereum', 'bitcoin'];

export default function CopierBacktest() {
  const [chain, setChain] = useState<ChainId>('hyperliquid');
  const [address, setAddress] = useState('');
  const [whales, setWhales] = useState<WhaleSummary[]>([]);
  const [assets, setAssets] = useState<string[]>([]);
  const [selectedAssets, setSelectedAssets] = useState<string[]>([]);
  const [initialDeposit, setInitialDeposit] = useState(10000);
  const [positionPct, setPositionPct] = useState<number | null>(null);
  const [feeBps, setFeeBps] = useState(5);
  const [slippageBps, setSlippageBps] = useState(5);
  const [leverage, setLeverage] = useState(1);
  const [start, setStart] = useState<string>('');
  const [end, setEnd] = useState<string>('');
  const [includePrices, setIncludePrices] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CopierBacktestResponse | null>(null);

  // preload whales for selection
  useEffect(() => {
    const params = new URLSearchParams();
    params.set('limit', '200');
    api.getWhales(params)
      .then((res) => setWhales(res.items || []))
      .catch(() => setWhales([]));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload: any = {
        chain,
        address,
        initial_deposit_usd: initialDeposit,
        fee_bps: feeBps,
        slippage_bps: slippageBps,
        leverage,
      };
      if (selectedAssets.length > 0) payload.asset_symbols = selectedAssets;
      if (positionPct !== null) payload.position_size_pct = positionPct;
      if (start) payload.start = new Date(start).toISOString();
      if (end) payload.end = new Date(end).toISOString();
      if (includePrices) payload.include_price_points = true;
      const data = await api.runCopierBacktest(payload);
      setResult(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  // fetch assets when chain/address set
  useEffect(() => {
    if (!chain || !address) {
      setAssets([]);
      setSelectedAssets([]);
      return;
    }
    api.getWhaleAssets(chain, address)
      .then((res) => {
        setAssets(res.assets || []);
        setSelectedAssets([]);
      })
      .catch(() => {
        setAssets([]);
        setSelectedAssets([]);
      });
  }, [chain, address]);

  return (
    <div className="space-y-6 animate-fade-up">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Copier Backtest</h1>
          <p className="text-muted-foreground">
            Simulate copying a whale&apos;s entries/exits with your own capital, including fees & slippage.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <form onSubmit={handleSubmit} className="card-glass rounded-xl p-4 space-y-4 lg:col-span-1">
          <div className="flex items-center gap-2 text-sm font-medium text-foreground">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            Backtest Inputs
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="sm:col-span-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Chain
              </label>
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
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Select Whale
              </label>
              <select
                value={address}
                onChange={(e) => {
                  const selected = whales.find((w) => w.address === e.target.value);
                  setAddress(e.target.value);
                  if (selected) {
                    setChain(selected.chain);
                  }
                }}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="">-- Choose from tracked whales --</option>
                {whales.map((w) => (
                  <option key={w.id} value={w.address}>
                    {w.labels && w.labels.length ? w.labels[0] : formatAddress(w.address)} · {w.chain}
                  </option>
                ))}
              </select>
            </div>

            <div className="sm:col-span-2">
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Whale Address
              </label>
              <input
                required
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="0x..."
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            {assets.length > 0 && (
              <div className="sm:col-span-2">
                <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                  Assets to Copy (optional)
                </label>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedAssets([])}
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-xs transition-all',
                      selectedAssets.length === 0
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted'
                    )}
                  >
                    All assets
                  </button>
                  {assets.map((sym) => {
                    const active = selectedAssets.includes(sym);
                    return (
                      <button
                        type="button"
                        key={sym}
                        onClick={() => {
                          setSelectedAssets((prev) =>
                            active ? prev.filter((s) => s !== sym) : [...prev, sym]
                          );
                        }}
                        className={cn(
                          'flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs transition-all',
                          active
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border text-muted-foreground hover:bg-muted'
                        )}
                      >
                        {active ? <CheckSquare className="h-3 w-3" /> : <Square className="h-3 w-3" />}
                        {sym}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Initial Deposit (USD)
              </label>
              <input
                type="number"
                min={1}
                value={initialDeposit}
                onChange={(e) => setInitialDeposit(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Position Size % (optional)
              </label>
              <input
                type="number"
                min={0}
                step={0.0001}
                max={200}
                value={positionPct ?? ''}
                onChange={(e) => {
                  const v = e.target.value === '' ? null : Number(e.target.value);
                  setPositionPct(v);
                }}
                placeholder="auto"
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Fee (bps)
              </label>
              <input
                type="number"
                min={0}
                max={1000}
                value={feeBps}
                onChange={(e) => setFeeBps(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Slippage (bps)
              </label>
              <input
                type="number"
                min={0}
                max={1000}
                value={slippageBps}
                onChange={(e) => setSlippageBps(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Leverage (x)
              </label>
              <input
                type="number"
                min={0.1}
                max={100}
                step={0.1}
                value={leverage}
                onChange={(e) => setLeverage(Number(e.target.value))}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Start (UTC)
              </label>
              <input
                type="datetime-local"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                End (UTC)
              </label>
              <input
                type="datetime-local"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
            </div>

            <div className="sm:col-span-2 flex items-center gap-2">
              <input
                id="includePrices"
                type="checkbox"
                checked={includePrices}
                onChange={(e) => setIncludePrices(e.target.checked)}
                className="h-4 w-4 rounded border-border text-primary focus:ring-primary"
              />
              <label htmlFor="includePrices" className="text-sm text-foreground">
                Include price points used for marking (caches prices in response)
              </label>
            </div>
          </div>

          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-primary-foreground text-sm font-semibold shadow-md hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            Run Backtest
          </button>
        </form>

        <div className="lg:col-span-2 space-y-4">
          <div className="card-glass rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Result</p>
                <h2 className="text-lg font-semibold text-foreground">Performance</h2>
              </div>
              {result && (
                <div className="text-xs text-muted-foreground">
                  Window: {result.summary.start ? formatDate(result.summary.start) : '—'} →{' '}
                  {result.summary.end ? formatDate(result.summary.end) : '—'}
                </div>
              )}
            </div>

            {!result && (
              <div className="text-sm text-muted-foreground mt-6">
                Run a backtest to see PnL, ROI, fees, and trade-by-trade results.
              </div>
            )}

            {result && (
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
                <SummaryTile label="Net PnL" value={formatUSDExact(result.summary.net_pnl_usd)} highlight />
                <SummaryTile label="ROI" value={formatPercent(result.summary.roi_percent)} />
                <SummaryTile label="Gross PnL" value={formatUSDExact(result.summary.gross_pnl_usd)} />
                <SummaryTile label="Fees Paid" value={formatUSDExact(result.summary.total_fees_usd)} />
                <SummaryTile label="Slippage" value={formatUSDExact(result.summary.total_slippage_usd)} />
                <SummaryTile
                  label="Win Rate"
                  value={
                    result.summary.win_rate_percent !== null
                      ? formatPercent(result.summary.win_rate_percent)
                      : '—'
                  }
                />
                <SummaryTile
                  label="Recommended %"
                  value={`${result.summary.recommended_position_pct.toFixed(1)}%`}
                />
                <SummaryTile
                  label="Using %"
                  value={`${result.summary.used_position_pct.toFixed(1)}%`}
                />
                <SummaryTile label="Trades Copied" value={String(result.summary.trades_copied)} />
                <SummaryTile label="Start Equity" value={formatUSDExact(result.summary.initial_deposit_usd)} />
                <SummaryTile label="End Equity" value={formatUSDExact(result.summary.initial_deposit_usd + result.summary.net_pnl_usd)} />
                <SummaryTile
                  label="Assets Copied"
                  value={selectedAssets.length > 0 ? selectedAssets.join(', ') : 'All'}
                />
                <SummaryTile
                  label="Equity Points"
                  value={result.equity_curve ? String(result.equity_curve.length) : '0'}
                />
                <SummaryTile
                  label="Price Points"
                  value={
                    result.price_points
                      ? String(
                          Object.values(result.price_points).reduce(
                            (acc, arr) => acc + (arr?.length || 0),
                            0
                          )
                        )
                      : 'not requested'
                  }
                />
              </div>
            )}
          </div>

          {result && (
            <div className="card-glass rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-md font-semibold text-foreground">Equity Curve (per minute)</h3>
                <p className="text-xs text-muted-foreground">
                  Includes price drift when no trades occur
                </p>
              </div>
              {result.equity_curve && result.equity_curve.length > 1 ? (
                <EquityChart points={result.equity_curve} />
              ) : (
                <div className="text-sm text-muted-foreground">No equity data</div>
              )}
            </div>
          )}

          {result && (
            <div className="card-glass rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-md font-semibold text-foreground">Trade Breakdown</h3>
                <p className="text-xs text-muted-foreground">
                  Cumulative PnL & equity after fees, slippage, and unrealized PnL
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-xs uppercase text-muted-foreground">
                    <tr className="border-b border-border">
                      <th className="text-left py-2 pr-3">Time</th>
                      <th className="text-left py-2 pr-3">Dir</th>
                      <th className="text-left py-2 pr-3">Asset</th>
                      <th className="text-right py-2 pr-3">Notional</th>
                      <th className="text-right py-2 pr-3">PnL</th>
                      <th className="text-right py-2 pr-3">Fees</th>
                      <th className="text-right py-2 pr-3">Slippage</th>
                      <th className="text-right py-2 pr-3">Net</th>
                      <th className="text-right py-2 pr-3">Unrealized</th>
                      <th className="text-right py-2 pr-3">Equity</th>
                      <th className="text-right py-2">Cumulative</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((t) => (
                      <tr key={t.id} className="border-b border-border/50 last:border-0">
                        <td className="py-2 pr-3 text-foreground">{formatDate(t.timestamp)}</td>
                        <td className="py-2 pr-3 text-muted-foreground">{t.direction}</td>
                        <td className="py-2 pr-3 text-muted-foreground">{t.base_asset || '—'}</td>
                        <td className="py-2 pr-3 text-right text-foreground">
                          {formatUSDExact(t.notional_usd, 2, 2)}
                        </td>
                        <td
                          className={cn(
                            'py-2 pr-3 text-right',
                            t.pnl_usd >= 0 ? 'text-success' : 'text-destructive'
                          )}
                        >
                          {formatUSDExact(t.pnl_usd, 2, 2)}
                        </td>
                        <td className="py-2 pr-3 text-right text-muted-foreground">
                          {formatUSDExact(t.fee_usd, 2, 2)}
                        </td>
                        <td className="py-2 pr-3 text-right text-muted-foreground">
                          {formatUSDExact(t.slippage_usd, 2, 2)}
                        </td>
                        <td
                          className={cn(
                            'py-2 pr-3 text-right',
                            t.net_pnl_usd >= 0 ? 'text-success' : 'text-destructive'
                          )}
                        >
                          {formatUSDExact(t.net_pnl_usd, 2, 2)}
                        </td>
                        <td className="py-2 pr-3 text-right text-muted-foreground">
                          {formatUSDExact(t.unrealized_pnl_usd, 2, 2)}
                        </td>
                        <td className="py-2 pr-3 text-right text-foreground">
                          {formatUSDExact(t.equity_usd, 2, 2)}
                        </td>
                        <td
                          className={cn(
                            'py-2 text-right',
                            t.cumulative_pnl_usd >= 0 ? 'text-success' : 'text-destructive'
                          )}
                        >
                          {formatUSDExact(t.cumulative_pnl_usd, 2, 2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function SummaryTile({ label, value, highlight = false }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border/60 p-3 bg-muted/30',
        highlight && 'bg-gradient-to-br from-primary/10 via-primary/5 to-transparent border-primary/40'
      )}
    >
      <p className="text-xs text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="text-sm font-semibold text-foreground mt-1">{value}</p>
    </div>
  );
}

function EquityChart({ points }: { points: { timestamp: string; equity_usd: number }[] }) {
  if (!points.length) return null;
  const values = points.map((p) => p.equity_usd);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = (max - min) * 0.1 || 1;
  const ymin = min - pad;
  const ymax = max + pad;
  const width = 600;
  const height = 200;
  const xs = points.map((_, i) => (i / Math.max(1, points.length - 1)) * width);
  const ys = values.map((v) => height - ((v - ymin) / (ymax - ymin)) * height);
  const d = xs
    .map((x, i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${ys[i].toFixed(2)}`)
    .join(' ');

  return (
    <div className="w-full overflow-x-auto">
      <svg width={width} height={height} className="text-primary">
        <path d={d} fill="none" stroke="currentColor" strokeWidth={2} />
      </svg>
      <div className="mt-2 text-xs text-muted-foreground flex justify-between">
        <span>{formatDate(points[0].timestamp)}</span>
        <span>{formatDate(points[points.length - 1].timestamp)}</span>
      </div>
    </div>
  );
}
