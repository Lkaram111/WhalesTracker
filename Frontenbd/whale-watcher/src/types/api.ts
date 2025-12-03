export type ChainId = 'ethereum' | 'bitcoin' | 'hyperliquid';
export type WhaleType = 'holder' | 'trader' | 'holder_trader';

export interface WhaleSummary {
  address: string;
  chain: ChainId;
  type: WhaleType;
  labels: string[];
  roi_percent: number;
  realized_pnl_usd: number;
  unrealized_pnl_usd: number | null;
  portfolio_value_usd: number;
  volume_30d_usd: number;
  trades_30d: number;
  win_rate_percent: number | null;
  last_active_at: string;
}

export interface Holding {
  asset_symbol: string;
  asset_name: string;
  chain: ChainId;
  amount: string;
  value_usd: number;
  portfolio_percent: number;
}

export interface RoiPoint {
  timestamp: string;
  roi_percent: number;
}

export interface PortfolioPoint {
  timestamp: string;
  value_usd: number;
}

export interface OpenPosition {
  asset: string;
  direction: 'long' | 'short';
  size: number;
  entry_price_usd: number | null;
  mark_price_usd: number | null;
  value_usd: number | null;
  unrealized_pnl_usd: number | null;
}

export type TradeSource = 'onchain' | 'hyperliquid' | 'exchange_flow';

export interface Trade {
  id: string;
  timestamp: string;
  chain: ChainId;
  source: TradeSource;
  platform: string;
  direction: 'buy' | 'sell' | 'deposit' | 'withdraw' | 'long' | 'short' | 'close_long' | 'close_short';
  base_asset: string | null;
  quote_asset: string | null;
  amount_base: string | null;
  amount_quote: string | null;
  value_usd: number;
  pnl_usd: number | null;
  pnl_percent: number | null;
  tx_hash: string | null;
  external_url: string | null;
  price_usd?: number | null;
  open_price_usd?: number | null;
  close_price_usd?: number | null;
}

export interface LiveEvent {
  id: string;
  timestamp: string;
  chain: ChainId;
  type: 'large_swap' | 'large_transfer' | 'exchange_flow' | 'perp_trade';
  wallet: {
    address: string;
    chain: ChainId;
    label: string | null;
  };
  summary: string;
  value_usd: number;
  tx_hash: string | null;
  details: Record<string, unknown>;
}

export interface DashboardSummary {
  total_tracked_whales: number;
  active_whales_24h: number;
  total_volume_24h_usd: number;
  hyperliquid_whales: number;
}

export interface WalletDetails {
  wallet: {
    address: string;
    chain: ChainId;
    type: WhaleType;
    labels: string[];
    external_explorer_url: string;
  };
  metrics: {
    roi_percent: number;
    realized_pnl_usd: number;
    unrealized_pnl_usd: number | null;
    portfolio_value_usd: number;
    volume_30d_usd: number;
    trades_30d: number;
    win_rate_percent: number | null;
    first_seen_at: string;
    last_active_at: string;
  };
  holdings: Holding[];
  notes: string;
}

export interface WhaleCreateRequest {
  address: string;
  chain: ChainId;
  labels?: string[];
  type?: WhaleType;
}
