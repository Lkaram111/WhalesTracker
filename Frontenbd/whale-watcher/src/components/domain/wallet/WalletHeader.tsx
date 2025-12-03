import { ChainBadge } from '@/components/common/ChainBadge';
import { TypeBadge } from '@/components/common/TypeBadge';
import { AddressDisplay } from '@/components/common/AddressDisplay';
import { useFiltersStore } from '@/stores/filtersStore';
import { Star, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { WalletDetails } from '@/types/api';

interface WalletHeaderProps {
  wallet: WalletDetails['wallet'];
}

export function WalletHeader({ wallet }: WalletHeaderProps) {
  const { isInWatchlist, addToWatchlist, removeFromWatchlist } = useFiltersStore();
  const inWatchlist = isInWatchlist(wallet.address, wallet.chain);

  const toggleWatchlist = () => {
    if (inWatchlist) {
      removeFromWatchlist(wallet.address, wallet.chain);
    } else {
      addToWatchlist(wallet.address, wallet.chain);
    }
  };

  return (
    <div className="card-glass rounded-xl p-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <AddressDisplay 
              address={wallet.address} 
              chain={wallet.chain}
              truncate={false}
              className="text-lg"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <ChainBadge chain={wallet.chain} size="md" />
            <TypeBadge type={wallet.type} size="md" />
            {wallet.labels.map((label) => (
              <span 
                key={label}
                className="inline-flex items-center rounded-md border border-border bg-muted/50 px-2.5 py-1 text-sm text-muted-foreground"
              >
                {label.replace('_', ' ')}
              </span>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={toggleWatchlist}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all',
              inWatchlist 
                ? 'border-warning bg-warning/10 text-warning' 
                : 'border-border hover:border-warning hover:bg-warning/10 text-muted-foreground hover:text-warning'
            )}
          >
            <Star className={cn('h-4 w-4', inWatchlist && 'fill-current')} />
            {inWatchlist ? 'Watching' : 'Add to Watchlist'}
          </button>
          <a
            href={wallet.external_explorer_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-all"
          >
            <ExternalLink className="h-4 w-4" />
            Explorer
          </a>
        </div>
      </div>
    </div>
  );
}
