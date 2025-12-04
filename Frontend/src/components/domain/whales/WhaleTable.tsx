import { useNavigate } from 'react-router-dom';
import { ChainBadge } from '@/components/common/ChainBadge';
import { TypeBadge } from '@/components/common/TypeBadge';
import { AddressDisplay } from '@/components/common/AddressDisplay';
import { formatUSD, formatPercent, formatTimeAgo } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { WhaleSummary } from '@/types/api';
import { Badge } from '@/components/ui/badge';
import { Pencil, Tag as TagIcon, Trash2 } from 'lucide-react';

interface WhaleTableProps {
  whales: WhaleSummary[];
  loading?: boolean;
  compact?: boolean;
  sortBy?: string;
  sortDir?: 'asc' | 'desc';
  onSort?: (field: string) => void;
  showActions?: boolean;
  onEditTags?: (whale: WhaleSummary) => void;
  onDeleteWhale?: (whale: WhaleSummary) => void;
}

export function WhaleTable({
  whales,
  loading,
  compact = false,
  sortBy,
  sortDir,
  onSort,
  showActions = false,
  onEditTags,
  onDeleteWhale,
}: WhaleTableProps) {
  const navigate = useNavigate();

  const handleRowClick = (whale: WhaleSummary) => {
    navigate(`/whales/${whale.chain}/${whale.address}`);
  };

  const renderHeader = (label: string, field?: string, align: 'left' | 'right' = 'left') => {
    const isActive = field && sortBy === field;
    return (
      <th
        className={cn(
          'px-4 py-3 text-xs font-medium uppercase tracking-wider',
          align === 'right' ? 'text-right' : 'text-left',
          field && onSort ? 'cursor-pointer select-none' : '',
          'text-muted-foreground'
        )}
        onClick={() => field && onSort && onSort(field)}
      >
        <span className="inline-flex items-center gap-1">
          {label}
          {isActive && sortDir && (
            <span className="text-[10px]">{sortDir === 'asc' ? '↑' : '↓'}</span>
          )}
        </span>
      </th>
    );
  };

  return (
    <div className="card-glass rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/30">
              {renderHeader('Address', 'address')}
              {renderHeader('Chain', 'chain')}
          {renderHeader('Type', 'type')}
          {renderHeader('ROI', 'roi', 'right')}
          {renderHeader('Realized PnL', 'realized_pnl_usd', 'right')}
          {renderHeader('Tag')}
          {!compact && (
            <>
              {renderHeader('30d Volume', 'volume_30d_usd', 'right')}
              {renderHeader('Win Rate', 'win_rate_percent', 'right')}
            </>
          )}
          {renderHeader('Last Active', 'last_active_at', 'right')}
          {showActions && renderHeader('Actions')}
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
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <TagIcon className="h-3.5 w-3.5 text-muted-foreground" />
                    {whale.labels && whale.labels.length > 0 ? (
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-xs px-2 py-0.5">
                          {whale.labels[0]}
                        </Badge>
                        {whale.labels.length > 1 && (
                          <span className="text-[11px] text-muted-foreground">
                            +{whale.labels.length - 1} more
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">—</span>
                    )}
                  </div>
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
                {showActions && (
                  <td className="px-4 py-3 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onEditTags?.(whale);
                        }}
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-semibold text-foreground transition-colors hover:bg-muted"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        Edit tag
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onDeleteWhale?.(whale);
                        }}
                        className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs font-semibold text-destructive transition-colors hover:bg-destructive/10"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Delete
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
