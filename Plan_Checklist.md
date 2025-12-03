# Backend & Integration Checklist

Goal: Track progress across backend phases to match `Blueprint_frontend.md` and keep frontend contracts stable.

## Tech Stack
- [ ] Confirm Python 3.11, FastAPI, Uvicorn
- [ ] Confirm PostgreSQL 16 and SQLAlchemy 2.x + Alembic
- [ ] Confirm Redis (optional later) for caching/pub-sub
- [ ] Confirm HTTP clients: httpx, web3.py, CoinGecko, Esplora, Hyperliquid Info (httpx/web3/CoinGecko + mempool.space + Hyperliquid client present; still to validate)
- [x] Confirm background jobs choice (`apscheduler` now, Celery optional later)
- [ ] Confirm testing stack: pytest + HTTPX

## Repository Layout
- [x] Create `backend/app` with `api`, `core`, `db`, `models`, `schemas`, `services`, `workers`
- [x] Create `backend/tests` and `backend/alembic`
- [ ] Prepare `infra/docker` for runtime images/compose
- [ ] Keep top-level docs: `Plan.md`, `Blueprint_frontend.md`, `README.md` (README missing)

## Environment & Configuration
- [x] Add `.env` and `.env.example` with app, DB, Ethereum, Bitcoin, Hyperliquid, CoinGecko URLs
- [x] Default local DB uses SQLite file (`DATABASE_URL=sqlite:///./data/whales.db`)
- [x] Load settings in `app/core/config.py` via `pydantic-settings` or `python-dotenv`
- [x] Wire DB URL and secrets into Alembic config

## Database Schema
- [x] Create `chains` table (id, slug, name)
- [x] Create `whales` table (address, chain_id, type, labels[], explorer URL, first/last active)
- [x] Create `current_wallet_metrics` table
- [x] Create `wallet_metrics_daily` table
- [x] Create `holdings` table
- [x] Create `trades` table with indexes for whale and chain timestamps
- [x] Create `events` table for live feed
- [x] Create `price_history` table

## Phase 0 Лил Backend Skeleton & Stub API
- [x] Initialize Python project in `backend/`
- [x] Install base deps: fastapi, uvicorn[standard], sqlalchemy, alembic, psycopg2-binary, pydantic, httpx, web3, apscheduler, python-dotenv
- [x] Add FastAPI app at `app/main.py` with `/health` and router include
- [x] Add DB session factory in `app/db/session.py`
- [x] Init Alembic and align config with DB URL
- [x] Create routers under `app/api/` (`dashboard`, `whales`, `wallets`, `events`) and mount
- [x] Provide API endpoints for frontend contracts (DB-backed; not static stubs):
  - [x] `GET /api/v1/dashboard/summary`
  - [x] `GET /api/v1/whales`
  - [x] `GET /api/v1/whales/top`
  - [x] `GET /api/v1/wallets/{chain}/{address}`
  - [x] `GET /api/v1/wallets/{chain}/{address}/roi-history`
  - [x] `GET /api/v1/wallets/{chain}/{address}/portfolio-history`
  - [x] `GET /api/v1/wallets/{chain}/{address}/trades`
  - [x] `GET /api/v1/events/recent`
  - [x] `GET /api/v1/events/live`
- [ ] Run `uvicorn app.main:app --reload --port 8000` locally (not verified)
- [ ] Point frontend to `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` (not verified)

## Phase 1 Лил Ethereum Integration
- [x] Implement Ethereum client (`app/services/ethereum_client.py`) with HTTP+WS providers
- [x] Seed `config/ethereum_whales.yaml` and import via `scripts/seed_ethereum_whales.py`
- [x] Build Ethereum ingestion worker (new blocks, whale tx detection, swap/exchange classification) — native ETH + ERC20 Transfer log ingestion (receipt-based) with swap decoding and exchange/bridge heuristics
- [x] Compute USD values using CoinGecko and known contracts (ETH + expanded ERC20 prices; dynamic contract lookup fallback)
- [x] Insert trades/events; update whale `last_active_at`
- [x] Build holdings service (ETH + ERC20 balances) and USD conversion
- [x] Persist holdings into `holdings` and `current_wallet_metrics`
- [x] Implement ROI/metrics aggregation and daily snapshots (`wallet_metrics_daily`) (per-asset cost basis, unrealized, win-rate)
- [x] Schedule daily metrics job (apscheduler) and optional incremental updates (5-min holdings/metrics refresh)

## Phase 2 Лил Bitcoin Integration
- [x] Implement Bitcoin Esplora client (`app/services/bitcoin_client.py`) (mempool.space client)
- [x] Seed `config/bitcoin_whales.yaml` via `scripts/seed_bitcoin_whales.py`
- [x] Build BTC ingestion worker (poll or WS), classify direction and exchange flows (deposit/withdraw + broader exchange-flow heuristics added)
- [x] Compute USD values from CoinGecko; insert trades/events; update `last_active_at` (events now emitted)
- [x] Update holdings & metrics for BTC whales; extend ROI calculations (holdings present; ROI/metrics live via cost basis)

## Phase 3 Лил Hyperliquid Integration
- [x] Implement Hyperliquid client (`app/services/hyperliquid_client.py`)
- [x] Detect Hyperliquid whales (bridge contract deposits add `hyperliquid` label) (label added when ledger/positions found)
- [x] Build Hyperliquid ingestion worker (positions, ledger, PnL) (ledger ingestion with dedupe by ledger id; positions mapped into holdings/events)
- [x] Map position changes to trades; compute realized PnL from ledger (ledger->trade with ledger_id stored; side/size/price mapped)
- [x] Integrate Hyperliquid metrics into wallet metrics (via holdings/metrics recompute)

## Phase 4 Лил Real API Implementation
- [x] Replace stub endpoints with DB-backed queries
- [x] Implement `/api/v1/dashboard/summary` aggregates
- [x] Implement `/api/v1/whales` with filters, sort, pagination
- [x] Implement `/api/v1/whales/top` defaults (sort ROI, limit 10)
- [x] Implement wallet detail endpoints (metrics, holdings, notes)
- [x] Implement ROI history and portfolio history from `wallet_metrics_daily`
- [x] Implement trades endpoint with cursor pagination and optional source filter (cursor pagination added)
- [x] Implement events endpoints (`recent`, `live` windowed)
- [x] Connect frontend pages to live API responses (dashboard, whales list, whale detail, live feed)

## Phase 5 Лил WebSocket Live Feed
- [x] Add `/ws/live` route and connection tracking
- [x] Add broadcaster service to fan out events
- [x] Broadcast new high-value events from ingestion workers

## Phase 6 Лил Classification & Scheduled Jobs
- [x] Add whale classifier worker (holder/trader/holder_trader) with thresholds
- [x] Add scheduled jobs: metrics aggregator, classifier, price updater
- [x] Ensure long-running workers are managed separately (process manager / Docker) (scheduler + ingestors togglable via env)

## Integration with Frontend
- [x] Local dev loop: run against SQLite file, apply Alembic migrations, seed chains (`scripts/seed_chains.py`) and whales (`scripts/seed_ethereum_whales.py`), run backend, run frontend (documented in backend/README.md)
- [x] Replace frontend mocks with real API URLs once endpoints are live (frontend `.env` points to `http://localhost:8000`)
- [x] Align backend Pydantic schemas and frontend TS types; fix mismatches
- [x] Add basic logging and error handling in workers
- [ ] Dockerize backend and frontend
- [ ] Add monitoring/alerting and document deployment/runbooks

## PostgreSQL Final Pass
- [ ] Switch `DATABASE_URL` to Postgres per Plan.md, rerun Alembic migrations, and validate API endpoints against Postgres
