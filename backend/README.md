# Whale Tracker Backend

## Dev loop
- Python 3.11+ with `pip install -r requirements.txt`
- Copy `.env.example` to `.env`, adjust RPC/API keys; defaults point to local SQLite at `./data/whales.db`.
- Create schema: `alembic upgrade head`
- Seed chains/whales: `python scripts/seed_chains.py` then `python scripts/seed_ethereum_whales.py` and `python scripts/seed_bitcoin_whales.py`
- Run API: `uvicorn app.main:app --reload --port 8000` (frontend uses `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`)
- Optional: disable background jobs for tests with `ENABLE_INGESTORS=false ENABLE_SCHEDULER=false`
- For Hyperliquid S3 paid imports: set `AWS_PROFILE=hl-requester` (or configure AWS credentials) to access requester-pays S3 bucket
- Adding whales now triggers an async backfill; responses return immediately with the whale `id`. Frontend can poll `/api/v1/whales/{whale_id}/backfill_status` to show progress (0-100) while historical data is imported.
- Hyperliquid wallets can be fully reset/re-synced via `POST /api/v1/whales/{whale_id}/reset_hyperliquid`; it wipes trades/events/holdings/metrics then re-imports with progress visible via the same status endpoint.
- Hyperliquid ingestion is incremental: we store the last ingested fill time per wallet and only fetch newer fills on subsequent runs.
- Any wallet can be re-backfilled without wiping data via `POST /api/v1/whales/{whale_id}/backfill` (returns `BackfillStatus`).

## Runbook (freshness & verification)
- Start API with ingestors/scheduler: `ENABLE_INGESTORS=true ENABLE_SCHEDULER=true uvicorn app.main:app --reload --port 8000`
- Check migrations applied: `alembic current`; apply with `alembic upgrade head`.
- Verify ingestion health:
  - Hyperliquid: watch logs for `Hyperliquid ingestor start` ticks; ensure `ingestion_checkpoints` rows grow.
  - Ethereum/Bitcoin: logs should show ingestion ticks; confirm latest trade timestamps advance: `select max(timestamp) from trades;`
- Backfill a wallet: `POST /api/v1/whales/{id}/backfill` (or reset for Hyperliquid via `/reset_hyperliquid`). Poll `/backfill_status`.
- Rebuild chart history if empty: call `GET /api/v1/wallets/{chain}/{address}/roi-history` and `/portfolio-history`; they trigger rebuilds when missing.

## Frontend integration
-Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
- Frontend `.env` already points to `http://localhost:8000`.
- API CORS is open; run backend first, then frontend at `127.0.0.1:8080`.
- Websocket live feed: connect to `ws://localhost:8000/api/v1/events/ws/live`.

## Tests
Run `pytest` from `backend/` (smoke tests cover health and core API responses). Enable/disable ingestors via env as above.


## This is the command to download from hyperliquid s3

cd "C:\Users\Elie Karam\OneDrive - REANOVA\Bureau\Perso\Whale\backend"
$env:AWS_PROFILE = 'hl-requester'

@'
from datetime import date
from app.db.session import SessionLocal
from app.models import Whale
from app.services.hyperliquid_paid_import import import_hl_history_from_s3

addr = "0x7839e2f2c375dd2935193f2736167514efff9916"

# 01/12/2025 to 02/12/2025 (inclusive)
start = date(2025, 12, 1)
end   = date(2025, 12, 2)

with SessionLocal() as session:
    whale = session.query(Whale).filter(Whale.address.ilike(addr)).first()
    if not whale:
        raise SystemExit("Whale not found")
    result = import_hl_history_from_s3(session, whale, start, end)
    print(result)
'@ | python -