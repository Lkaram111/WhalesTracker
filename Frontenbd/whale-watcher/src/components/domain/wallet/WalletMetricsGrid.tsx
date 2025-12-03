import { MetricCard } from '@/components/common/MetricCard';
import { formatUSD, formatPercent } from '@/lib/formatters';
import { TrendingUp, DollarSign, Target, Activity, BarChart3, Trophy } from 'lucide-react';
import type { WalletDetails } from '@/types/api';

interface WalletMetricsGridProps {
  metrics: WalletDetails['metrics'];
}

export function WalletMetricsGrid({ metrics }: WalletMetricsGridProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
      <MetricCard
        title="Overall ROI"
        value={formatPercent(metrics.roi_percent)}
        changeType={metrics.roi_percent >= 0 ? 'positive' : 'negative'}
        icon={TrendingUp}
      />
      <MetricCard
        title="Realized PnL"
        value={formatUSD(metrics.realized_pnl_usd)}
        changeType={metrics.realized_pnl_usd >= 0 ? 'positive' : 'negative'}
        icon={DollarSign}
      />
      <MetricCard
        title="Unrealized PnL"
        value={metrics.unrealized_pnl_usd !== null ? formatUSD(metrics.unrealized_pnl_usd) : '—'}
        changeType={metrics.unrealized_pnl_usd !== null && metrics.unrealized_pnl_usd >= 0 ? 'positive' : 'negative'}
        icon={Target}
      />
      <MetricCard
        title="Portfolio Value"
        value={formatUSD(metrics.portfolio_value_usd)}
        icon={BarChart3}
      />
      <MetricCard
        title="30d Volume"
        value={formatUSD(metrics.volume_30d_usd)}
        icon={Activity}
      />
      <MetricCard
        title="Win Rate"
        value={metrics.win_rate_percent !== null ? `${metrics.win_rate_percent.toFixed(1)}%` : '—'}
        changeType={metrics.win_rate_percent !== null && metrics.win_rate_percent >= 50 ? 'positive' : 'neutral'}
        icon={Trophy}
      />
    </div>
  );
}
