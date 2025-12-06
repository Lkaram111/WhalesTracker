from __future__ import annotations

import argparse
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.services.price_service import fetch_and_store_binance_prices


def parse_dt(val: str | None) -> datetime | None:
    if not val:
        return None
    return datetime.fromisoformat(val).astimezone(timezone.utc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Binance prices via ccxt and store to price_history.")
    parser.add_argument("--assets", required=True, help="Comma-separated asset symbols, e.g. BTC,ETH,SOL")
    parser.add_argument("--timeframe", default="1h", help="ccxt timeframe (default: 1h)")
    parser.add_argument("--since", help="ISO datetime UTC start (e.g., 2025-01-01T00:00:00Z)")
    parser.add_argument("--until", help="ISO datetime UTC end (e.g., 2025-02-01T00:00:00Z)")
    parser.add_argument("--limit", type=int, default=1500, help="Max candles per request")
    args = parser.parse_args()

    assets = [a.strip() for a in args.assets.split(",") if a.strip()]
    if not assets:
        raise SystemExit("No assets provided")

    since = parse_dt(args.since)
    until = parse_dt(args.until)

    with SessionLocal() as session:
        written = fetch_and_store_binance_prices(
            session,
            assets=assets,
            timeframe=args.timeframe,
            since=since,
            until=until,
            limit=args.limit,
        )
        session.commit()
        print(f"Wrote {written} price rows for assets: {', '.join(assets)}")


if __name__ == "__main__":
    main()
