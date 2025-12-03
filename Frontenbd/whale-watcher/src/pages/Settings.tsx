import { useUIStore } from '@/stores/uiStore';
import { useFiltersStore } from '@/stores/filtersStore';
import { formatUSD } from '@/lib/formatters';
import { ChainBadge } from '@/components/common/ChainBadge';
import { AddressDisplay } from '@/components/common/AddressDisplay';
import { Moon, Sun, Monitor, Radio, Trash2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChainId } from '@/types/api';

const themes = [
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'system', label: 'System', icon: Monitor },
];

const defaultChains: { value: ChainId; label: string }[] = [
  { value: 'ethereum', label: 'Ethereum' },
  { value: 'bitcoin', label: 'Bitcoin' },
];

export default function Settings() {
  const { theme, setTheme } = useUIStore();
  const { 
    liveFeedMinValue, 
    setLiveFeedMinValue,
    watchlist,
    removeFromWatchlist
  } = useFiltersStore();

  return (
    <div className="space-y-6 animate-fade-up max-w-3xl">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Settings</h1>
        <p className="text-muted-foreground">Customize your WhaleTracker experience</p>
      </div>

      {/* Appearance */}
      <div className="card-glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Appearance</h2>
        <div>
          <label className="text-sm text-muted-foreground mb-3 block">Theme</label>
          <div className="flex gap-3">
            {themes.map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.value}
                  onClick={() => setTheme(t.value as 'dark' | 'light' | 'system')}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border px-4 py-3 transition-all',
                    theme === t.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-muted'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  <span className="text-sm font-medium">{t.label}</span>
                </button>
              );
            })}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            Note: Light mode is currently in preview. Dark theme is recommended.
          </p>
        </div>
      </div>

      {/* Live Feed Settings */}
      <div className="card-glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <Radio className="h-5 w-5 text-primary" />
          Live Feed
        </h2>
        <div className="space-y-4">
          <div>
            <label className="text-sm text-muted-foreground mb-3 block">
              Default Minimum Event Value: <span className="text-foreground font-medium">{formatUSD(liveFeedMinValue)}</span>
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
      </div>

      {/* Watchlist */}
      <div className="card-glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Watchlist</h2>
        {watchlist.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-muted-foreground">No wallets in your watchlist</p>
            <p className="text-sm text-muted-foreground mt-1">
              Add wallets from the whale detail page
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {watchlist.map((item) => (
              <div 
                key={`${item.chain}-${item.address}`}
                className="flex items-center justify-between p-3 rounded-lg bg-muted/30"
              >
                <div className="flex items-center gap-3">
                  <ChainBadge chain={item.chain} />
                  <AddressDisplay 
                    address={item.address} 
                    chain={item.chain}
                    showCopy={true}
                    showExternalLink={true}
                  />
                  {item.label && (
                    <span className="text-sm text-muted-foreground">({item.label})</span>
                  )}
                </div>
                <button
                  onClick={() => removeFromWatchlist(item.address, item.chain)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Data & Privacy */}
      <div className="card-glass rounded-xl p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Data & Privacy</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">Local Storage</p>
              <p className="text-xs text-muted-foreground">Your settings are stored locally in your browser</p>
            </div>
            <button
              onClick={() => {
                localStorage.clear();
                window.location.reload();
              }}
              className="rounded-lg border border-destructive/50 px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive/10 transition-all"
            >
              Clear All Data
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
