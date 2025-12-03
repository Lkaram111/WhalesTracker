import { useNavigate } from 'react-router-dom';
import { ChainBadge } from '@/components/common/ChainBadge';
import { TypeBadge } from '@/components/common/TypeBadge';
import { AddressDisplay } from '@/components/common/AddressDisplay';
import { formatUSD, formatPercent, formatTimeAgo } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { WhaleSummary } from '@/types/api';

interface WhaleTableProps {
  whales: WhaleSummary[];
  loading?: boolean;
  compact?: boolean;
}

export function WhaleTable({ whales, loading, compact = false }: WhaleTableProps) {
  const navigate = useNavigate();

  const handleRowClick = (whale: WhaleSummary) => {
    navigate(`/whales/${whale.chain}/${whale.address}`);
  };

  return (
    <div className="card-glass rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Address
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Chain
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Type
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                ROI
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Realized PnL
              </th>
              {!compact && (
                <>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    30d Volume
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Win Rate
                  </th>
                </>
              )}
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Last Active
              </th>
            </tr>
          </thead>
          <tbody>
            {whales.map((whale, index) => (
              <tr
                key={`${whale.chain}-${whale.address}`}
                onClick={() => handleRowClick(whale)}
                className={cn(
                  'border-b border-border/50 cursor-pointer transition-colors hover:bg-muted/30',
                  index % 2 === 0 ? 'bg-transparent' : 'bg-muted/10'
                )}
              >
                <td className="px-4 py-3">
                  <AddressDisplay 
                    address={whale.address} 
                    chain={whale.chain}
                    showCopy={false}
                    showExternalLink={false}
                  />
                </td>
                <td className="px-4 py-3">
                  <ChainBadge chain={whale.chain} />
                </td>
                <td className="px-4 py-3">
                  <TypeBadge type={whale.type} />
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={cn(
                    'font-medium',
                    whale.roi_percent >= 0 ? 'text-success' : 'text-destructive'
                  )}>
                    {formatPercent(whale.roi_percent)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={cn(
                    'font-medium',
                    whale.realized_pnl_usd >= 0 ? 'text-success' : 'text-destructive'
                  )}>
                    {formatUSD(whale.realized_pnl_usd)}
                  </span>
                </td>
                {!compact && (
                  <>
                    <td className="px-4 py-3 text-right text-muted-foreground">
                      {formatUSD(whale.volume_30d_usd)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {whale.win_rate_percent !== null ? (
                        <span className="text-muted-foreground">
                          {whale.win_rate_percent.toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-muted-foreground/50">—</span>
                      )}
                    </td>
                  </>
                )}
                <td className="px-4 py-3 text-right text-muted-foreground text-sm">
                  {formatTimeAgo(whale.last_active_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
