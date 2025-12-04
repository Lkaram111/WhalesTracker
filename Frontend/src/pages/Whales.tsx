import { useCallback, useEffect, useMemo, useState } from 'react';
import { WhaleTable } from '@/components/domain/whales/WhaleTable';
import { ChainBadge } from '@/components/common/ChainBadge';
import { AddWhaleForm } from '@/components/domain/whales/AddWhaleForm';
import { useFiltersStore } from '@/stores/filtersStore';
import { 
  Pagination, 
  PaginationContent, 
  PaginationItem, 
  PaginationPrevious, 
  PaginationNext 
} from '@/components/ui/pagination';
import { Search, Filter } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChainId } from '@/types/api';
import { api } from '@/lib/apiClient';
import type { WhaleSummary } from '@/types/api';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

const chains: ChainId[] = ['ethereum', 'bitcoin', 'hyperliquid'];
const whaleTypes = [
  { value: null, label: 'All Types' },
  { value: 'holder', label: 'Holder' },
  { value: 'trader', label: 'Trader' },
  { value: 'holder_trader', label: 'Holder + Trader' },
];
const sortOptions = [
  { value: 'roi', label: 'ROI' },
  { value: 'realized_pnl_usd', label: 'Realized PnL' },
  { value: 'volume_30d_usd', label: '30d Volume' },
  { value: 'last_active_at', label: 'Last Active' },
  { value: 'win_rate_percent', label: 'Win Rate' },
  { value: 'address', label: 'Address' },
  { value: 'chain', label: 'Chain' },
  { value: 'type', label: 'Type' },
];
const roiPresets = [
  { value: null, label: 'Any ROI' },
  { value: 0, label: '> 0%' },
  { value: 50, label: '> 50%' },
  { value: 100, label: '> 100%' },
  { value: 500, label: '> 500%' },
];

export default function Whales() {
  const {
    selectedChains,
    toggleChain,
    setSelectedChains,
    whaleType,
    setWhaleType,
    sortBy,
    setSortBy,
    sortDir,
    setSortDir,
    minRoi,
    setMinRoi,
    searchQuery,
    setSearchQuery,
  } = useFiltersStore();

  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage] = useState(1);
  const [whales, setWhales] = useState<WhaleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [pageSize, setPageSize] = useState(5);

  const loadWhales = useCallback(() => {
    const params = new URLSearchParams();
    if (selectedChains.length && selectedChains.length < chains.length) {
      params.set('chain', selectedChains.join(','));
    }
    if (whaleType) params.set('type', whaleType);
    if (sortBy) params.set('sortBy', sortBy);
    if (minRoi !== null) params.set('minRoi', String(minRoi));
    if (searchQuery) params.set('search', searchQuery);
    params.set('limit', '100');

    api.getWhales(params)
      .then((res) => {
        setWhales(res.items);
        setTotal(res.total);
        setPage(1);
      })
      .catch(() => {
        setWhales([]);
        setTotal(0);
      });
  }, [selectedChains, whaleType, minRoi, searchQuery, sortBy]);

  useEffect(() => {
    loadWhales();
  }, [loadWhales]);

  // Reset to first page whenever filters change
  useEffect(() => {
    setPage(1);
  }, [selectedChains, whaleType, minRoi, searchQuery, sortBy]);

  const filteredWhales = useMemo(() => whales, [whales]);
  const sortedWhales = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1;
    return [...filteredWhales].sort((a, b) => {
      const getVal = (w: WhaleSummary) => {
        switch (sortBy) {
          case 'roi':
            return w.roi_percent ?? 0;
          case 'realized_pnl_usd':
            return w.realized_pnl_usd ?? 0;
          case 'volume_30d_usd':
            return w.volume_30d_usd ?? 0;
          case 'last_active_at':
            return new Date(w.last_active_at).getTime();
          case 'win_rate_percent':
            return w.win_rate_percent ?? -Infinity;
          case 'address':
            return w.address.toLowerCase();
          case 'chain':
            return w.chain;
          case 'type':
            return w.type;
          default:
            return 0;
        }
      };
      const va = getVal(a);
      const vb = getVal(b);
      if (typeof va === 'number' && typeof vb === 'number') {
        return (va - vb) * dir;
      }
      return String(va).localeCompare(String(vb)) * dir;
    });
  }, [filteredWhales, sortBy, sortDir]);

  const totalPages = Math.max(1, Math.ceil(sortedWhales.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const start = (currentPage - 1) * pageSize;
  const end = start + pageSize;
  const pageData = sortedWhales.slice(start, end);

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field as typeof sortBy);
      setSortDir('desc');
    }
  };

  const activeFiltersCount = [
    selectedChains.length < 3,
    whaleType !== null,
    minRoi !== null,
    searchQuery !== ''
  ].filter(Boolean).length;

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Whales</h1>
        <p className="text-muted-foreground">Explore and filter tracked whale wallets</p>
      </div>

      <AddWhaleForm
        initialChain={selectedChains.length === 1 ? selectedChains[0] : 'ethereum'}
        onCreated={(whale) => {
          // Ensure the new whale's chain is visible in filters
          if (!selectedChains.includes(whale.chain)) {
            setSelectedChains([...selectedChains, whale.chain]);
          }
          loadWhales();
        }}
      />

      {/* Filters Bar */}
      <div className="card-glass rounded-xl p-4">
        <div className="flex flex-col lg:flex-row lg:items-center gap-4">
          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search by address or label..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-full rounded-lg border border-border bg-background pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50"
            />
          </div>

          {/* Chain Filters */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSelectedChains(chains)}
              className={cn(
                'rounded-lg border px-2 py-1 text-xs transition-all',
                selectedChains.length === chains.length
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:bg-muted'
              )}
            >
              All
            </button>
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

          {/* Toggle Filters Button */}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={cn(
              'flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-all',
              showFilters || activeFiltersCount > 0
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:bg-muted'
            )}
          >
            <Filter className="h-4 w-4" />
            Filters
            {activeFiltersCount > 0 && (
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                {activeFiltersCount}
              </span>
            )}
          </button>
          {activeFiltersCount > 0 && (
            <button
              onClick={() => {
                setSelectedChains(chains);
                setWhaleType(null);
                setMinRoi(null);
                setSearchQuery('');
                setSortBy('roi');
                setSortDir('desc');
                setShowFilters(false);
              }}
              className="text-sm text-muted-foreground hover:text-foreground transition"
            >
              Reset
            </button>
          )}
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-border grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Type Filter */}
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Whale Type
              </label>
              <div className="flex flex-wrap gap-2">
                {whaleTypes.map((type) => (
                  <button
                    key={type.value || 'all'}
                    onClick={() => setWhaleType(type.value as typeof whaleType)}
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-sm transition-all',
                      whaleType === type.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Sort By */}
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Sort By
              </label>
              <div className="flex flex-wrap gap-2">
                {sortOptions.map((option) => (
                  <button
                    key={option.value}
                    onClick={() => setSortBy(option.value as typeof sortBy)}
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-sm transition-all',
                      sortBy === option.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Min ROI */}
            <div>
              <label className="text-xs text-muted-foreground uppercase tracking-wider mb-2 block">
                Minimum ROI
              </label>
              <div className="flex flex-wrap gap-2">
                {roiPresets.map((preset) => (
                  <button
                    key={preset.value || 'any'}
                    onClick={() => setMinRoi(preset.value)}
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-sm transition-all',
                      minRoi === preset.value
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Results Count */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Showing{' '}
          <span className="font-medium text-foreground">
            {filteredWhales.length === 0 ? 0 : start + 1}-{Math.min(end, filteredWhales.length)}
          </span>{' '}
          of <span className="font-medium text-foreground">{total}</span> whales
        </p>
      </div>

      {/* Whale Table */}
      <div className="space-y-4">
        <WhaleTable whales={pageData} sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Rows per page</span>
            <Select
              value={String(pageSize)}
              onValueChange={(v) => {
                const size = Number(v);
                setPageSize(size);
                setPage(1);
              }}
            >
              <SelectTrigger className="w-24">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[5, 10, 20, 50].map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {filteredWhales.length > pageSize && (
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    href="#"
                  aria-disabled={currentPage === 1}
                  onClick={(e) => {
                    e.preventDefault();
                    setPage((prev) => Math.max(1, prev - 1));
                  }}
                  className={cn(currentPage === 1 && 'pointer-events-none opacity-50')}
                />
              </PaginationItem>
              <PaginationItem>
                <div className="text-sm text-muted-foreground px-3 py-2 rounded-lg border border-border bg-muted/30">
                  Page <span className="text-foreground font-medium">{currentPage}</span> of{' '}
                  <span className="text-foreground font-medium">{totalPages}</span>
                </div>
              </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      href="#"
                      aria-disabled={currentPage === totalPages}
                      onClick={(e) => {
                        e.preventDefault();
                        setPage((prev) => Math.min(totalPages, prev + 1));
                      }}
                      className={cn(currentPage === totalPages && 'pointer-events-none opacity-50')}
                    />
                  </PaginationItem>
              </PaginationContent>
            </Pagination>
          )}
        </div>
      </div>
    </div>
  );
}
