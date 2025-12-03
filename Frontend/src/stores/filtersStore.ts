import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ChainId } from '@/types/api';

interface FiltersState {
  selectedChains: ChainId[];
  whaleType: 'holder' | 'trader' | 'holder_trader' | null;
  sortBy: 'roi' | 'realized_pnl_usd' | 'volume_30d_usd' | 'last_active_at';
  sortDir: 'asc' | 'desc';
  minRoi: number | null;
  activityWindow: '24h' | '7d' | '30d' | '90d' | 'any';
  searchQuery: string;
  liveFeedMinValue: number;
  watchlist: { address: string; chain: ChainId; label?: string }[];
  
  setSelectedChains: (chains: ChainId[]) => void;
  toggleChain: (chain: ChainId) => void;
  setWhaleType: (type: 'holder' | 'trader' | 'holder_trader' | null) => void;
  setSortBy: (field: FiltersState['sortBy']) => void;
  setSortDir: (dir: 'asc' | 'desc') => void;
  setMinRoi: (roi: number | null) => void;
  setActivityWindow: (window: FiltersState['activityWindow']) => void;
  setSearchQuery: (query: string) => void;
  setLiveFeedMinValue: (value: number) => void;
  addToWatchlist: (address: string, chain: ChainId, label?: string) => void;
  removeFromWatchlist: (address: string, chain: ChainId) => void;
  isInWatchlist: (address: string, chain: ChainId) => boolean;
  resetFilters: () => void;
}

const defaultFilters = {
  selectedChains: ['ethereum', 'bitcoin', 'hyperliquid'] as ChainId[],
  whaleType: null,
  sortBy: 'roi' as const,
  sortDir: 'desc' as const,
  minRoi: null,
  activityWindow: 'any' as const,
  searchQuery: '',
  liveFeedMinValue: 100000,
  watchlist: [],
};

export const useFiltersStore = create<FiltersState>()(
  persist(
    (set, get) => ({
      ...defaultFilters,
      
      setSelectedChains: (chains) => set({ selectedChains: chains }),
      toggleChain: (chain) => set((state) => {
        const chains = state.selectedChains.includes(chain)
          ? state.selectedChains.filter(c => c !== chain)
          : [...state.selectedChains, chain];
        return { selectedChains: chains.length > 0 ? chains : state.selectedChains };
      }),
      setWhaleType: (type) => set({ whaleType: type }),
      setSortBy: (field) => set({ sortBy: field }),
      setSortDir: (dir) => set({ sortDir: dir }),
      setMinRoi: (roi) => set({ minRoi: roi }),
      setActivityWindow: (window) => set({ activityWindow: window }),
      setSearchQuery: (query) => set({ searchQuery: query }),
      setLiveFeedMinValue: (value) => set({ liveFeedMinValue: value }),
      addToWatchlist: (address, chain, label) => set((state) => ({
        watchlist: [...state.watchlist, { address, chain, label }]
      })),
      removeFromWatchlist: (address, chain) => set((state) => ({
        watchlist: state.watchlist.filter(w => !(w.address === address && w.chain === chain))
      })),
      isInWatchlist: (address, chain) => {
        return get().watchlist.some(w => w.address === address && w.chain === chain);
      },
      resetFilters: () => set(defaultFilters),
    }),
    {
      name: 'whale-tracker-filters',
    }
  )
);
