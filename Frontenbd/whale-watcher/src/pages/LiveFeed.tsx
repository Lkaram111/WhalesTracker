import { useEffect, useMemo, useState } from 'react';
import { LiveEventList } from '@/components/domain/live/LiveEventList';
import { ChainBadge } from '@/components/common/ChainBadge';
import { useUIStore } from '@/stores/uiStore';
import { useFiltersStore } from '@/stores/filtersStore';
import { formatUSD } from '@/lib/formatters';
import { Pause, Play, Radio, SlidersHorizontal } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChainId, LiveEvent } from '@/types/api';
import { api } from '@/lib/apiClient';

const chains: ChainId[] = ['ethereum', 'bitcoin', 'hyperliquid'];
const eventTypes = [
  { value: null, label: 'All Events' },
  { value: 'large_swap', label: 'Large Swaps' },
  { value: 'large_transfer', label: 'Transfers' },
  { value: 'exchange_flow', label: 'Exchange Flows' },
  { value: 'perp_trade', label: 'Perp Trades' },
];

export default function LiveFeed() {
  const { liveFeedPaused, setLiveFeedPaused } = useUIStore();
  const { selectedChains, toggleChain, liveFeedMinValue, setLiveFeedMinValue } = useFiltersStore();
  
  const [selectedEventType, setSelectedEventType] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [events, setEvents] = useState<LiveEvent[]>([]);

  useEffect(() => {
    api.getLiveEvents(50).then((res) => setEvents(res.items)).catch(() => setEvents([]));
  }, []);

  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      // Chain filter
      if (!selectedChains.includes(event.chain)) return false;
      
      // Event type filter
      if (selectedEventType && event.type !== selectedEventType) return false;
      
      // Min value filter
      if (event.value_usd < liveFeedMinValue) return false;
      
      return true;
    });
  }, [events, selectedChains, selectedEventType, liveFeedMinValue]);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-foreground">Live Feed</h1>
            <div className={cn(
              'flex items-center gap-2 rounded-full px-3 py-1.5',
              liveFeedPaused ? 'bg-muted' : 'bg-success/10'
            )}>
              <div className={cn(
                'h-2 w-2 rounded-full',
                liveFeedPaused ? 'bg-muted-foreground' : 'bg-success animate-pulse'
              )} />
              <span className={cn(
                'text-xs font-medium',
                liveFeedPaused ? 'text-muted-foreground' : 'text-success'
              )}>
                {liveFeedPaused ? 'Paused' : 'Live'}
              </span>
            </div>
          </div>
          <p className="text-muted-foreground">Real-time whale activity and transactions</p>
        </div>
        
        <button
          onClick={() => setLiveFeedPaused(!liveFeedPaused)}
          className={cn(
            'flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all',
            liveFeedPaused
              ? 'border-success bg-success/10 text-success hover:bg-success/20'
              : 'border-warning bg-warning/10 text-warning hover:bg-warning/20'
          )}
        >
          {liveFeedPaused ? (
            <>
              <Play className="h-4 w-4" />
              Resume
            </>
          ) : (
            <>
              <Pause className="h-4 w-4" />
              Pause
            </>
          )}
        </button>
      </div>

      {/* Filters Bar */}
      <div className="card-glass rounded-xl p-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Chain Filters */}
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">Chains:</span>
            <div className="flex items-center gap-2">
              {chains.map((chain) => (
                <button
                  key={chain}
                  onClick={() => toggleChain(chain)}
                  className={cn(
                    'transition-all',
                    selectedChains.includes(chain) ? 'opacity-100' : 'opacity-40 hover:opacity-70'
                  )}
                >
                  <ChainBadge chain={chain} size="md" />
                </button>
              ))}
            </div>
          </div>

          {/* Toggle Filters */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all',
              showFilters
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:bg-muted'
            )}
          >
            <SlidersHorizontal className="h-4 w-4" />
            Filters
          </button>
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-border grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Event Type */}
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Event Type
              </label>
              <div className="flex flex-wrap gap-2">
                {eventTypes.map((type) => (
                  <button
                    key={type.value || 'all'}
                    onClick={() => setSelectedEventType(type.value)}
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-sm transition-all',
                      selectedEventType === type.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Min Value Slider */}
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Minimum Value: {formatUSD(liveFeedMinValue)}
              </label>
              <input
                type="range"
                min="0"
                max="10000000"
                step="100000"
                value={liveFeedMinValue}
                onChange={(e) => setLiveFeedMinValue(Number(e.target.value))}
                className="w-full h-2 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
              />
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>$0</span>
                <span>$10M</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Stats Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="card-glass rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-foreground">{filteredEvents.length}</p>
          <p className="text-xs text-muted-foreground">Events</p>
        </div>
        <div className="card-glass rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-success">
            {formatUSD(filteredEvents.reduce((sum, e) => sum + e.value_usd, 0))}
          </p>
          <p className="text-xs text-muted-foreground">Total Volume</p>
        </div>
        <div className="card-glass rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-foreground">
            {filteredEvents.filter(e => e.type === 'perp_trade').length}
          </p>
          <p className="text-xs text-muted-foreground">Perp Trades</p>
        </div>
        <div className="card-glass rounded-lg p-3 text-center">
          <p className="text-2xl font-bold text-foreground">
            {filteredEvents.filter(e => e.type === 'large_swap').length}
          </p>
          <p className="text-xs text-muted-foreground">Large Swaps</p>
        </div>
      </div>

      {/* Event List */}
      <LiveEventList events={filteredEvents} />
    </div>
  );
}
