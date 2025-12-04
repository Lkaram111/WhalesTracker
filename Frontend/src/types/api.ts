export type ChainId = 'ethereum' | 'bitcoin' | 'hyperliquid';
export type WhaleType = 'holder' | 'trader' | 'holder_trader';

export interface WhaleSummary {
  id: string;
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
    id?: string;
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

export interface BackfillStatus {
  whale_id: string;
  chain?: ChainId | null;
  status: 'idle' | 'running' | 'done' | 'error';
  progress: number;
  message?: string | null;
  updated_at?: string | null;
}

export interface BacktestTrade {
  id: number;
  timestamp: string;
  direction: string;
  base_asset: string | null;
  notional_usd: number;
  pnl_usd: number;
  fee_usd: number;
  slippage_usd: number;
  net_pnl_usd: number;
  cumulative_pnl_usd: number;
  equity_usd: number;
  unrealized_pnl_usd: number;
  position_size_base: number | null;
}

export interface BacktestSummary {
  initial_deposit_usd: number;
  recommended_position_pct: number;
  used_position_pct: number;
  leverage_used?: number | null;
  asset_symbols?: string[] | null;
  total_fees_usd: number;
  total_slippage_usd: number;
  gross_pnl_usd: number;
  net_pnl_usd: number;
  roi_percent: number;
  trades_copied: number;
  win_rate_percent: number | null;
  max_drawdown_percent?: number | null;
  max_drawdown_usd?: number | null;
  start: string | null;
  end: string | null;
}

export interface EquityCurvePoint {
  timestamp: string;
  equity_usd: number;
  unrealized_pnl_usd: number;
}

export interface PricePoint {
  timestamp: string;
  price: number;
}

export interface CopierBacktestResponse {
  summary: BacktestSummary;
  trades: BacktestTrade[];
  equity_curve: EquityCurvePoint[];
  price_points?: Record<string, PricePoint[]>;
  trades_total: number;
  trades_limit: number;
  trades_offset: number;
}

export interface BacktestRunSummary {
  id: number;
  whale_id: string;
  created_at: string;
  leverage: number | null;
  position_size_pct: number | null;
  asset_symbols: string[] | null;
  win_rate_percent: number | null;
  trades_copied: number | null;
  max_drawdown_percent: number | null;
  max_drawdown_usd: number | null;
  initial_deposit_usd: number | null;
  net_pnl_usd: number | null;
  roi_percent: number | null;
}

export interface LiveTrade {
  id: number;
  timestamp: string;
  direction: string;
  base_asset: string | null;
  value_usd: number | null;
}

export interface LiveTradesResponse {
  trades: LiveTrade[];
}

export interface CopierSessionStatus {
  session_id: number;
  active: boolean;
  processed: number;
  errors: string[];
  notifications: string[];
}

export interface WhaleAssetsResponse {
  assets: string[];
}
