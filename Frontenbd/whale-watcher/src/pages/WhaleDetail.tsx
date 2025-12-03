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
import type { ChainId, Trade, WalletDetails, OpenPosition } from '@/types/api';
import { api } from '@/lib/apiClient';
import { formatUSDExact } from '@/lib/formatters';
import { Button } from '@/components/ui/button';

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
    api.getWalletDetails(chain, address).then(setWalletDetails).catch(() => setWalletDetails(null));
  }, [chain, address]);

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
  }, [chain, address, tradeSource, tradeDirection]);

  useEffect(() => {
    if (!chain || !address) return;
    api.getWalletPositions(chain, address)
      .then((res) => setPositions(res.items))
      .catch(() => setPositions([]));
  }, [chain, address]);

  useEffect(() => {
    if (!chain || !address) return;
    api.getWalletRoiHistory(chain, address, roiRange).then((res) => setRoiHistory(res.points)).catch(() => setRoiHistory([]));
  }, [chain, address, roiRange]);

  useEffect(() => {
    if (!chain || !address) return;
    api
      .getWalletPortfolioHistory(chain, address, portfolioRange)
      .then((res) => setPortfolioHistory(res.points))
      .catch(() => setPortfolioHistory([]));
  }, [chain, address, portfolioRange]);

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
          </div>
        </div>
        <TradesTable trades={trades} />
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
