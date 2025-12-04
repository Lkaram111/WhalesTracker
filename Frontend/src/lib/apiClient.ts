import type {
  DashboardSummary,
  LiveEvent,
  PortfolioPoint,
  RoiPoint,
  Trade,
  WhaleCreateRequest,
  WhaleSummary,
  WalletDetails,
  BackfillStatus,
} from '@/types/api';

const baseUrl =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.NEXT_PUBLIC_API_BASE_URL ||
  'http://localhost:8000';

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status} for ${path}`);
  }
  return res.json() as Promise<T>;
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status} for ${path}: ${detail || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getDashboardSummary: () => apiGet<DashboardSummary>('/api/v1/dashboard/summary'),
  getTopWhales: (limit = 8) =>
    apiGet<{ items: WhaleSummary[]; total: number }>(`/api/v1/whales/top?limit=${limit}`),
  getWhales: (params: URLSearchParams) =>
    apiGet<{ items: WhaleSummary[]; total: number }>(`/api/v1/whales?${params.toString()}`),
  createWhale: (payload: WhaleCreateRequest) =>
    apiPost<WhaleSummary>('/api/v1/whales', payload),
  getBackfillStatus: (whaleId: string) =>
    apiGet<BackfillStatus>(`/api/v1/whales/${whaleId}/backfill_status`),
  resolveWhale: (chain: string, address: string) =>
    apiGet<{ whale_id: string }>(`/api/v1/whales/resolve?chain=${chain}&address=${address}`),
  resetHyperliquid: (whaleId: string) =>
    apiPost<BackfillStatus>(`/api/v1/whales/${whaleId}/reset_hyperliquid`, {}),
  getRecentEvents: (limit = 10) =>
    apiGet<{ items: LiveEvent[] }>(`/api/v1/events/recent?limit=${limit}`),
  getLiveEvents: (limit = 50) =>
    apiGet<{ items: LiveEvent[] }>(`/api/v1/events/live?limit=${limit}`),
  getWalletDetails: (chain: string, address: string) =>
    apiGet<WalletDetails>(`/api/v1/wallets/${chain}/${address}`),
  backfillWhale: (whaleId: string) =>
    apiPost<BackfillStatus>(`/api/v1/whales/${whaleId}/backfill`, {}),
  getWalletPositions: (chain: string, address: string) =>
    apiGet<{ items: import('@/types/api').OpenPosition[] }>(
      `/api/v1/wallets/${chain}/${address}/positions`
    ),
  getWalletTrades: (
    chain: string,
    address: string,
    source?: string,
    direction?: string,
    limit = 200,
    cursor?: string
  ) => {
    const params = new URLSearchParams();
    if (source) params.set('source', source);
    if (direction) params.set('direction', direction);
    params.set('limit', `${limit}`);
    if (cursor) params.set('cursor', cursor);
    return apiGet<{ items: Trade[]; next_cursor: string | null }>(
      `/api/v1/wallets/${chain}/${address}/trades?${params.toString()}`
    );
  },
  getWalletRoiHistory: (chain: string, address: string, days = 30) =>
    apiGet<{ points: RoiPoint[] }>(
      `/api/v1/wallets/${chain}/${address}/roi-history?days=${days}`
    ),
  getWalletPortfolioHistory: (chain: string, address: string, days = 30) =>
    apiGet<{ points: PortfolioPoint[] }>(
      `/api/v1/wallets/${chain}/${address}/portfolio-history?days=${days}`
    ),
};
