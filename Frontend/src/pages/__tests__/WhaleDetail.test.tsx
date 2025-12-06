import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import WhaleDetail from '../WhaleDetail';
import { api } from '@/lib/apiClient';

jest.mock('@/lib/apiClient', () => {
  const mockApi = {
    getWalletDetails: jest.fn(),
    getWalletTrades: jest.fn(),
    getWalletPositions: jest.fn(),
    getWalletRoiHistory: jest.fn(),
    getWalletPortfolioHistory: jest.fn(),
    getWhales: jest.fn(),
    resolveWhale: jest.fn(),
    getBackfillStatus: jest.fn(),
    resetHyperliquid: jest.fn(),
    importHyperliquidPaidHistory: jest.fn(),
    backfillWhale: jest.fn(),
    createWhale: jest.fn(),
  };
  return { api: mockApi };
});

const mockApi = api as jest.Mocked<typeof api>;

const mockWalletDetails = {
  wallet: {
    id: 'whale-1',
    address: '0xabc',
    chain: 'hyperliquid' as const,
    type: 'trader' as const,
    labels: [],
    external_explorer_url: 'https://app.hyperliquid.xyz/explorer/user/0xabc',
  },
  metrics: {
    roi_percent: 12,
    realized_pnl_usd: 500,
    unrealized_pnl_usd: 100,
    portfolio_value_usd: 1200,
    volume_30d_usd: 50000,
    trades_30d: 10,
    win_rate_percent: 55,
    first_seen_at: new Date().toISOString(),
    last_active_at: new Date().toISOString(),
  },
  holdings: [],
  notes: '',
};

const createMockTrades = () => {
  const now = Date.now();
  return [
    {
      id: 't1',
      timestamp: new Date(now - 2 * 60 * 60 * 1000).toISOString(),
      chain: 'hyperliquid' as const,
      source: 'hyperliquid' as const,
      platform: 'Hyperliquid',
      direction: 'buy' as const,
      base_asset: 'ETH',
      quote_asset: 'USDC',
      amount_base: '1',
      amount_quote: '2000',
      value_usd: 2000,
      pnl_usd: 50,
      pnl_percent: 2.5,
      tx_hash: '0xhash1',
      external_url: null,
      open_price_usd: 2000,
      close_price_usd: null,
      price_usd: 2000,
    },
    {
      id: 't2',
      timestamp: new Date(now - 3 * 24 * 60 * 60 * 1000).toISOString(),
      chain: 'hyperliquid' as const,
      source: 'onchain' as const,
      platform: 'Onchain',
      direction: 'sell' as const,
      base_asset: 'BTC',
      quote_asset: 'USDC',
      amount_base: '0.1',
      amount_quote: '3000',
      value_usd: 3000,
      pnl_usd: -25,
      pnl_percent: -0.5,
      tx_hash: '0xhash2',
      external_url: null,
      open_price_usd: null,
      close_price_usd: null,
      price_usd: 30000,
    },
  ];
};

const setupApiMocks = (trades = createMockTrades()) => {
  const now = new Date();
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);

  mockApi.getWalletDetails.mockResolvedValue(mockWalletDetails);
  mockApi.getWalletTrades.mockImplementation(async (_chain, _address, source) => ({
    items: source ? trades.filter((trade) => trade.source === source) : trades,
    next_cursor: null,
    total: trades.length,
  }));
  mockApi.getWalletPositions.mockResolvedValue({ items: [] });
  mockApi.getWalletRoiHistory.mockResolvedValue({
    points: [
      { timestamp: yesterday.toISOString(), roi_percent: 10 },
      { timestamp: now.toISOString(), roi_percent: 12 },
    ],
  });
  mockApi.getWalletPortfolioHistory.mockResolvedValue({
    points: [
      { timestamp: yesterday.toISOString(), value_usd: 1000 },
      { timestamp: now.toISOString(), value_usd: 1200 },
    ],
  });
  mockApi.getWhales.mockResolvedValue({
    items: [{ id: 'whale-1', chain: 'hyperliquid', address: '0xabc', type: 'trader', labels: [] }],
    total: 1,
  });
  mockApi.resolveWhale.mockResolvedValue({ whale_id: 'whale-1' });
  mockApi.getBackfillStatus.mockResolvedValue({ whale_id: 'whale-1', status: 'idle', progress: 0 });
  mockApi.resetHyperliquid.mockResolvedValue({ whale_id: 'whale-1', status: 'idle', progress: 0 });
  mockApi.importHyperliquidPaidHistory.mockResolvedValue({ imported: 0, skipped: 0 });
  mockApi.backfillWhale.mockResolvedValue({ whale_id: 'whale-1', status: 'idle', progress: 0 });
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/whales/hyperliquid/0xabc']}>
      <Routes>
        <Route path="/whales/:chain/:address" element={<WhaleDetail />} />
      </Routes>
    </MemoryRouter>
  );

describe('WhaleDetail page', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    setupApiMocks();
  });

  it('filters trades via tabs', async () => {
    renderPage();

    const table = await screen.findByRole('table');
    expect(within(table).getByText('Onchain')).toBeInTheDocument();

    const tab = screen.getByRole('tab', { name: /Hyperliquid/i });
    fireEvent.click(tab);

    await waitFor(() => expect(within(table).queryByText('Onchain')).toBeNull());
    expect(within(table).getAllByText('Hyperliquid').length).toBeGreaterThan(0);
  });

  it('shows 24h metrics and filters recent trades by time', async () => {
    renderPage();

    expect(await screen.findByText('24h PnL')).toBeInTheDocument();
    expect(screen.getByText('24h ROI Change')).toBeInTheDocument();
    expect(screen.getByText('$200.00')).toBeInTheDocument();
    expect(screen.getByText('20.00%')).toBeInTheDocument();

    const table = await screen.findByRole('table');
    expect(within(table).getByText('Onchain')).toBeInTheDocument();

    const timeSelect = screen.getByLabelText('Time filter');
    fireEvent.change(timeSelect, { target: { value: '24h' } });

    await waitFor(() => expect(within(table).queryByText('Onchain')).toBeNull());
    expect(within(table).getByText('Hyperliquid')).toBeInTheDocument();
  });
});
