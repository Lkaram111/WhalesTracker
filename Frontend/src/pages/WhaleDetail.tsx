import { useEffect, useMemo, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { WalletHeader } from '@/components/domain/wallet/WalletHeader';
import { WalletMetricsGrid } from '@/components/domain/wallet/WalletMetricsGrid';
import { HoldingsTable } from '@/components/domain/wallet/HoldingsTable';
import { HoldingsDonut } from '@/components/domain/wallet/HoldingsDonut';
import { TradesTable } from '@/components/domain/wallet/TradesTable';
import { RoiChart } from '@/components/domain/charts/RoiChart';
import { PortfolioChart } from '@/components/domain/charts/PortfolioChart';
import { MetricCard } from '@/components/common/MetricCard';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, MessageSquare } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { BackfillStatus, ChainId, Trade, WalletDetails, OpenPosition } from '@/types/api';
import { api } from '@/lib/apiClient';
import { formatUSD, formatUSDExact } from '@/lib/formatters';
import { Button } from '@/components/ui/button';
import { aggregateTrades } from '@/lib/tradeGrouping';
import { MY_HYPERLIQUID_ADDRESS } from '@/config';

interface WhaleDetailProps {
  chainOverride?: ChainId;
  addressOverride?: string;
  hideBackLink?: boolean;
}

export default function WhaleDetail({
  chainOverride,
  addressOverride,
  hideBackLink = false,
}: WhaleDetailProps) {
  const params = useParams<{ chain: ChainId; address: string }>();
  const chain = chainOverride ?? params.chain;
  const address = addressOverride ?? params.address;
  const [roiRange, setRoiRange] = useState(30);
  const [portfolioRange, setPortfolioRange] = useState(30);
  const [tradeSource, setTradeSource] = useState<Trade['source'] | 'all'>('all');
  const [tradeDirection, setTradeDirection] = useState<Trade['direction'] | 'all'>('all');
  const [tradesTimeFilter, setTradesTimeFilter] = useState<'all' | '24h' | '7d'>('all');

  const [walletDetails, setWalletDetails] = useState<WalletDetails | null>(null);
  const [walletError, setWalletError] = useState<string | null>(null);
  const [autoCreateAttempted, setAutoCreateAttempted] = useState(false);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [tradesNextCursor, setTradesNextCursor] = useState<string | null>(null);
  const [tradesTotal, setTradesTotal] = useState<number | null>(null);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [positions, setPositions] = useState<OpenPosition[]>([]);
  const [roiHistory, setRoiHistory] = useState<{ timestamp: string; roi_percent: number }[]>([]);
  const [portfolioHistory, setPortfolioHistory] = useState<{ timestamp: string; value_usd: number }[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [tradesError, setTradesError] = useState<string | null>(null);

  const [whaleId, setWhaleId] = useState<string | null>(null);
  const [backfillStatus, setBackfillStatus] = useState<BackfillStatus | null>(null);
  const [resetting, setResetting] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [groupSimilarTrades, setGroupSimilarTrades] = useState(false);
  const [backfillPending, setBackfillPending] = useState(false);
  const [backfillError, setBackfillError] = useState<string | null>(null);
  const [paidImportStart, setPaidImportStart] = useState<string>('');
  const [paidImportEnd, setPaidImportEnd] = useState<string>('');
  const [paidImportStatus, setPaidImportStatus] = useState<string | null>(null);
  const [paidImportIsError, setPaidImportIsError] = useState(false);
  const [paidImportLoading, setPaidImportLoading] = useState(false);

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
  const tradeTimeFilters: { value: 'all' | '24h' | '7d'; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: '24h', label: '24h' },
    { value: '7d', label: '7d' },
  ];
  const isMyHyperliquidWallet =
    chain === 'hyperliquid' &&
    !!MY_HYPERLIQUID_ADDRESS &&
    address?.toLowerCase() === MY_HYPERLIQUID_ADDRESS.toLowerCase();

  useEffect(() => {
    setAutoCreateAttempted(false);
  }, [chain, address]);

  useEffect(() => {
    if (!chain || !address) return;
    setWalletError(null);
    api
      .getWalletDetails(chain, address)
      .then((data) => {
        setWalletDetails(data);
        if (data.wallet?.id) {
          setWhaleId(data.wallet.id);
        }
      })
      .catch(async (err: unknown) => {
        const status = (err as { status?: number })?.status;
        if (
          status === 404 &&
          isMyHyperliquidWallet &&
          !autoCreateAttempted
        ) {
          setAutoCreateAttempted(true);
          setWalletError('Tracking your Hyperliquid wallet now—fetching data...');
          try {
            await api.createWhale({ chain, address, type: 'trader' });
            setRefreshKey((k) => k + 1);
            return;
          } catch (createErr) {
            const createMessage =
              createErr instanceof Error
                ? createErr.message
                : 'Failed to add your Hyperliquid wallet automatically.';
            setWalletError(createMessage);
            setWalletDetails(null);
            return;
          }
        }

        const notFoundMessage =
          status === 404
            ? chain === 'hyperliquid'
              ? 'Wallet not found. Make sure your Hyperliquid address is added as a tracked whale in the Settings / Whales page.'
              : 'Wallet not found.'
            : null;
        const message =
          notFoundMessage ||
          (err instanceof Error ? err.message : 'Failed to load wallet details.');
        setWalletError(message);
        setWalletDetails(null);
      });
  }, [chain, address, refreshKey, isMyHyperliquidWallet, autoCreateAttempted]);

  useEffect(() => {
    if (!chain || !address) return;
    const source = tradeSource === 'all' ? undefined : tradeSource;
    const direction = tradeDirection === 'all' ? undefined : tradeDirection;
    setTradesLoading(true);
    setTradesError(null);
    api.getWalletTrades(chain, address, source, direction, 200)
      .then((res) => {
        setTrades(res.items);
        setTradesNextCursor(res.next_cursor);
        setTradesTotal(res.total ?? null);
        setLastRefreshed(new Date());
      })
      .catch(() => {
        setTrades([]);
        setTradesNextCursor(null);
        setTradesTotal(null);
        setTradesError('Failed to load trades. Please refresh.');
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
        setTradesTotal(res.total ?? tradesTotal);
      })
      .finally(() => setTradesLoading(false));
  };
  const { roi24hChange, portfolio24hChangeUsd, portfolio24hChangePct } = useMemo(() => {
    const roiChange =
      roiHistory.length >= 2
        ? roiHistory[roiHistory.length - 1].roi_percent - roiHistory[roiHistory.length - 2].roi_percent
        : null;

    let valueChange: number | null = null;
    let pctChange: number | null = null;
    if (portfolioHistory.length >= 2) {
      const latest = portfolioHistory[portfolioHistory.length - 1].value_usd;
      const previous = portfolioHistory[portfolioHistory.length - 2].value_usd;
      valueChange = latest - previous;
      if (previous > 0) {
        pctChange = (valueChange / previous) * 100;
      }
    }

    return {
      roi24hChange: roiChange,
      portfolio24hChangeUsd: valueChange,
      portfolio24hChangePct: pctChange,
    };
  }, [roiHistory, portfolioHistory]);

  const openTrades = positions;
  const filteredTrades = useMemo(() => {
    if (tradesTimeFilter === 'all') return trades;
    const windowMs = tradesTimeFilter === '24h' ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000;
    const cutoff = Date.now() - windowMs;
    return trades.filter((trade) => new Date(trade.timestamp).getTime() >= cutoff);
  }, [trades, tradesTimeFilter]);

  const displayedTrades = useMemo(
    () => (groupSimilarTrades ? aggregateTrades(filteredTrades) : filteredTrades),
    [filteredTrades, groupSimilarTrades]
  );

  // Auto-refresh trades/positions/backfill every 30s
  useEffect(() => {
    if (!chain || !address) return;
    const id = setInterval(() => setRefreshKey((k) => k + 1), 30000);
    return () => clearInterval(id);
  }, [chain, address]);

  const handleManualRefresh = () => {
    setRefreshKey((k) => k + 1);
  };

  const handleBackfill = async () => {
    if (!whaleId) return;
    setBackfillError(null);
    setBackfillPending(true);
    try {
      const status = await api.backfillWhale(whaleId);
      setBackfillStatus(status);
    } catch (err) {
      setBackfillError(err instanceof Error ? err.message : 'Failed to start backfill');
      setBackfillPending(false);
    }
  };

  if (!chain || !address) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">Invalid wallet address</p>
      </div>
    );
  }

  if (walletError) {
    return (
      <div className="flex items-center justify-center min-h-[400px] text-center">
        <p className="max-w-2xl text-sm text-muted-foreground">{walletError}</p>
      </div>
    );
  }

  if (!walletDetails) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <p className="text-muted-foreground">
          {walletError || 'Loading wallet details...'}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      {!hideBackLink && (
        <Link
          to="/whales"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Whales
        </Link>
      )}

      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="text-xs text-muted-foreground">
          Last refreshed: {lastRefreshed ? lastRefreshed.toLocaleTimeString() : 'n/a'}
        </div>
        <Button variant="outline" size="sm" onClick={handleManualRefresh} disabled={tradesLoading}>
          {tradesLoading ? 'Refreshing…' : 'Refresh data'}
        </Button>
      </div>

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
          <div className="border-t border-border pt-3 mt-2 space-y-2">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h4 className="text-xs font-semibold text-foreground">Fetch historical paid data (Hyperliquid S3)</h4>
                <p className="text-xs text-muted-foreground">
                  Downloads from requester-pays S3; set start/end dates and ingest past fills.
                </p>
              </div>
              <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
                <input
                  type="date"
                  value={paidImportStart}
                  onChange={(e) => setPaidImportStart(e.target.value)}
                  className="h-9 rounded-md border border-border bg-background px-2 text-xs"
                />
                <input
                  type="date"
                  value={paidImportEnd}
                  onChange={(e) => setPaidImportEnd(e.target.value)}
                  className="h-9 rounded-md border border-border bg-background px-2 text-xs"
                />
                <Button
                  size="sm"
                  onClick={async () => {
                    if (!paidImportStart || !paidImportEnd) return;
                    setPaidImportLoading(true);
                    setPaidImportStatus(null);
                    setPaidImportIsError(false);
                    try {
                      const res = await api.importHyperliquidPaidHistory(
                        chain,
                        address,
                        new Date(paidImportStart).toISOString(),
                        new Date(paidImportEnd).toISOString()
                      );
                      setPaidImportStatus(`Imported ${res.imported} fills, skipped ${res.skipped}.`);
                      setPaidImportIsError(false);
                      setRefreshKey((k) => k + 1);
                    } catch (err) {
                      const rawMessage = err instanceof Error ? err.message : 'Import failed';
                      const normalizedMessage =
                        rawMessage.toLowerCase().includes('aws login') || (err as { status?: number })?.status === 401
                          ? 'AWS login required. Run `aws login` locally, then retry the Hyperliquid import.'
                          : rawMessage;
                      setPaidImportStatus(normalizedMessage);
                      setPaidImportIsError(true);
                    } finally {
                      setPaidImportLoading(false);
                    }
                  }}
                  disabled={!paidImportStart || !paidImportEnd || paidImportLoading}
                >
                  {paidImportLoading ? 'Fetching…' : 'Fetch historical paid data'}
                </Button>
              </div>
            </div>
            {paidImportStatus && (
              <p className={`text-xs ${paidImportIsError ? 'text-destructive' : 'text-muted-foreground'}`}>
                {paidImportStatus}
              </p>
            )}
          </div>
        </div>
      )}
      {chain !== 'hyperliquid' && (
        <div className="card-glass rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-foreground">Recompute & backfill history</h3>
              <p className="text-xs text-muted-foreground">
                Refreshes trades, holdings, and metrics for this wallet without wiping data.
              </p>
            </div>
            <Button
              size="sm"
              onClick={handleBackfill}
              disabled={!whaleId || backfillPending}
              variant="outline"
            >
              {backfillPending ? 'Running…' : 'Recompute'}
            </Button>
          </div>
          {backfillError && <p className="text-xs text-destructive">{backfillError}</p>}
          {backfillStatus && backfillStatus.status !== 'idle' && (
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
          )}
        </div>
      )}

      {/* Metrics Grid */}
      <WalletMetricsGrid metrics={walletDetails.metrics} />

      {(roi24hChange !== null || portfolio24hChangeUsd !== null || portfolio24hChangePct !== null) && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-4">
          {portfolio24hChangeUsd !== null && (
            <MetricCard
              title="24h PnL"
              value={formatUSD(portfolio24hChangeUsd)}
              changeType={portfolio24hChangeUsd >= 0 ? 'positive' : 'negative'}
            />
          )}
          {portfolio24hChangePct !== null && (
            <MetricCard
              title="24h Growth"
              value={`${portfolio24hChangePct.toFixed(2)}%`}
              changeType={portfolio24hChangePct >= 0 ? 'positive' : 'negative'}
            />
          )}
          {roi24hChange !== null && (
            <MetricCard
              title="24h ROI Change"
              value={`${roi24hChange.toFixed(2)}%`}
              changeType={roi24hChange >= 0 ? 'positive' : 'negative'}
            />
          )}
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-3">
          {roiHistory.length < 2 ? (
            <div className="card-glass rounded-xl p-6 text-sm text-muted-foreground">No ROI data yet.</div>
          ) : (
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
          )}
        </div>
        <div className="space-y-3">
          {portfolioHistory.length < 2 ? (
            <div className="card-glass rounded-xl p-6 text-sm text-muted-foreground">No portfolio history yet.</div>
          ) : (
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
          )}
        </div>
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
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-foreground">Trades</h2>
            {tradesTotal !== null && (
              <span className="text-xs text-muted-foreground">
                {tradesTotal.toLocaleString()} historical trades
              </span>
            )}
          </div>
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2">
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Direction</span>
              <select
                value={tradeDirection}
                onChange={(e) => setTradeDirection(e.target.value as typeof tradeDirection)}
                className="h-9 rounded-md border border-border bg-background px-2 text-xs"
                aria-label="Direction filter"
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
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Time</span>
              <select
                value={tradesTimeFilter}
                onChange={(e) => setTradesTimeFilter(e.target.value as typeof tradesTimeFilter)}
                className="h-9 rounded-md border border-border bg-background px-2 text-xs"
                aria-label="Time filter"
              >
                {tradeTimeFilters.map((filter) => (
                  <option key={filter.value} value={filter.value}>
                    {filter.label}
                  </option>
                ))}
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
        {tradesError && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {tradesError}
          </div>
        )}
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
