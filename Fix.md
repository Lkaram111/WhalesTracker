# Fix checklist (whale tracker)

## Snapshot from repo (based on backend/data/whales.db)
- Latest trades now at 2025-12-04 09:38:38 (Hyperliquid). Ethereum/Bitcoin wallets and seeds removed for now.
- Non-HL data cleaned from trades/events/holdings; only 3 Hyperliquid wallets remain.
- `wallet_metrics_daily` rebuilt to 9 rows across the 3 Hyperliquid wallets (dates span 2025-12-01..2025-12-04).
- `ingestion_checkpoints` table migration added (applied).
- Frontend API base URL uses `VITE_API_BASE_URL` with `.env.example`.
- Trades enforce unique `(whale_id, tx_hash)` via index.

## Data freshness and ingestion (highest priority)
- [x] Add an Alembic migration for `ingestion_checkpoints` (see `app/models/tables.py`) and rerun `alembic upgrade head` so Hyperliquid cursors persist.
- [ ] Run ingestors as dedicated processes (or confirm `ENABLE_INGESTORS=true` with FastAPI lifespan actually starts them in prod). Add startup logs to prove Hyperliquid loops are running.
- [x] Hyperliquid: fetch fills newer than `checkpoint.last_fill_time`, filter out old ones, ingest oldest -> newest; dedupe tx hashes before insert; stop skipping wallets without labels; store signed sizes; recompute metrics after ingest.
- [ ] Ethereum: track last processed block height and iterate sequentially; polling only `"latest"` drops blocks. Implement historical backfill (disabled for now; seeds removed).
- [ ] Ethereum: avoid scanning full blocks + receipts; use `eth_getLogs` filters or WS; add retry/backoff on provider errors.
- [ ] Bitcoin: add a checkpoint (last_seen_txid or block height) and paginate beyond `limit=20`; back off on HTTP 429/5xx (disabled for now; seeds removed).

## Metrics and history correctness
- [x] Rebuild `wallet_metrics_daily` for every whale from trades (`rebuild_portfolio_history_from_trades`) and schedule a daily snapshot job; keep ROI/volume per day instead of only today (nightly cron added).
- [x] Make `/api/v1/wallets/{chain}/{address}/roi-history` rebuild data when empty (like portfolio-history does) so charts are not blank.
- [ ] Refresh holdings before recomputing metrics; for perps, use signed sizes + mark/entry px for unrealized/realized PnL.
- [x] Add a uniqueness constraint or upsert on `trades` (e.g., `whale_id + tx_hash`) to avoid duplicates when ingestors replay blocks/fills.
- [ ] Persist `price_history` for tracked assets and use it for historical valuations rather than cumulative trade value.

## Frontend and UX
- [x] Rename env var in `src/lib/apiClient.ts` to `VITE_API_BASE_URL` and add `Frontend/.env.example`; ensure builds pick the correct API host.
- [x] Show error banners for failed API calls (trades) and display “last refreshed” with a manual refresh button (bump `refreshKey`).
- [x] Auto-poll trades/positions/backfill status while a whale page is open so users see new activity without a full reload.
- [x] Handle empty history gracefully: show “no data yet” on charts when `< 2` points instead of filling with zeroes.
- [x] Expose a “recompute/backfill” action for non-Hyperliquid whales (or at least surface current backfill status).

## Observability and tests
- [x] Add ingestion heartbeats/metrics (latest trade per chain + last daily snapshot) via `/api/v1/dashboard/ingestion-status`.
- [ ] Add tests for: Hyperliquid dedupe and checkpointing, ROI/portfolio history rebuild, trades pagination with `cursor`, and API filtering by `source/direction`.
- [x] Document runbooks in `backend/README.md`: how to start ingestors, run backfill, and verify freshness (sample SQL: `select max(timestamp) from trades`).

## Next actions to run now
- [x] Apply migration: `cd backend && alembic upgrade head` (done; `ingestion_checkpoints` and unique trade index applied).
- [ ] Restart backend with `ENABLE_INGESTORS=true ENABLE_SCHEDULER=true` and confirm Hyperliquid ingestor logs show ticks.
- [ ] Backfill history: run Hyperliquid backfill/reset as needed to repopulate trades and rebuild `wallet_metrics_daily`.
- [ ] Recompute metrics/history after backfill: call `rebuild_portfolio_history_from_trades` or trigger the scheduler job; verify charts show multiple dates.
