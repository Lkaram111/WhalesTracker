# Plan.md – Backend & Integration Blueprint

## 1. Goal

This backend plan is the companion to `Blueprint_frontend.md`. It describes how to:

1. Stand up the Python backend and database.
2. Integrate with Ethereum, Bitcoin, and Hyperliquid using only free/public APIs or self-hosted infrastructure.
3. Compute whale metrics (ROI, PnL, win-rate).
4. Expose REST + WebSocket endpoints matching the frontend contracts.
5. Connect everything in a way that you can:
   - Build the frontend first with mocks.
   - Then implement backend pieces phase by phase.
   - Finally wire them together with minimal refactors.

---

## 2. Tech Stack (Decisions)

- **Language:** Python 3.11
- **Web framework:** FastAPI (async, OpenAPI, easy to test)
- **ASGI server:** Uvicorn
- **Database:** PostgreSQL 16
- **ORM & migrations:**
  - SQLAlchemy 2.x (declarative)
  - Alembic for migrations
- **Caching / pub-sub (optional, later):** Redis
- **Blockchain / external integrations:**
  - Ethereum: `web3.py` against a free/own RPC node
  - Bitcoin: Esplora-compatible API (Blockstream / mempool.space)
  - Hyperliquid: Info HTTP API
  - Market data: CoinGecko public API
- **Background jobs:** 
  - Simple: `apscheduler` within the app process
  - Advanced (optional): Celery + Redis broker
- **Testing:** pytest + HTTPX (for API tests)

---

## 3. Repository Layout

Recommended monorepo structure:

```bash
.
  frontend/               # Next.js app (already defined)
  backend/
    app/
      api/                # FastAPI routers
      core/               # config, logging, security
      db/                 # DB session & init
      models/             # SQLAlchemy models
      schemas/            # Pydantic schemas
      services/           # business logic (whales, metrics, chains)
      workers/            # background ingestion & aggregation
    tests/
    alembic/
  infra/
    docker/               # Dockerfiles & compose
  Plan.md
  Blueprint_frontend.md
  README.md
```

---

## 4. Environment & Configuration

Define **.env** (and `.env.example`) with:

```env
# App
APP_ENV=dev
APP_PORT=8000

# Database
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=whales

# Ethereum
ETHEREUM_RPC_HTTP_URL=https://mainnet.infura.io/v3/your-key-or-other-free-rpc
ETHEREUM_RPC_WS_URL=wss://mainnet.infura.io/ws/v3/your-key-or-other-free-ws

# Bitcoin (Esplora / mempool.space)
BITCOIN_API_BASE_URL=https://mempool.space/api

# Hyperliquid
HYPERLIQUID_INFO_URL=https://api.hyperliquid.xyz/info

# CoinGecko
COINGECKO_API_BASE_URL=https://api.coingecko.com/api/v3
```

In `app/core/config.py`, load this with `pydantic-settings` or `python-dotenv`.

---

## 5. Database Schema

### 5.1 Core Tables

Use PostgreSQL with the following main tables:

#### `chains`

- `id` (PK, int)
- `slug` (text, unique) – `"ethereum" | "bitcoin" | "hyperliquid"`
- `name` (text)

#### `whales`

- `id` (PK, uuid or serial)
- `address` (text)
- `chain_id` (FK -> chains.id)
- `type` (enum: `holder`, `trader`, `holder_trader`)
- `labels` (text[]) – e.g. `{"smart_money","hyperliquid"}`
- `external_explorer_url` (text)
- `first_seen_at` (timestamptz)
- `last_active_at` (timestamptz)

Indexes:

- unique `(address, chain_id)`
- index on `last_active_at`

#### `current_wallet_metrics`

- `whale_id` (PK, FK -> whales.id)
- `roi_percent` (numeric)
- `portfolio_value_usd` (numeric)
- `realized_pnl_usd` (numeric)
- `unrealized_pnl_usd` (numeric)
- `volume_30d_usd` (numeric)
- `trades_30d` (integer)
- `win_rate_percent` (numeric)

#### `wallet_metrics_daily`

For historical charts:

- `id` (PK)
- `whale_id` (FK)
- `date` (date)
- `roi_percent` (numeric)
- `portfolio_value_usd` (numeric)
- `realized_pnl_usd` (numeric)
- `unrealized_pnl_usd` (numeric)
- `volume_1d_usd` (numeric)
- `trades_1d` (int)
- `win_rate_percent` (numeric)

Index `(whale_id, date)`.

#### `holdings`

- `id` (PK)
- `whale_id` (FK)
- `asset_symbol` (text)
- `asset_name` (text)
- `chain_id` (FK)
- `amount` (numeric)
- `value_usd` (numeric)
- `portfolio_percent` (numeric)
- `updated_at` (timestamptz)

Index `(whale_id, updated_at)`.

#### `trades`

- `id` (PK)
- `whale_id` (FK)
- `timestamp` (timestamptz)
- `chain_id` (FK)
- `source` (enum: `onchain`, `hyperliquid`, `exchange_flow`)
- `platform` (text) – `uniswap_v3`, `hyperliquid`, `binance`, etc
- `direction` (text) – `buy`, `sell`, `deposit`, `withdraw`, `long`, `short`, `close_long`, `close_short`
- `base_asset` (text, nullable)
- `quote_asset` (text, nullable)
- `amount_base` (numeric, nullable)
- `amount_quote` (numeric, nullable)
- `value_usd` (numeric)
- `pnl_usd` (numeric, nullable)
- `pnl_percent` (numeric, nullable)
- `tx_hash` (text, nullable)
- `external_url` (text, nullable)

Indexes:

- `(whale_id, timestamp DESC)`
- `(chain_id, timestamp DESC)`

#### `events`

For live feed:

- `id` (PK)
- `timestamp` (timestamptz)
- `chain_id` (FK)
- `type` (text) – `large_swap`, `large_transfer`, `exchange_flow`, `perp_trade`
- `whale_id` (FK)
- `summary` (text)
- `value_usd` (numeric)
- `tx_hash` (text, nullable)
- `details` (jsonb)

Index `timestamp DESC`.

#### `price_history`

- `id` (PK)
- `asset_symbol` (text)
- `timestamp` (timestamptz)
- `price_usd` (numeric)

Index `(asset_symbol, timestamp)`.

---

## 6. Backend Phases

### Phase 0 – Backend Skeleton & Stub API

**Objective:** Get the backend running with mock data and API shapes that the frontend expects.

#### Steps

1. **Create backend project**

   - Initialize a Python project in `backend/`.
   - Install dependencies:

     ```bash
     pip install fastapi uvicorn[standard] sqlalchemy alembic psycopg2-binary pydantic httpx web3 apscheduler python-dotenv
     ```

2. **Setup FastAPI app**

   - `app/main.py`:

     ```python
     from fastapi import FastAPI
     from app.api import router as api_router

     app = FastAPI(title="Whale Tracker API")
     app.include_router(api_router, prefix="/api/v1")

     @app.get("/health")
     async def health():
         return {"status": "ok"}
     ```

3. **Database connection**

   - `app/db/session.py`:
     - Create SQLAlchemy engine using env vars.
     - Provide `SessionLocal` or async session factory.

4. **Alembic**

   - Run `alembic init alembic`.
   - Configure `alembic.ini` to use the same DB URL as `SessionLocal`.
   - Create initial migration for tables in section 5.

5. **API routers**

   Under `app/api/` create modules:

   - `routers/dashboard.py`
   - `routers/whales.py`
   - `routers/wallets.py`
   - `routers/events.py`

   Import them in `app/api/__init__.py` and mount into main router.

6. **Stub implementations**

   For each route expected by frontend, return **static mock JSON**:

   - `GET /api/v1/dashboard/summary`
   - `GET /api/v1/whales`
   - `GET /api/v1/whales/top`
   - `GET /api/v1/wallets/{chain}/{address}`
   - `GET /api/v1/wallets/{chain}/{address}/roi-history`
   - `GET /api/v1/wallets/{chain}/{address}/portfolio-history`
   - `GET /api/v1/wallets/{chain}/{address}/trades`
   - `GET /api/v1/events/recent`
   - `GET /api/v1/events/live`

   Make sure JSON matches the types in `Blueprint_frontend.md`.

7. **Run local server**

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

8. **Connect frontend**

   - Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
   - Frontend can now be wired to these stub endpoints.

---

### Phase 1 – Ethereum Integration

**Objective:** Track Ethereum whales (initially from a static list), ingest trades, and compute their metrics.

#### 1.1 Ethereum client

- `app/services/ethereum_client.py`:

  ```python
  from web3 import Web3
  from app.core.config import settings

  w3_http = Web3(Web3.HTTPProvider(settings.eth_rpc_http_url))
  w3_ws = Web3(Web3.WebsocketProvider(settings.eth_rpc_ws_url))
  ```

- Expose helper functions:
  - `get_balance(address: str) -> int`
  - `get_block(block_number: int)`
  - `get_transaction(tx_hash: str)`
  - `get_logs(filter_params: dict)`

#### 1.2 Seed Ethereum whales

- Create `config/ethereum_whales.yaml` with an initial curated list:

  ```yaml
  - address: "0x1234..."
    labels: ["smart_money"]
  - address: "0xabcd..."
    labels: ["fund"]
  ```

- `scripts/seed_ethereum_whales.py`:
  - Load YAML.
  - Insert rows into `whales` with `chain='ethereum'` and `first_seen_at=now()`.

#### 1.3 Ethereum ingestion worker

- `app/workers/ethereum_ingestor.py`:

  - Long-lived async task:
    - Start from latest block number.
    - Subscribe to `newHeads` via WebSocket OR poll `eth_blockNumber` repeatedly.
    - For each new block:
      - Fetch full block with transactions.
      - For each tx:
        - If `from` or `to` matches a tracked whale, process it.
        - If tx interacts with known contracts (Uniswap routers, known exchanges, Hyperliquid bridge), classify accordingly.

- Logic per relevant tx:

  - Determine if it's a **swap**:
    - If `to` is a DEX router, decode input and logs (use ABI).
  - Determine if it's an **exchange deposit / withdrawal**:
    - If `to` or `from` is a known CEX deposit address.
  - Compute approximate USD value:
    - If ETH only: `value_in_eth * current_eth_price`.
    - If token: use CoinGecko price for that token.

- Insert:

  - A `trades` row with appropriate `source` and `platform`.
  - If value exceeds threshold (e.g. $500k), insert an `events` row.

- Update `whales.last_active_at`.

#### 1.4 Holdings & pricing

- `app/services/coingecko_client.py`:
  - `get_simple_price(symbols: list[str]) -> dict`
  - `get_market_chart(symbol: str, days: int) -> list[PricePoint]`

- `app/services/holdings_service.py`:
  - For each Ethereum whale:
    - Get ETH balance.
    - Get selected ERC-20 balances by calling contract `balanceOf`.
  - Convert to USD using CoinGecko.
  - Compute:
    - `portfolio_value_usd`
    - Individual `value_usd` and `portfolio_percent`.
  - Upsert into `holdings` and `current_wallet_metrics`.

#### 1.5 ROI & metrics

- Add `app/services/metrics_service.py`:

  - For each whale:
    - Compute deposits / withdrawals from transaction history.
    - Compute overall ROI:

      ```text
      ROI = (current_value + withdrawals - deposits) / deposits * 100
      ```

    - Compute realized and unrealized PnL.
    - Compute 30d volume and trades from `trades` table.
    - Estimate win-rate, if you can pair buy/sell or open/close events.

  - Store:
    - Daily snapshot in `wallet_metrics_daily`.
    - Current snapshot in `current_wallet_metrics`.

- Schedule:

  - Use `apscheduler` to run a daily job for full recalculation.
  - Optionally, run incremental updates when new trades are recorded.

---

### Phase 2 – Bitcoin Integration

**Objective:** Track BTC whales and surface large transfers and exchange flows.

#### 2.1 Bitcoin client

- `app/services/bitcoin_client.py`:

  - Base URL from env: `BITCOIN_API_BASE_URL` (e.g. `https://mempool.space/api`).
  - Use `httpx` to implement:
    - `get_address(address: str)` -> balance, basic stats
    - `get_address_txs(address: str)` -> list of recent transactions
    - Optionally, WebSocket subscribe to mempool.space for real-time tx events.

#### 2.2 Seed Bitcoin whales

- `config/bitcoin_whales.yaml` with initial addresses.
- `scripts/seed_bitcoin_whales.py` to insert them into `whales` with `chain='bitcoin'`.

#### 2.3 BTC ingestion worker

- `app/workers/bitcoin_ingestor.py`:

  - Use WebSocket or polling:
    - Every N seconds, check each whale address for new tx (or subscribe via WS).
  - For each new tx involving a whale:
    - Identify direction:
      - Whale appears in inputs -> sending.
      - Whale appears in outputs -> receiving.
    - Detect exchange flow by comparing counterpart addresses to known exchange addresses.
    - Compute value in BTC and convert to USD via CoinGecko.

  - Insert `trades` and `events` rows similar to Ethereum.
  - Update `last_active_at`.

#### 2.4 BTC holdings & metrics

- For each BTC whale:
  - Query address endpoint for total balance.
  - Convert to USD and update `holdings`.
- Extend `metrics_service` to:
  - Compute BTC whale ROI (simpler, often just current vs historical snapshots).
  - Use BTC price history from CoinGecko for ROI over time.

---

### Phase 3 – Hyperliquid Integration

**Objective:** Add derivatives trading info for whales that trade on Hyperliquid.

#### 3.1 Hyperliquid client

- `app/services/hyperliquid_client.py`:

  - Base URL: `HYPERLIQUID_INFO_URL`.
  - `async def get_clearinghouse_state(address: str) -> dict`:
    - POST body:
      ```json
      {
        "type": "clearinghouseState",
        "user": "<ETH_address>"
      }
      ```
  - `async def get_user_ledger(address: str, start_time: int | None, end_time: int | None)`:
    - Use documented ledger endpoints to retrieve PnL events.

#### 3.2 Detect Hyperliquid whales

- Keep a config entry for **Hyperliquid bridge contract** (Ethereum).
- Ethereum ingestor:
  - If a whale sends a large deposit to this contract:
    - Add `"hyperliquid"` to that whale’s `labels`.
- Optionally, maintain a separate table `hyperliquid_accounts` mapping ETH address to metadata.

#### 3.3 Hyperliquid ingestion

- `app/workers/hyperliquid_ingestor.py`:

  - Periodically (e.g. every 5 minutes) loop over whales labeled `"hyperliquid"`:
    - Fetch clearinghouse state:
      - Positions, equity, ROE.
    - Fetch recent ledger entries:
      - Realized PnL, deposits, withdrawals.

  - For positions:
    - When position size goes from 0 → nonzero:
      - Insert `trades` row: open `long` or `short`.
    - When size reduced or closed:
      - Insert `trades` row: partial/close.
      - Compute realized PnL from ledger diff.

  - Update metrics:
    - Use ROE as a direct measurement of Hyperliquid account ROI.
    - Add Hyperliquid volume and PnL into aggregated wallet metrics.

---

### Phase 4 – Real API Implementation

**Objective:** Replace stubs with real database-driven endpoints that match the frontend contracts.

#### 4.1 Dashboard

- `GET /api/v1/dashboard/summary`:

  - `total_tracked_whales`:
    - `SELECT COUNT(*) FROM whales;`
  - `active_whales_24h`:
    - `WHERE last_active_at >= now() - interval '24 hours'`
  - `total_volume_24h_usd`:
    - Sum of `value_usd` from `trades` for last 24h.
  - `hyperliquid_whales`:
    - Count `whales` with `labels` array containing `"hyperliquid"`.

#### 4.2 Whales list

- `GET /api/v1/whales`:

  - Join `whales` + `current_wallet_metrics`.
  - Filters from query params:
    - `chain` -> filter by `chains.slug`.
    - `type` -> `whales.type`.
    - `minRoi` -> `current_wallet_metrics.roi_percent >= value`.
    - `activityWindow` -> `last_active_at >= now() - X interval`.
    - `search` -> if valid address, filter `whales.address`, otherwise `labels ILIKE %search%`.
  - Sorting:
    - `sortBy` -> map to appropriate column.
  - Pagination:
    - Use `limit` and `offset`.
  - Return `items` + `total`.

- `GET /api/v1/whales/top`:
  - Same as `/whales` with defaults: 
    - `sortBy=roi`, `limit=10`.

#### 4.3 Wallet detail

- `GET /api/v1/wallets/{chain}/{address}`:

  - Resolve `chain` string to `chain_id`.
  - Find whale by `(chain_id, address)`.
  - Query `current_wallet_metrics` and `holdings`.
  - Compose JSON with:
    - `wallet` (address, labels, explorer URL)
    - `metrics` (ROI, PnL, volume, etc.)
    - `holdings` (array)
    - `notes` (optional summary string, can be simple at first).

- `GET /api/v1/wallets/{chain}/{address}/roi-history`:

  - Use `wallet_metrics_daily` filtered by `whale_id` and `date >= now - days`.
  - Return `points` as `{ timestamp, roi_percent }`.

- `GET /api/v1/wallets/{chain}/{address}/portfolio-history`:

  - Same table, using `portfolio_value_usd`.

#### 4.4 Trades & events

- `GET /api/v1/wallets/{chain}/{address}/trades`:

  - Resolve whale.
  - Filter `trades` by `whale_id` and optional `source`.
  - Order by `timestamp DESC`.
  - Implement cursor pagination:
    - If `cursor` is provided, decode to `(timestamp, id)` and add condition `timestamp < ts OR (timestamp = ts AND id < id)`.
  - Return `items` and `next_cursor` if more rows exist.

- `GET /api/v1/events/recent` and `GET /api/v1/events/live`:

  - Query `events` ordered by timestamp desc.
  - Restrict to `limit` items.
  - For `/live`, you can filter to last 1h or last N events.

---

### Phase 5 – WebSocket Live Feed

**Objective:** Allow the frontend `/live` page to receive new whale events in real time.

#### 5.1 WebSocket route

- In `app/api/ws.py`:

  ```python
  from fastapi import APIRouter, WebSocket, WebSocketDisconnect

  router = APIRouter()
  active_connections: set[WebSocket] = set()

  @router.websocket("/ws/live")
  async def live_ws(websocket: WebSocket):
      await websocket.accept()
      active_connections.add(websocket)
      try:
          while True:
              await websocket.receive_text()  # keep connection open
      except WebSocketDisconnect:
          active_connections.remove(websocket)
  ```

- Add router to app:

  ```python
  app.include_router(ws.router)
  ```

#### 5.2 Broadcasting events

- Create `app/services/live_broadcaster.py`:

  - Manage `active_connections`.
  - Provide `async def broadcast(event: dict)`.

- In ingestion workers (Ethereum, Bitcoin, Hyperliquid):

  - Whenever a new `events` row is inserted and `value_usd` > configured threshold:
    - Build `LiveEvent` payload (matching frontend type).
    - Call `broadcast(payload)`.

---

### Phase 6 – Classification & Periodic Jobs

**Objective:** Keep whale classification and metrics current.

#### 6.1 Whale classification

- `app/workers/whale_classifier.py`:

  - Runs daily.
  - For each whale:
    - Compute average trade size, volume vs portfolio value, and holding periods.
    - Assign:
      - `holder` if low trade frequency, large portfolio.
      - `trader` if high trade frequency/volume.
      - `holder_trader` if both thresholds hit.
  - Update `whales.type`.

#### 6.2 Scheduler

- Use `apscheduler`:

  - On app startup, schedule jobs:
    - `metrics_aggregator` – run daily or every few hours.
    - `whale_classifier` – daily.
    - `price_updater` – e.g. every 5 minutes for major assets.
  - Ensure long-running ingestion workers run in separate process or background tasks managed by your process manager (e.g. systemd or Docker).

---

## 7. Integration with Frontend

### 7.1 Local dev workflow

1. Start Postgres (example using Docker):

   ```bash
   docker run --name whale-postgres      -e POSTGRES_PASSWORD=postgres      -e POSTGRES_DB=whales      -p 5432:5432 -d postgres:16
   ```

2. Apply migrations:

   ```bash
   alembic upgrade head
   ```

3. Seed chains and whales:

   - `python scripts/seed_chains.py`
   - `python scripts/seed_ethereum_whales.py`
   - `python scripts/seed_bitcoin_whales.py`

4. Run backend:

   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

5. Run frontend:

   ```bash
   cd frontend
   npm run dev
   ```

### 7.2 Replacing mocks

- Once backend endpoints are implemented:

  - Remove mocked data in frontend hooks/services.
  - Ensure all hooks call the real API URLs.
  - Fix any type mismatches by aligning backend Pydantic schemas and frontend TypeScript types.

- Run end-to-end tests to validate:
  - Dashboard renders real data.
  - Whales list filters correctly.
  - Wallet detail shows real trades and charts.
  - Live feed receives WebSocket events.

---

## 8. Master Checklist

### Backend Core

- [ ] Initialize FastAPI project and DB connection
- [ ] Configure Alembic and create initial migration
- [ ] Define SQLAlchemy models for all tables
- [ ] Implement stub API endpoints for all frontend contracts

### Ethereum

- [ ] Implement Ethereum client
- [ ] Seed initial Ethereum whales
- [ ] Implement Ethereum ingestion worker (tx scanning, trade classification)
- [ ] Implement holdings calculation and price integration
- [ ] Implement ROI and metrics aggregation for Ethereum whales

### Bitcoin

- [ ] Implement Bitcoin Esplora client
- [ ] Seed initial Bitcoin whales
- [ ] Implement BTC ingestion worker
- [ ] Implement BTC holdings & metrics aggregation

### Hyperliquid

- [ ] Implement Hyperliquid Info client
- [ ] Detect Hyperliquid whales via bridge activity
- [ ] Implement Hyperliquid ingestion worker (positions, PnL)
- [ ] Integrate Hyperliquid metrics into overall wallet metrics

### API & WebSocket

- [ ] Replace stub endpoints with real DB queries
- [ ] Implement pagination & filters for `/whales` and `/trades`
- [ ] Implement dashboard summary endpoint
- [ ] Implement events endpoints (`recent`, `live`)
- [ ] Implement WebSocket `/ws/live` and broadcasting

### Classification & Jobs

- [ ] Implement whale type classifier
- [ ] Implement scheduled metrics & classification jobs
- [ ] Implement price updater job

### Integration & Production

- [ ] Wire frontend to real backend URLs
- [ ] Add logging and error handling in workers
- [ ] Dockerize backend and frontend
- [ ] Add basic monitoring/alerting
- [ ] Document deployment procedure and operational runbooks

---

This `Plan.md` is intended to be executable as a roadmap: if you work through the checklist phase by phase, you’ll end up with a backend that cleanly powers the frontend described in `Blueprint_frontend.md`, and a complete whale-tracking system that can be iterated and scaled over time.
