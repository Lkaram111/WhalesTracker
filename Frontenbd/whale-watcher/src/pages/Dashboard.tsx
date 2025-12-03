import { useEffect, useState } from 'react';
import { MetricCard } from '@/components/common/MetricCard';
import { WhaleTable } from '@/components/domain/whales/WhaleTable';
import { LiveEventList } from '@/components/domain/live/LiveEventList';
import { PortfolioChart } from '@/components/domain/charts/PortfolioChart';
import { formatUSD, formatNumber } from '@/lib/formatters';
import { api } from '@/lib/apiClient';
import type { DashboardSummary, LiveEvent, PortfolioPoint, WhaleSummary } from '@/types/api';
import { Users, Activity, DollarSign, Zap } from 'lucide-react';

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [topWhales, setTopWhales] = useState<WhaleSummary[]>([]);
  const [recentEvents, setRecentEvents] = useState<LiveEvent[]>([]);
  const [portfolioHistory, setPortfolioHistory] = useState<PortfolioPoint[]>([]);

  useEffect(() => {
    api.getDashboardSummary().then(setSummary).catch(() => setSummary(null));
    api.getTopWhales(8).then((res) => setTopWhales(res.items)).catch(() => setTopWhales([]));
    api.getRecentEvents(5).then((res) => setRecentEvents(res.items)).catch(() => setRecentEvents([]));
    setPortfolioHistory([]); // backend not providing this yet
  }, []);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <p className="text-muted-foreground">Real-time whale activity and market overview</p>
      </div>

      {/* Summary Metrics */}
      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            title="Total Tracked Whales"
            value={formatNumber(summary.total_tracked_whales)}
            change=""
            changeType="neutral"
            icon={Users}
          />
          <MetricCard
            title="Active Whales (24h)"
            value={formatNumber(summary.active_whales_24h)}
            change=""
            changeType="neutral"
            icon={Activity}
          />
          <MetricCard
            title="24h Volume"
            value={formatUSD(summary.total_volume_24h_usd)}
            change=""
            changeType="neutral"
            icon={DollarSign}
          />
          <MetricCard
            title="Hyperliquid Whales"
            value={formatNumber(summary.hyperliquid_whales)}
            change=""
            changeType="neutral"
            icon={Zap}
          />
        </div>
      )}

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Top Whales Table - Takes 2 columns */}
        <div className="xl:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Top Performing Whales</h2>
            <a href="/whales" className="text-sm text-primary hover:underline">
              View all →
            </a>
          </div>
          <WhaleTable whales={topWhales} compact />
        </div>

        {/* Recent Events - Takes 1 column */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-foreground">Recent Activity</h2>
            <a href="/live" className="text-sm text-primary hover:underline">
              Live feed →
            </a>
          </div>
          <LiveEventList events={recentEvents} />
        </div>
      </div>

      {/* Portfolio Chart */}
      {portfolioHistory.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-foreground mb-4">Top Whale Portfolio Trend (30d)</h2>
          <PortfolioChart data={portfolioHistory} height={350} />
        </div>
      )}
    </div>
  );
}
