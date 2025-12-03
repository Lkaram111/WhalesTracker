import { useNavigate } from 'react-router-dom';
import { ChainBadge } from '@/components/common/ChainBadge';
import { formatUSD, formatTimeAgo, getEventTypeIcon } from '@/lib/formatters';
import { cn } from '@/lib/utils';
import type { LiveEvent } from '@/types/api';
import { ExternalLink } from 'lucide-react';

interface LiveEventItemProps {
  event: LiveEvent;
  isNew?: boolean;
}

export function LiveEventItem({ event, isNew = false }: LiveEventItemProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/whales/${event.wallet.chain}/${event.wallet.address}`);
  };

  return (
    <div
      onClick={handleClick}
      className={cn(
        'card-glass rounded-lg p-4 cursor-pointer transition-all duration-300 hover:border-primary/30',
        isNew && 'animate-flash'
      )}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-xl">
            {getEventTypeIcon(event.type)}
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-foreground">{event.summary}</p>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <ChainBadge chain={event.chain} size="sm" />
              {event.wallet.label && (
                <span className="text-primary">{event.wallet.label}</span>
              )}
              <span>•</span>
              <span>{formatTimeAgo(event.timestamp)}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn(
            'text-lg font-bold',
            event.value_usd >= 1000000 ? 'text-success' : 'text-foreground'
          )}>
            {formatUSD(event.value_usd)}
          </span>
          {event.tx_hash && (
            <a
              href={`#`}
              onClick={(e) => e.stopPropagation()}
              className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-muted transition-colors"
            >
              <ExternalLink className="h-4 w-4 text-muted-foreground" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
