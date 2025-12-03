import { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { WalletHeader } from '@/components/domain/wallet/WalletHeader';
import { WalletMetricsGrid } from '@/components/domain/wallet/WalletMetricsGrid';
import { HoldingsTable } from '@/components/domain/wallet/HoldingsTable';
import { HoldingsDonut } from '@/components/domain/wallet/HoldingsDonut';
import { TradesTable } from '@/components/domain/wallet/TradesTable';
import { RoiChart } from '@/components/domain/charts/RoiChart';
import { PortfolioChart } from '@/components/domain/charts/PortfolioChart';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { BackfillStatus, ChainId, Trade, WalletDetails, OpenPosition } from '@/types/api';
import { api } from '@/lib/apiClient';
import { formatUSDExact } from '@/lib/formatters';
import { Button } from '@/components/ui/button';
import { aggregateTrades } from '@/lib/tradeGrouping';

export default function WhaleDetail() {
  const { chain, address } = useParams<{ chain: ChainId; address: string }>();
  const [roiRange, setRoiRange] = useState(30);
  const [portfolioRange, setPortfolioRange] = useState(30);
  const [tradeSource, setTradeSource] = useState<Trade['source'] | 'all'>('all');
  const [tradeDirection, setTradeDirection] = useState<Trade['direction'] | 'all'>('all');

  const [walletDetails, setWalletDetails] = useState<WalletDetails | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [tradesNextCursor, setTradesNextCursor] = useState<string | null>(null);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [positions, setPositions] = useState<OpenPosition[]>([]);
  const [roiHistory, setRoiHistory] = useState<{ timestamp: string; roi_percent: number }[]>([]);
  const [portfolioHistory, setPortfolioHistory] = useState<{ timestamp: string; value_usd: number }[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);

  const [whaleId, setWhaleId] = useState<string | null>(null);
  const [backfillStatus, setBackfillStatus] = useState<BackfillStatus | null>(null);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [groupSimilarTrades, setGroupSimilarTrades] = useState(false);

  const fillDailySeries = <T extends { timestamp: string }>(
    points: T[],
    days: number,
    valueKey: keyof T,
    defaultValue: number = 0
  ) => {
    const sorted = [...points].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    const byDate = new Map<string, T>();
    sorted.forEach((p) => {
      const key = new Date(p.timestamp).toISOString().slice(0, 10);
      byDate.set(key, p);
    });

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const start = new Date(today);
    start.setDate(start.getDate() - days);

    const filled: T[] = [];
    let lastValue =
      sorted.length > 0 && typeof sorted[0][valueKey] === 'number'
        ? (sorted[0][valueKey] as number)
        : defaultValue;

    for (
      const cursor = new Date(start);
      cursor.getTime() <= today.getTime();
      cursor.setDate(cursor.getDate() + 1)
    ) {
      const key = cursor.toISOString().slice(0, 10);
      const match = byDate.get(key);
      if (match) {
        const val = match[valueKey];
        if (typeof val === 'number') {
          lastValue = val;
        }
        filled.push({ ...match, timestamp: new Date(key).toISOString() });
      } else {
        filled.push({
          ...(sorted[0] || { timestamp: cursor.toISOString() }),
          timestamp: cursor.toISOString(),
          [valueKey]: lastValue,
        } as T);
      }
    }
    return filled;
  };

  const rangeOptions = [
    { label: '7d', value: 7 },
    { label: '30d', value: 30 },
    { label: '90d', value: 90 },
    { label: 'All', value: 180 },
  ];
  const tradeTabs: { value: Trade['source'] | 'all'; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: 'onchain', label: 'On-chain' },
    { value: 'hyperliquid', label: 'Hyperliquid' },
    { value: 'exchange_flow', label: 'Exchange Flows' },
  ];

  useEffect(() => {
    if (!chain || !address) return;
    api
      .getWalletDetails(chain, address)
      .then((data) => {
        setWalletDetails(data);
        if (data.wallet?.id) {
          setWhaleId(data.wallet.id);
        }
      })
      .catch(() => setWalletDetails(null));
  }, [chain, address, refreshKey]);

  useEffect(() => {
    if (!chain || !address) return;
    const source = tradeSource === 'all' ? undefined : tradeSource;
    const direction = tradeDirection === 'all' ? undefined : tradeDirection;
    setTradesLoading(true);
    api.getWalletTrades(chain, address, source, direction, 200)
      .then((res) => {
        setTrades(res.items);
        setTradesNextCursor(res.next_cursor);
      })
      .catch(() => {
        setTrades([]);
        setTradesNextCursor(null);
      })
      .finally(() => setTradesLoading(false));
  }, [chain, address, tradeSource, tradeDirection, refreshKey]);

  useEffect(() => {
    if (!chain || !address) return;
    api.getWalletPositions(chain, address)
      .then((res) => setPositions(res.items))
      .catch(() => setPositions([]));
  }, [chain, address, refreshKey]);

  useEffect(() => {
    if (!chain || !address) return;
    api
      .getWalletRoiHistory(chain, address, roiRange)
      .then((res) => setRoiHistory(fillDailySeries(res.points, roiRange, 'roi_percent', 0)))
      .catch(() => setRoiHistory([]));
  }, [chain, address, roiRange, refreshKey]);

  useEffect(() => {
    if (!chain || !address) return;
    api
      .getWalletPortfolioHistory(chain, address, portfolioRange)
      .then((res) => setPortfolioHistory(fillDailySeries(res.points, portfolioRange, 'value_usd', 0)))
      .catch(() => setPortfolioHistory([]));
  }, [chain, address, portfolioRange, refreshKey]);

  useEffect(() => {
    if (!chain || !address) return;
    const params = new URLSearchParams();
    params.set('search', address);
    params.set('limit', '5');
    params.set('chain', chain);
    api
      .getWhales(params)
      .then((res) => {
        const match = res.items.find(
          (w) => w.chain === chain && w.address.toLowerCase() === address.toLowerCase()
        );
        setWhaleId(match ? match.id : null);
      })
      .catch(() => setWhaleId((prev) => prev || null));
  }, [chain, address]);

  // Fallback resolve if id still missing
  useEffect(() => {
    if (!chain || !address) return;
    if (whaleId) return;
    api
      .resolveWhale(chain, address)
      .then((res) => setWhaleId(res.whale_id))
      .catch(() => {});
  }, [chain, address]);

  // Poll backfill/reset status when requested
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;
    const shouldPoll =
      chain === 'hyperliquid' &&
      whaleId &&
      (resetting || (backfillStatus && backfillStatus.status === 'running'));
    if (!shouldPoll) {
      return () => undefined;
    }
    const poll = async () => {
      try {
        const status = await api.getBackfillStatus(whaleId!);
        if (cancelled) return;
        setBackfillStatus(status);
        if (status.status === 'done' || status.status === 'error') {
          setResetting(false);
          setRefreshKey((k) => k + 1);
          return;
        }
      } catch {
        if (cancelled) return;
      }
      timeout = setTimeout(poll, 2000);
    };
    poll();
    return () => {
      cancelled = true;
      if (timeout) clearTimeout(timeout);
    };
  }, [chain, whaleId, resetting, backfillStatus?.status]);

  const handleReset = async () => {
    if (!whaleId || chain !== 'hyperliquid') return;
    setResetError(null);
    setResetting(true);
    try {
      const status = await api.resetHyperliquid(whaleId);
      setBackfillStatus(status);
    } catch (err) {
      setResetError(err instanceof Error ? err.message : 'Failed to start reset');
      setResetting(false);
    }
  };

  const loadMoreTrades = () => {
    if (!chain || !address || !tradesNextCursor || tradesLoading) return;
    const source = tradeSource === 'all' ? undefined : tradeSource;
    const direction = tradeDirection === 'all' ? undefined : tradeDirection;
    setTradesLoading(true);
    api
      .getWalletTrades(chain, address, source, direction, 200, tradesNextCursor)
      .then((res) => {
        setTrades((prev) => [...prev, ...res.items]);
        setTradesNextCursor(res.next_cursor);
      })
      .finally(() => setTradesLoading(false));
  };
  const openTrades = positions;
  const displayedTrades = useMemo(
    () => (groupSimilarTrades ? aggregateTrades(trades) : trades),
    [trades, groupSimilarTrades]
  );

  if (!chain || !address) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">Invalid wallet address</p>
      </div>
    );
  }

  if (!walletDetails) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">Loading wallet details...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Back Link */}
      <Link
        to="/whales"
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Whales
      </Link>

      {/* Wallet Header */}
      <WalletHeader wallet={walletDetails.wallet} />

      {chain === 'hyperliquid' && (
        <div className="card-glass rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Reset & re-import Hyperliquid data</h3>
              <p className="text-xs text-muted-foreground">
                Clears trades, holdings, and metrics for this wallet, then re-imports history. Progress is reported below.
              </p>
            </div>
            <Button
              size="sm"
              onClick={handleReset}
              disabled={!whaleId || resetting}
              variant="outline"
            >
              {resetting ? 'Resetting...' : 'Reset & Re-import'}
            </Button>
          </div>
          {resetError && <p className="text-xs text-destructive">{resetError}</p>}
          {backfillStatus ? (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{backfillStatus.message || backfillStatus.status}</span>
                <span className="font-medium text-foreground">{Math.round(backfillStatus.progress)}%</span>
              </div>
              <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${Math.max(0, Math.min(100, backfillStatus.progress))}%` }}
                />
              </div>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              {whaleId ? 'Progress will appear once a reset starts.' : 'Resolving wallet id...'}
            </p>
          )}
        </div>
      )}

      {/* Metrics Grid */}
      <WalletMetricsGrid metrics={walletDetails.metrics} />

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RoiChart
          data={roiHistory}
          actionSlot={
            <div className="flex items-center gap-2">
              {rangeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setRoiRange(option.value)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    roiRange === option.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-muted'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          }
        />
        <PortfolioChart
          data={portfolioHistory}
          actionSlot={
            <div className="flex items-center gap-2">
              {rangeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setPortfolioRange(option.value)}
                  className={`rounded-md border px-2.5 py-1 text-xs font-medium transition-colors ${
                    portfolioRange === option.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-muted'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          }
        />
      </div>

      {/* Notes */}
      {walletDetails.notes && (
        <div className="card-glass rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
              <MessageSquare className="h-4 w-4 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-foreground mb-1">Behavior Analysis</h3>
              <p className="text-sm text-muted-foreground">{walletDetails.notes}</p>
            </div>
          </div>
        </div>
      )}

      {/* Holdings Table */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <HoldingsTable holdings={walletDetails.holdings} />
        </div>
        <HoldingsDonut holdings={walletDetails.holdings} />
      </div>

      {/* Open Trades */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Open Trades</h2>
        <div className="card-glass rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/30">
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Asset</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Direction</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Size</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Entry</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Mark</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Value</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">Unrealized PnL</th>
                </tr>
              </thead>
              <tbody>
                {openTrades.length === 0 && (
                  <tr>
                    <td className="px-4 py-6 text-center text-sm text-muted-foreground" colSpan={7}>
                      No open trades
                    </td>
                  </tr>
                )}
                {openTrades.map((pos, idx) => (
                  <tr key={`${pos.asset}-${idx}`} className="border-b border-border/50">
                    <td className="px-4 py-3 text-sm text-foreground">{pos.asset}</td>
                    <td className="px-4 py-3">
                      <div className={cn('inline-flex items-center gap-1 text-sm font-medium', pos.direction === 'long' ? 'text-success' : 'text-destructive')}>
                        {pos.direction === 'long' ? 'Long' : 'Short'}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-foreground">{pos.size}</td>
                    <td className="px-4 py-3 text-right text-sm text-foreground">
                      {pos.entry_price_usd != null ? formatUSDExact(pos.entry_price_usd, 2, 8) : <span className="text-muted-foreground/50">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-foreground">
                      {pos.mark_price_usd != null ? formatUSDExact(pos.mark_price_usd, 2, 8) : <span className="text-muted-foreground/50">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right text-sm text-foreground">
                      {pos.value_usd != null ? formatUSDExact(pos.value_usd, 2, 8) : <span className="text-muted-foreground/50">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right text-sm">
                      {pos.unrealized_pnl_usd != null ? (
                        <span className={cn('font-medium', pos.unrealized_pnl_usd >= 0 ? 'text-success' : 'text-destructive')}>
                          {formatUSDExact(pos.unrealized_pnl_usd, 2, 8)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground/50">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Trades Table */}
      <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Trades</h2>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Direction</span>
              <select
                value={tradeDirection}
                onChange={(e) => setTradeDirection(e.target.value as typeof tradeDirection)}
                className="h-9 rounded-md border border-border bg-background px-2 text-xs"
              >
                <option value="all">All</option>
                <option value="long">Long</option>
                <option value="short">Short</option>
                <option value="close_long">Close Long</option>
                <option value="close_short">Close Short</option>
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
                <option value="deposit">Deposit</option>
                <option value="withdraw">Withdraw</option>
              </select>
            </div>
            <Tabs value={tradeSource} onValueChange={(value) => setTradeSource(value as typeof tradeSource)}>
              <TabsList>
                {tradeTabs.map((tab) => (
                  <TabsTrigger key={tab.value} value={tab.value} className="text-xs sm:text-sm">
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
            <Button
              variant={groupSimilarTrades ? 'default' : 'outline'}
              size="sm"
              onClick={() => setGroupSimilarTrades((prev) => !prev)}
              className="w-full sm:w-auto"
            >
              {groupSimilarTrades ? 'Ungroup partial fills' : 'Group partial fills'}
            </Button>
          </div>
        </div>
        <TradesTable trades={displayedTrades} groupingEnabled={groupSimilarTrades} />
        <div className="flex justify-center">
          {tradesNextCursor ? (
            <Button variant="outline" size="sm" onClick={loadMoreTrades} disabled={tradesLoading}>
              {tradesLoading ? 'Loading…' : 'Load more trades'}
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">No more trades</p>
          )}
        </div>
      </div>
    </div>
  );
}
