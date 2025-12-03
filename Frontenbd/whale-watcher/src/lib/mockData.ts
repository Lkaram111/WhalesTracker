import type { 
  WhaleSummary, 
  DashboardSummary, 
  LiveEvent, 
  WalletDetails,
  RoiPoint,
  PortfolioPoint,
  Trade,
  ChainId
} from '@/types/api';

export const mockDashboardSummary: DashboardSummary = {
  total_tracked_whales: 1247,
  active_whales_24h: 342,
  total_volume_24h_usd: 892500000,
  hyperliquid_whales: 186
};

export const mockTopWhales: WhaleSummary[] = [
  {
    address: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    chain: 'ethereum',
    type: 'holder_trader',
    labels: ['smart_money', 'hyperliquid'],
    roi_percent: 892.4,
    realized_pnl_usd: 12450000,
    unrealized_pnl_usd: 3200000,
    portfolio_value_usd: 45600000,
    volume_30d_usd: 89000000,
    trades_30d: 156,
    win_rate_percent: 78.2,
    last_active_at: '2025-12-03T08:45:00Z'
  },
  {
    address: '0x8894E0a0c962CB723c1976a4421c95949bE2D4E3',
    chain: 'ethereum',
    type: 'trader',
    labels: ['defi_whale', 'hyperliquid'],
    roi_percent: 654.8,
    realized_pnl_usd: 8920000,
    unrealized_pnl_usd: 1450000,
    portfolio_value_usd: 28900000,
    volume_30d_usd: 67000000,
    trades_30d: 234,
    win_rate_percent: 72.1,
    last_active_at: '2025-12-03T09:12:00Z'
  },
  {
    address: 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',
    chain: 'bitcoin',
    type: 'holder',
    labels: ['btc_maximalist'],
    roi_percent: 445.2,
    realized_pnl_usd: 5680000,
    unrealized_pnl_usd: 12400000,
    portfolio_value_usd: 89000000,
    volume_30d_usd: 23000000,
    trades_30d: 12,
    win_rate_percent: 91.7,
    last_active_at: '2025-12-02T22:30:00Z'
  },
  {
    address: '0x1234567890123456789012345678901234567890',
    chain: 'ethereum',
    type: 'holder_trader',
    labels: ['exchange', 'market_maker'],
    roi_percent: 389.6,
    realized_pnl_usd: 4230000,
    unrealized_pnl_usd: 890000,
    portfolio_value_usd: 19500000,
    volume_30d_usd: 156000000,
    trades_30d: 892,
    win_rate_percent: 65.4,
    last_active_at: '2025-12-03T09:30:00Z'
  },
  {
    address: '0xABCDEF1234567890ABCDEF1234567890ABCDEF12',
    chain: 'ethereum',
    type: 'trader',
    labels: ['hyperliquid', 'leverage_trader'],
    roi_percent: 312.8,
    realized_pnl_usd: 2890000,
    unrealized_pnl_usd: -120000,
    portfolio_value_usd: 8900000,
    volume_30d_usd: 234000000,
    trades_30d: 1456,
    win_rate_percent: 58.9,
    last_active_at: '2025-12-03T09:28:00Z'
  },
  {
    address: 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq',
    chain: 'bitcoin',
    type: 'holder',
    labels: ['institutional'],
    roi_percent: 287.4,
    realized_pnl_usd: 3450000,
    unrealized_pnl_usd: 8900000,
    portfolio_value_usd: 67000000,
    volume_30d_usd: 12000000,
    trades_30d: 8,
    win_rate_percent: 87.5,
    last_active_at: '2025-12-01T18:00:00Z'
  },
  {
    address: '0x9876543210987654321098765432109876543210',
    chain: 'ethereum',
    type: 'holder_trader',
    labels: ['nft_whale', 'defi'],
    roi_percent: 234.5,
    realized_pnl_usd: 1890000,
    unrealized_pnl_usd: 560000,
    portfolio_value_usd: 12300000,
    volume_30d_usd: 45000000,
    trades_30d: 89,
    win_rate_percent: 71.2,
    last_active_at: '2025-12-03T07:15:00Z'
  },
  {
    address: '0xFEDCBA0987654321FEDCBA0987654321FEDCBA09',
    chain: 'ethereum',
    type: 'trader',
    labels: ['hyperliquid', 'scalper'],
    roi_percent: 198.7,
    realized_pnl_usd: 1230000,
    unrealized_pnl_usd: 89000,
    portfolio_value_usd: 4500000,
    volume_30d_usd: 389000000,
    trades_30d: 3456,
    win_rate_percent: 54.2,
    last_active_at: '2025-12-03T09:29:00Z'
  }
];

export const mockLiveEvents: LiveEvent[] = [
  {
    id: 'evt_001',
    timestamp: '2025-12-03T09:30:15Z',
    chain: 'ethereum',
    type: 'large_swap',
    wallet: {
      address: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
      chain: 'ethereum',
      label: 'Smart Whale'
    },
    summary: 'Swapped 2,400 ETH → 8.2M USDC on Uniswap V3',
    value_usd: 8200000,
    tx_hash: '0xabc123def456...',
    details: { platform: 'Uniswap V3', pair: 'ETH/USDC' }
  },
  {
    id: 'evt_002',
    timestamp: '2025-12-03T09:28:42Z',
    chain: 'hyperliquid',
    type: 'perp_trade',
    wallet: {
      address: '0x8894E0a0c962CB723c1976a4421c95949bE2D4E3',
      chain: 'ethereum',
      label: 'DeFi Whale'
    },
    summary: 'Opened 50x Long BTC-PERP @ $98,450',
    value_usd: 4900000,
    tx_hash: null,
    details: { market: 'BTC-PERP', leverage: '50x', side: 'long' }
  },
  {
    id: 'evt_003',
    timestamp: '2025-12-03T09:25:18Z',
    chain: 'bitcoin',
    type: 'large_transfer',
    wallet: {
      address: 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',
      chain: 'bitcoin',
      label: 'BTC Maximalist'
    },
    summary: 'Transferred 450 BTC to cold storage',
    value_usd: 44325000,
    tx_hash: '3a1b2c3d4e5f...',
    details: { type: 'cold_storage' }
  },
  {
    id: 'evt_004',
    timestamp: '2025-12-03T09:22:05Z',
    chain: 'ethereum',
    type: 'exchange_flow',
    wallet: {
      address: '0x1234567890123456789012345678901234567890',
      chain: 'ethereum',
      label: 'Market Maker'
    },
    summary: 'Withdrew 15M USDT from Binance',
    value_usd: 15000000,
    tx_hash: '0xdef789abc012...',
    details: { exchange: 'Binance', direction: 'withdraw' }
  },
  {
    id: 'evt_005',
    timestamp: '2025-12-03T09:18:33Z',
    chain: 'hyperliquid',
    type: 'perp_trade',
    wallet: {
      address: '0xABCDEF1234567890ABCDEF1234567890ABCDEF12',
      chain: 'ethereum',
      label: 'Leverage Trader'
    },
    summary: 'Closed Short ETH-PERP +$234,500 PnL',
    value_usd: 2800000,
    tx_hash: null,
    details: { market: 'ETH-PERP', pnl: 234500, side: 'close_short' }
  },
  {
    id: 'evt_006',
    timestamp: '2025-12-03T09:15:12Z',
    chain: 'ethereum',
    type: 'large_swap',
    wallet: {
      address: '0x9876543210987654321098765432109876543210',
      chain: 'ethereum',
      label: 'NFT Whale'
    },
    summary: 'Swapped 500K USDC → 145 ETH on Curve',
    value_usd: 500000,
    tx_hash: '0x456789abc...',
    details: { platform: 'Curve', pair: 'USDC/ETH' }
  }
];

export const mockWalletDetails: WalletDetails = {
  wallet: {
    address: '0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
    chain: 'ethereum',
    type: 'holder_trader',
    labels: ['smart_money', 'hyperliquid', 'defi'],
    external_explorer_url: 'https://etherscan.io/address/0x742d35Cc6634C0532925a3b844Bc454e4438f44e'
  },
  metrics: {
    roi_percent: 892.4,
    realized_pnl_usd: 12450000,
    unrealized_pnl_usd: 3200000,
    portfolio_value_usd: 45600000,
    volume_30d_usd: 89000000,
    trades_30d: 156,
    win_rate_percent: 78.2,
    first_seen_at: '2023-06-15T10:00:00Z',
    last_active_at: '2025-12-03T08:45:00Z'
  },
  holdings: [
    { asset_symbol: 'ETH', asset_name: 'Ethereum', chain: 'ethereum', amount: '8450.5', value_usd: 28930000, portfolio_percent: 63.4 },
    { asset_symbol: 'USDC', asset_name: 'USD Coin', chain: 'ethereum', amount: '8200000', value_usd: 8200000, portfolio_percent: 18.0 },
    { asset_symbol: 'WBTC', asset_name: 'Wrapped Bitcoin', chain: 'ethereum', amount: '45.2', value_usd: 4450000, portfolio_percent: 9.8 },
    { asset_symbol: 'LINK', asset_name: 'Chainlink', chain: 'ethereum', amount: '125000', value_usd: 2500000, portfolio_percent: 5.5 },
    { asset_symbol: 'UNI', asset_name: 'Uniswap', chain: 'ethereum', amount: '85000', value_usd: 1020000, portfolio_percent: 2.2 },
    { asset_symbol: 'AAVE', asset_name: 'Aave', chain: 'ethereum', amount: '3200', value_usd: 500000, portfolio_percent: 1.1 }
  ],
  notes: 'This whale consistently accumulates ETH during market corrections and uses Hyperliquid for high-leverage directional bets. Shows strong conviction in DeFi blue chips. Win rate suggests sophisticated entry/exit timing.'
};

export const generateRoiHistory = (days: number): RoiPoint[] => {
  const points: RoiPoint[] = [];
  const now = new Date();
  let roi = 750;
  
  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    roi += (Math.random() - 0.45) * 15;
    points.push({
      timestamp: date.toISOString(),
      roi_percent: Math.max(0, roi)
    });
  }
  return points;
};

export const generatePortfolioHistory = (days: number): PortfolioPoint[] => {
  const points: PortfolioPoint[] = [];
  const now = new Date();
  let value = 38000000;
  
  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    value += (Math.random() - 0.45) * 800000;
    points.push({
      timestamp: date.toISOString(),
      value_usd: Math.max(0, value)
    });
  }
  return points;
};

export const mockTrades: Trade[] = [
  {
    id: 'trade_001',
    timestamp: '2025-12-03T08:45:00Z',
    chain: 'ethereum',
    source: 'onchain',
    platform: 'Uniswap V3',
    direction: 'sell',
    base_asset: 'ETH',
    quote_asset: 'USDC',
    amount_base: '500',
    amount_quote: '1712500',
    value_usd: 1712500,
    pnl_usd: 245000,
    pnl_percent: 16.7,
    tx_hash: '0xabc123...',
    external_url: 'https://etherscan.io/tx/0xabc123...'
  },
  {
    id: 'trade_002',
    timestamp: '2025-12-02T14:22:00Z',
    chain: 'ethereum',
    source: 'onchain',
    platform: 'Curve',
    direction: 'buy',
    base_asset: 'WBTC',
    quote_asset: 'USDC',
    amount_base: '12.5',
    amount_quote: '1231250',
    value_usd: 1231250,
    pnl_usd: null,
    pnl_percent: null,
    tx_hash: '0xdef456...',
    external_url: 'https://etherscan.io/tx/0xdef456...'
  },
  {
    id: 'trade_003',
    timestamp: '2025-12-01T09:15:00Z',
    chain: 'ethereum',
    source: 'hyperliquid',
    platform: 'Hyperliquid',
    direction: 'close_long',
    base_asset: 'BTC-PERP',
    quote_asset: 'USDC',
    amount_base: '25',
    amount_quote: null,
    value_usd: 2462500,
    pnl_usd: 187500,
    pnl_percent: 8.2,
    tx_hash: null,
    external_url: null
  },
  {
    id: 'trade_004',
    timestamp: '2025-11-30T16:45:00Z',
    chain: 'ethereum',
    source: 'exchange_flow',
    platform: 'Binance',
    direction: 'withdraw',
    base_asset: 'USDT',
    quote_asset: null,
    amount_base: '5000000',
    amount_quote: null,
    value_usd: 5000000,
    pnl_usd: null,
    pnl_percent: null,
    tx_hash: '0xghi789...',
    external_url: 'https://etherscan.io/tx/0xghi789...'
  }
];

export const getWhaleByAddress = (chain: ChainId, address: string): WhaleSummary | undefined => {
  return mockTopWhales.find(w => w.chain === chain && w.address.toLowerCase() === address.toLowerCase());
};
