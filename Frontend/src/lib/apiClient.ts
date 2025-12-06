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

async function handleError(path: string, res: Response): Promise<never> {
  let bodyText = '';
  try {
    bodyText = await res.text();
  } catch {
    // ignore parsing errors; we'll fall back to status text
  }

  let detail: string | undefined;
  if (bodyText) {
    try {
      const parsed = JSON.parse(bodyText);
      if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
        const rawDetail = (parsed as { detail: unknown }).detail;
        if (typeof rawDetail === 'string') {
          detail = rawDetail;
        } else {
          detail = JSON.stringify(rawDetail);
        }
      } else if (typeof parsed === 'string') {
        detail = parsed;
      }
    } catch {
      detail = bodyText;
    }
  }

  const message = (detail && detail.trim()) || `API error ${res.status} for ${path}: ${res.statusText}`;
  const error = new Error(message) as Error & { status?: number; rawBody?: string };
  error.name = 'ApiError';
  error.status = res.status;
  error.rawBody = bodyText || undefined;
  throw error;
}

async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    return handleError(path, res);
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
    return handleError(path, res);
  }
  return res.json() as Promise<T>;
}

async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    return handleError(path, res);
  }
  return res.json() as Promise<T>;
}

async function apiDelete<T>(path: string): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) {
    return handleError(path, res);
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
  updateWhale: (whaleId: string, payload: import('@/types/api').WhaleUpdateRequest) =>
    apiPatch<WhaleSummary>(`/api/v1/whales/${whaleId}`, payload),
  deleteWhale: (whaleId: string) =>
    apiDelete<import('@/types/api').DeleteResponse>(`/api/v1/whales/${whaleId}`),
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
    return apiGet<{ items: Trade[]; next_cursor: string | null; total: number }>(
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
  importHyperliquidPaidHistory: (chain: string, address: string, start_date: string, end_date: string) =>
    apiPost<{ imported: number; skipped: number }>(
      `/api/v1/wallets/${chain}/${address}/hyperliquid/import_paid`,
      { start_date, end_date }
    ),
  runCopierBacktest: (body: {
    chain: string;
    address: string;
    initial_deposit_usd: number;
    position_size_pct?: number | null;
    fee_bps?: number;
    slippage_bps?: number;
    start?: string;
    end?: string;
    max_trades?: number;
    asset_symbols?: string[];
    include_price_points?: boolean;
    trades_limit?: number;
    trades_offset?: number;
  }) => apiPost<import('@/types/api').CopierBacktestResponse>('/api/v1/backtest/copier', body),
  runMultiBacktest: (body: import('@/types/api').MultiWhaleBacktestRequest) =>
    apiPost<import('@/types/api').MultiWhaleBacktestResponse>('/api/v1/backtest/copier/multi', body),
  getWhaleAssets: (chain: string, address: string) =>
    apiGet<import('@/types/api').WhaleAssetsResponse>(
      `/api/v1/backtest/assets?chain=${chain}&address=${address}`
    ),
  getBacktestRuns: (chain: string, address: string, limit = 50) =>
    apiGet<import('@/types/api').BacktestRunSummary[]>(
      `/api/v1/backtest/runs?chain=${chain}&address=${address}&limit=${limit}`
    ),
  getLiveTrades: (chain: string, address: string, since?: string, limit = 50) => {
    const params = new URLSearchParams();
    params.set('chain', chain);
    params.set('address', address);
    params.set('limit', `${limit}`);
    if (since) params.set('since', since);
    return apiGet<import('@/types/api').LiveTradesResponse>(`/api/v1/backtest/live-trades?${params.toString()}`);
  },
  startCopierSession: (body: {
    chain: string;
    address: string;
    run_id: number;
    execute?: boolean;
    position_size_pct?: number | null;
  }) =>
    apiPost<import('@/types/api').CopierSessionStatus>('/api/v1/backtest/live/start', body),
  listActiveCopierSessions: (chain: string, address: string) =>
    apiGet<import('@/types/api').CopierSessionStatus[]>(
      `/api/v1/backtest/live/active?chain=${chain}&address=${address}`
    ),
  stopCopierSession: (session_id: number) =>
    apiPost<import('@/types/api').CopierSessionStatus>(`/api/v1/backtest/live/stop?session_id=${session_id}`, {}),
  getCopierSessionStatus: (session_id: number) =>
    apiGet<import('@/types/api').CopierSessionStatus>(`/api/v1/backtest/live/status?session_id=${session_id}`),
};
