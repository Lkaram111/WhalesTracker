# Fix checklist (whale tracker)

## Snapshot from repo (based on backend/data/whales.db)
- Latest trades are stale: Hyperliquid last at 2025-12-03 16:10:39, Ethereum last at 2025-12-03 14:10:47 (`select max(timestamp) from trades`).
- `wallet_metrics_daily` has only 36 rows (one per whale) and all are for 2025-12-03, so ROI/portfolio charts have no history.
- `ingestion_checkpoints` table migration added (needs `alembic upgrade head` to apply).
- Frontend API base URL now uses `VITE_API_BASE_URL` with `.env.example` added.
- Trades now enforce unique `(whale_id, tx_hash)` via index.

## Data freshness and ingestion (highest priority)
- [x] Add an Alembic migration for `ingestion_checkpoints` (see `app/models/tables.py`) and rerun `alembic upgrade head` so Hyperliquid cursors persist.
- [ ] Run ingestors as dedicated processes (or confirm `ENABLE_INGESTORS=true` with FastAPI lifespan actually starts them in prod). Add startup logs to prove Ethereum/Bitcoin/Hyperliquid loops are running.
- [x] Hyperliquid: fetch fills newer than `checkpoint.last_fill_time`, filter out old ones, and ingest oldest -> newest each tick.
- [x] Hyperliquid: stop skipping wallets without labels; always ingest by chain. Persist and reuse `last_fill_time`/`last_position_time`.
- [x] Hyperliquid: store signed sizes (no `abs`); recompute metrics after ingest.
- [ ] Ethereum: track last processed block height (DB checkpoint) and iterate sequentially; polling only `"latest"` drops every block mined between polls. Implement historical backfill for existing whales.
- [ ] Ethereum: avoid scanning full blocks + receipts; use `eth_getLogs` filters for tracked whale addresses/topics or a mempool/subscription feed. Add retry/backoff on Infura errors.
- [ ] Bitcoin: add a checkpoint (last_seen_txid or block height) and paginate beyond `limit=20`; back off on HTTP 429/5xx from mempool.space.

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
- [ ] Add tests for: Hyperliquid/Ethereum dedupe and checkpointing, ROI/portfolio history rebuild, trades pagination with `cursor`, and API filtering by `source/direction`.
- [x] Document runbooks in `backend/README.md`: how to start ingestors, run backfill, and verify freshness (sample SQL: `select max(timestamp) from trades`).

## Next actions to run now
- [x] Apply migration: `cd backend && alembic upgrade head` (done; `ingestion_checkpoints` and unique trade index applied).
- [ ] Restart backend with `ENABLE_INGESTORS=true ENABLE_SCHEDULER=true` and confirm Hyperliquid/Ethereum/Bitcoin ingestor logs show ticks.
- [ ] Backfill history: run the Hyperliquid/Bitcoin/Ethereum backfill routines (or the per-wallet reset for Hyperliquid) to repopulate trades and rebuild `wallet_metrics_daily`.
- [ ] Recompute metrics/history after backfill: call `rebuild_portfolio_history_from_trades` or trigger the scheduler job; verify charts show multiple dates.
