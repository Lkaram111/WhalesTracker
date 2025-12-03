# Whale Tracker Backend

## Dev loop
- Python 3.11+ with `pip install -r requirements.txt`
- Copy `.env.example` to `.env`, adjust RPC/API keys; defaults point to local SQLite at `./data/whales.db`.
- Create schema: `alembic upgrade head`
- Seed chains/whales: `python scripts/seed_chains.py` then `python scripts/seed_ethereum_whales.py` and `python scripts/seed_bitcoin_whales.py`
- Run API: `uvicorn app.main:app --reload --port 8000` (frontend uses `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`)
- Optional: disable background jobs for tests with `ENABLE_INGESTORS=false ENABLE_SCHEDULER=false`

## Frontend integration
- Frontend `.env` already points to `http://localhost:8000`.
- API CORS is open; run backend first, then frontend at `127.0.0.1:8080`.
- Websocket live feed: connect to `ws://localhost:8000/api/v1/events/ws/live`.

## Tests
Run `pytest` from `backend/` (smoke tests cover health and core API responses). Enable/disable ingestors via env as above.
