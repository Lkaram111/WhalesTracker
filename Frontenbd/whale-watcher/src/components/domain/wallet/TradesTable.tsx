import { formatUSD, formatUSDExact, formatDate, formatPercent } from '@/lib/formatters';
import { ChainBadge } from '@/components/common/ChainBadge';
import { ExternalLink, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Trade } from '@/types/api';

interface TradesTableProps {
  trades: Trade[];
  title?: string;
  emptyMessage?: string;
}

const directionConfig: Record<string, { label: string; color: string; icon: typeof ArrowUpRight }> = {
  buy: { label: 'Buy', color: 'text-success', icon: ArrowUpRight },
  sell: { label: 'Sell', color: 'text-destructive', icon: ArrowDownRight },
  long: { label: 'Long', color: 'text-success', icon: ArrowUpRight },
  short: { label: 'Short', color: 'text-destructive', icon: ArrowDownRight },
  close_long: { label: 'Close Long', color: 'text-muted-foreground', icon: ArrowDownRight },
  close_short: { label: 'Close Short', color: 'text-muted-foreground', icon: ArrowUpRight },
  deposit: { label: 'Deposit', color: 'text-primary', icon: ArrowDownRight },
  withdraw: { label: 'Withdraw', color: 'text-warning', icon: ArrowUpRight },
};

export function TradesTable({ trades, title = 'Recent Trades', emptyMessage }: TradesTableProps) {
  return (
    <div className="card-glass rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border">
        <h3 className="text-sm font-medium text-foreground">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Time
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Platform
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Direction
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Assets
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Open Price
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Close Price
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Value
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                PnL
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Tx
              </th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 && (
              <tr>
                <td className="px-4 py-6 text-center text-sm text-muted-foreground" colSpan={9}>
                  {emptyMessage || 'No trades to display'}
                </td>
              </tr>
            )}
            {trades.map((trade) => {
              const config = directionConfig[trade.direction] || directionConfig.buy;
              const Icon = config.icon;
              
              return (
                <tr 
                  key={trade.id}
                  className="border-b border-border/50"
                >
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatDate(trade.timestamp)}
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-foreground">{trade.platform}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className={cn('flex items-center gap-1', config.color)}>
                      <Icon className="h-4 w-4" />
                      <span className="text-sm font-medium">{config.label}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-sm text-foreground">
                      {trade.base_asset}
                      {trade.quote_asset && ` → ${trade.quote_asset}`}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-foreground">
                    {trade.open_price_usd != null ? (
                      formatUSDExact(trade.open_price_usd, 2, 8)
                    ) : (
                      <span className="text-muted-foreground/50">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-foreground">
                    {trade.close_price_usd != null ? (
                      formatUSDExact(trade.close_price_usd, 2, 8)
                    ) : (
                      <span className="text-muted-foreground/50">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-foreground">
                    {formatUSD(trade.value_usd)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {trade.pnl_usd !== null ? (
                      <div className={cn(
                        'font-medium',
                        trade.pnl_usd >= 0 ? 'text-success' : 'text-destructive'
                      )}>
                        <span>{formatUSD(trade.pnl_usd)}</span>
                        {trade.pnl_percent !== null && (
                          <span className="text-xs ml-1">
                            ({formatPercent(trade.pnl_percent)})
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground/50">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {trade.external_url ? (
                      <a
                        href={trade.external_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex h-8 w-8 items-center justify-center rounded hover:bg-muted transition-colors"
                      >
                        <ExternalLink className="h-4 w-4 text-muted-foreground" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground/50">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
