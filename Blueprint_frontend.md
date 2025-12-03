# Blueprint_frontend.md – Frontend Blueprint

## 1. Purpose and Scope

This document specifies exactly how to build the **frontend** of the crypto whale tracker:

- Tech stack and libraries  
- File/folder structure  
- Pages, components, and routing  
- State management and data fetching  
- API contracts (what the backend must provide)  
- Realtime behavior (WebSocket)  
- Styling, UX, and testing strategy  

The goal: you can finish the frontend end‑to‑end using mocks, then plug in the real backend with minimal changes.

---

## 2. Frontend Tech Stack

### Runtime & Framework

- **Node.js**: v20.x  
- **Framework**: Next.js 14 (App Router)  
- **Language**: TypeScript  
- **UI library**: React 18  

### Styling & Layout

- **Tailwind CSS** for styling
- Custom layout components (no heavy UI kit)
- Icons: `lucide-react`

### Data & State

- **TanStack Query v5 (React Query)** for server state and caching
- **Zustand** for UI/global state (filters, theme, watchlist)
- Native React controlled components for forms

### Charts & Visualization

- **Chart.js** + `react-chartjs-2`
- Chart types:
  - Line (ROI history, portfolio history)
  - Bar (volume)
  - Donut (holdings breakdown)

### Realtime

- **socket.io-client** for WebSockets
- Single namespace: `/ws/live`

### Tooling

- Testing: Jest + React Testing Library
- E2E: Playwright
- Linting: ESLint (Next.js config)
- Formatting: Prettier

### Environment

- `NEXT_PUBLIC_API_BASE_URL` – e.g. `http://localhost:8000`

---

## 3. Project Structure

Inside `frontend/`:

```bash
frontend/
  app/
    layout.tsx
    page.tsx                  # Dashboard
    whales/
      page.tsx                # Whales list
      [chain]/
        [address]/
          page.tsx            # Whale detail
    live/
      page.tsx                # Live feed
    settings/
      page.tsx
    about/
      page.tsx
  components/
    layout/
      AppLayout.tsx
      Sidebar.tsx
      TopNav.tsx
    common/
      Button.tsx
      Card.tsx
      Skeleton.tsx
      ErrorState.tsx
      Pagination.tsx
      Badge.tsx
      Tooltip.tsx
      Modal.tsx
    domain/
      whales/
        WhaleTable.tsx
        WhaleRow.tsx
        WhaleFilters.tsx
        ChainSelector.tsx
      wallet/
        WalletHeader.tsx
        WalletMetricsGrid.tsx
        HoldingsTable.tsx
        TradesTable.tsx
        RoiChart.tsx
        PortfolioValueChart.tsx
      live/
        LiveEventList.tsx
        LiveEventItem.tsx
      search/
        AddressSearchInput.tsx
  lib/
    apiClient.ts
    wsClient.ts
    queryClient.ts
    formatters.ts
    constants.ts
  stores/
    uiStore.ts
    filtersStore.ts
  types/
    api.ts
    domain.ts
  public/
    favicon.ico
    logo.svg
  styles/
    globals.css
    tailwind.css
  tests/
    components/
    e2e/
  next.config.mjs
  tsconfig.json
  tailwind.config.mjs
  postcss.config.mjs
```

---

## 4. Information Architecture & Pages

### 4.1 Global UX Decisions

- Default theme: **dark**
- Layout:
  - Left sidebar (navigation + chain selector)
  - Top bar (search, quick filters)
  - Main content area
- Responsive:
  - Mobile: stacked views, collapsible sidebar
  - Desktop: persistent sidebar

---

### 4.2 Dashboard (`/`)

**File:** `app/page.tsx`  

**Goal:** High‑level overview of whales and recent activity.

#### Sections

1. **Top metrics strip**
   - Component: `MetricsStrip`
   - Cards (MetricCard):
     - Total tracked whales
     - Active whales (24h)
     - Whale volume (24h, USD)
     - Hyperliquid whales count

2. **Top whales table**
   - Component: `WhaleTable`
   - Columns:
     - Address (short + copy)
     - Chain
     - Type (Holder/Trader/Both)
     - ROI (%)
     - Realized PnL (USD)
     - Last active
   - Row click → `/whales/[chain]/[address]`

3. **Portfolio value chart**
   - Component: `PortfolioValueChart`
   - Shows selected whales’ portfolio value over time
   - Toggle whales via checkboxes

4. **Recent events**
   - Component: `LiveEventList`
   - Displays last 10 whale events
   - Each event links to the whale detail page

#### Data Dependencies

- `GET /api/v1/dashboard/summary`
- `GET /api/v1/whales/top?limit=10&sortBy=roi`
- `GET /api/v1/events/recent?limit=10`
- `GET /api/v1/whales/top/portfolio-history?limit=5&days=30`

---

### 4.3 Whales List (`/whales`)

**File:** `app/whales/page.tsx`  

**Goal:** Explore whales with filters and sorting.

#### Filters (WhaleFilters + ChainSelector)

- Chain: multi-select (Ethereum, Bitcoin, Hyperliquid)
- Type: Holder / Trader / Holder+Trader
- Sort:
  - ROI
  - Realized PnL
  - 30d volume
  - Last active
- Minimum ROI: filter slider or preset buttons
- Activity window: 24h / 7d / 30d / 90d / any
- Search: address or label substring

Filters are mirrored in **URL search params**.

#### Table (WhaleTable)

Columns:

- Address
- Chain
- Type
- ROI (%)
- Portfolio value (USD)
- Realized PnL (USD)
- 30d volume (USD)
- Trades 30d
- Win rate (%)
- Last active

#### Data Dependencies

`GET /api/v1/whales?chain=&type=&sortBy=&sortDir=&minRoi=&activityWindow=&search=&limit=&offset=`

---

### 4.4 Whale Detail (`/whales/[chain]/[address]`)

**File:** `app/whales/[chain]/[address]/page.tsx`  

**Goal:** Deep profile of a single whale.

#### Layout

1. **Header (`WalletHeader`)**
   - Address (full, copy, external link)
   - Chain badge
   - Type badge
   - Labels (chips): e.g. Smart money, Hyperliquid
   - “Add to watchlist” button (Zustand)

2. **Metrics grid (`WalletMetricsGrid`)**
   - ROI (%)
   - Realized PnL (USD)
   - Unrealized PnL (USD)
   - Portfolio value (USD)
   - 30d volume (USD)
   - Win rate (%)

3. **Charts row**
   - Left: `RoiChart`
     - ROI % over time
     - Range selector: 7d / 30d / 90d / all
   - Right: `PortfolioValueChart`
     - Total USD value over time

4. **Holdings table (`HoldingsTable`)**
   - Columns:
     - Asset
     - Chain
     - Amount
     - Value (USD)
     - Portfolio %

5. **Trades table (`TradesTable`)**
   - Tabs:
     - On-chain
     - Hyperliquid
     - Flows (exchanges/bridge)
   - On-chain columns:
     - Time
     - Platform
     - Direction (Buy/Sell)
     - From asset → To asset
     - Amounts in/out
     - Value (USD)
     - PnL (optional)
     - Tx hash (link)
   - Hyperliquid columns:
     - Time
     - Market (BTC-PERP, etc.)
     - Side
     - Size
     - Entry / Exit
     - PnL USD & %
     - Status (open/closed)

6. **Behavior notes**
   - Text summary from backend (optional)

#### Data Dependencies

- `GET /api/v1/wallets/{chain}/{address}`
- `GET /api/v1/wallets/{chain}/{address}/roi-history?days=30`
- `GET /api/v1/wallets/{chain}/{address}/portfolio-history?days=30`
- `GET /api/v1/wallets/{chain}/{address}/trades?source=onchain&limit=&cursor=`
- `GET /api/v1/wallets/{chain}/{address}/trades?source=hyperliquid&limit=&cursor=`
- `GET /api/v1/wallets/{chain}/{address}/trades?source=exchange_flow&limit=&cursor=`

---

### 4.5 Live Feed (`/live`)

**File:** `app/live/page.tsx`  

**Goal:** Real-time stream of whale events.

#### Features

- Live list (`LiveEventList`)
- Item component (`LiveEventItem`)
- Filters:
  - Chain: Ethereum / Bitcoin / Hyperliquid
  - Type: large swap / large transfer / exchange flow / perp trade
  - Min value (USD) slider
- “Pause live updates” toggle

#### Data Flow

- Initial:
  - `GET /api/v1/events/live?limit=50`
- Realtime:
  - WebSocket `/ws/live`
  - Event shape:

```ts
interface LiveEvent {
  id: string;
  timestamp: string;
  chain: 'ethereum' | 'bitcoin' | 'hyperliquid';
  type: 'large_swap' | 'large_transfer' | 'exchange_flow' | 'perp_trade';
  wallet: { address: string; chain: ChainId; label: string | null };
  summary: string;
  value_usd: number;
  tx_hash: string | null;
  details: Record<string, unknown>;
}
```

---

### 4.6 Settings (`/settings`)

**File:** `app/settings/page.tsx`  

Client-side preferences stored in localStorage via Zustand:

- Theme: dark / light / system
- Default chain(s)
- Live feed defaults:
  - Auto-play on load
  - Minimum event value

---

### 4.7 About (`/about`)

**File:** `app/about/page.tsx`  

Static content explaining:

- What whales are
- What data is used
- Limitations & disclaimers

---

## 5. API Contracts (Frontend Expectations)

The frontend expects these shapes. Backend must conform.

### 5.1 Shared Types (`types/api.ts`)

```ts
export type ChainId = 'ethereum' | 'bitcoin' | 'hyperliquid';

export interface WhaleSummary {
  address: string;
  chain: ChainId;
  type: 'holder' | 'trader' | 'holder_trader';
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

export type TradeSource = 'onchain' | 'hyperliquid' | 'exchange_flow';

export interface Trade {
  id: string;
  timestamp: string;
  chain: ChainId;
  source: TradeSource;
  platform: string;
  direction:
    | 'buy'
    | 'sell'
    | 'deposit'
    | 'withdraw'
    | 'long'
    | 'short'
    | 'close_long'
    | 'close_short';
  base_asset: string | null;
  quote_asset: string | null;
  amount_base: string | null;
  amount_quote: string | null;
  value_usd: number;
  pnl_usd: number | null;
  pnl_percent: number | null;
  tx_hash: string | null;
  external_url: string | null;
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
```

---

### 5.2 Endpoint Specs

#### Dashboard

`GET /api/v1/dashboard/summary`

```json
{
  "total_tracked_whales": 120,
  "active_whales_24h": 36,
  "total_volume_24h_usd": 53200000,
  "hyperliquid_whales": 18
}
```

`GET /api/v1/whales/top?limit=10&sortBy=roi`

```json
{
  "items": [ /* WhaleSummary[] */ ],
  "total": 120
}
```

#### Whales List

`GET /api/v1/whales?chain=&type=&sortBy=&sortDir=&minRoi=&activityWindow=&search=&limit=&offset=`

```json
{
  "items": [ /* WhaleSummary[] */ ],
  "total": 87
}
```

#### Wallet Summary

`GET /api/v1/wallets/{chain}/{address}`

```json
{
  "wallet": {
    "address": "0x1234...",
    "chain": "ethereum",
    "type": "holder_trader",
    "labels": ["smart_money", "hyperliquid"],
    "external_explorer_url": "https://etherscan.io/address/0x1234..."
  },
  "metrics": {
    "roi_percent": 145.3,
    "realized_pnl_usd": 385000,
    "unrealized_pnl_usd": 45000,
    "portfolio_value_usd": 220000,
    "volume_30d_usd": 1300000,
    "trades_30d": 42,
    "win_rate_percent": 76.2,
    "first_seen_at": "2024-02-01T10:00:00Z",
    "last_active_at": "2025-12-02T20:31:00Z"
  },
  "holdings": [ /* Holding[] */ ],
  "notes": "Frequently accumulates ETH after large dips and uses Hyperliquid for high leverage."
}
```

#### ROI & Portfolio History

`GET /api/v1/wallets/{chain}/{address}/roi-history?days=30`

```json
{
  "points": [
    { "timestamp": "2025-11-01T00:00:00Z", "roi_percent": 120.0 }
  ]
}
```

`GET /api/v1/wallets/{chain}/{address}/portfolio-history?days=30`

```json
{
  "points": [
    { "timestamp": "2025-11-01T00:00:00Z", "value_usd": 180000 }
  ]
}
```

#### Trades

`GET /api/v1/wallets/{chain}/{address}/trades?source=onchain&limit=50&cursor=...`

```json
{
  "items": [ /* Trade[] */ ],
  "next_cursor": "opaque-or-null"
}
```

#### Events

`GET /api/v1/events/recent?limit=10`

```json
{
  "items": [ /* LiveEvent[] */ ]
}
```

`GET /api/v1/events/live?limit=50`

```json
{
  "items": [ /* LiveEvent[] */ ]
}
```

---

## 6. State Management & Data Fetching

### 6.1 React Query Setup

`lib/queryClient.ts`:

```ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: 2
    }
  }
});
```

Wrap `app/layout.tsx` with a provider component that uses `QueryClientProvider`.

### 6.2 Zustand Stores

`stores/uiStore.ts`:

- theme: 'dark' | 'light' | 'system'
- sidebarCollapsed: boolean

`stores/filtersStore.ts`:

- selectedChains: ChainId[]
- whaleType
- sortBy / sortDir
- minRoi
- activityWindow
- liveFeedMinValue
- watchlist: { chain: ChainId; address: string; label?: string }[]

Use `persist` middleware to store in `localStorage`.

---

## 7. API Client & WebSocket Client

### 7.1 API Client

`lib/apiClient.ts`:

```ts
const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {})
    }
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getDashboardSummary: () => apiGet('/api/v1/dashboard/summary'),
  getTopWhales: (params: string) => apiGet(`/api/v1/whales/top?${params}`),
  getWhales: (params: string) => apiGet(`/api/v1/whales?${params}`),
  getWalletSummary: (chain: string, address: string) =>
    apiGet(`/api/v1/wallets/${chain}/${address}`),
  // ...and so on
};
```

### 7.2 WebSocket Client

`lib/wsClient.ts`:

```ts
import { io, Socket } from 'socket.io-client';
import type { LiveEvent } from '@/types/api';

let socket: Socket | null = null;

export function getLiveSocket(): Socket {
  if (!socket) {
    socket = io(process.env.NEXT_PUBLIC_API_BASE_URL!, {
      path: '/ws/live',
      transports: ['websocket']
    });
  }
  return socket;
}

export function subscribeToLiveEvents(onEvent: (event: LiveEvent) => void) {
  const s = getLiveSocket();
  const handler = (payload: LiveEvent) => onEvent(payload);
  s.on('live_event', handler);
  return () => {
    s.off('live_event', handler);
  };
}
```

---

## 8. Styling Guidelines

### 8.1 Tailwind Theme

- Background:
  - body: `bg-slate-950 text-slate-50`
  - panels: `bg-slate-900 border border-slate-800`
- Primary accent: `blue-500`
- Success: `emerald-400`
- Danger: `rose-400`

Example card:

```tsx
<div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm">
  {children}
</div>
```

### 8.2 Typography

- Page title: `text-2xl font-semibold`
- Section title: `text-xl font-semibold`
- Body text: `text-sm text-slate-300`
- Secondary text: `text-xs text-slate-500`

### 8.3 Accessibility

- Focus styles: `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500`
- Icon buttons: `aria-label` attributes
- Tables: proper `<th>` usage

---

## 9. Testing Strategy

### 9.1 Unit / Component

- Test key components:
  - `WhaleTable`
  - `WalletMetricsGrid`
  - `LiveEventList`
- Use Jest + React Testing Library with mocked props.

### 9.2 Integration

- Mock API with MSW:
  - `/whales` page: confirm filter → network calls → UI updates.
  - Whale detail: ensure metrics and charts show with mocked data.

### 9.3 E2E (Playwright)

- Smoke tests:
  - Load dashboard → see top whales.
  - Click whale → detail page renders.
  - Open live feed → see events; simulate WebSocket via mock server in CI.

---

## 10. Frontend Implementation Checklist

You can treat this as a task list:

- [ ] Initialize Next.js 14 + TypeScript project
- [ ] Configure Tailwind & base theme
- [ ] Add `QueryClientProvider` and TanStack Query setup
- [ ] Create Zustand `uiStore` and `filtersStore` with persistence
- [ ] Implement layout: `AppLayout`, `Sidebar`, `TopNav`
- [ ] Implement shared components: `Button`, `Card`, `Skeleton`, `ErrorState`, `Pagination`, `Badge`, `Tooltip`, `Modal`
- [ ] Implement domain components for whales (filters + table)
- [ ] Implement Dashboard page with mock data
- [ ] Implement Whales list page with URL-driven filters
- [ ] Implement Whale detail page (header, metrics, holdings, charts, trades)
- [ ] Implement Live feed page (initial fetch + real WebSocket subscription)
- [ ] Implement Settings and About pages
- [ ] Replace mock data with real API calls using `apiClient.ts`
- [ ] Implement tests (unit, integration, E2E)
- [ ] Final UI polish (responsive, accessibility, animations if desired)

Once this checklist is complete, the frontend will be ready to plug into the backend following `Plan.md`.
