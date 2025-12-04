from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, Sequence

import ccxt  # type: ignore
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import PriceHistory


def _exchange_symbol(asset: str) -> str:
    """Map internal asset symbol to Binance market symbol."""
    # Default to USDT quoting; adjust here if you need per-asset overrides.
    base = asset.upper()
    return f"{base}/USDT"


def _upsert_price(session: Session, asset: str, ts: datetime, price: Decimal) -> None:
    payload = {
        "asset_symbol": asset.upper(),
        "timestamp": ts,
        "price_usd": price,
    }
    # Manual upsert (no composite unique on price_history)
    existing = (
        session.query(PriceHistory)
        .filter(
            PriceHistory.asset_symbol == payload["asset_symbol"],
            PriceHistory.timestamp == payload["timestamp"],
        )
        .one_or_none()
    )
    if existing:
        existing.price_usd = payload["price_usd"]
    else:
        session.add(PriceHistory(**payload))


def fetch_and_store_binance_prices(
    session: Session,
    assets: Sequence[str],
    timeframe: str = "1h",
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 1000,
) -> int:
    """
    Fetch OHLCV closes from Binance via ccxt for the given assets and persist to price_history.

    Args:
        session: SQLAlchemy session.
        assets: Iterable of asset symbols (e.g., ["BTC", "ETH"]).
        timeframe: ccxt timeframe (e.g., "1h", "4h", "1d").
        since: Optional start datetime (UTC); defaults to None (Binance default).
        until: Optional end datetime (UTC); used to stop pagination.
        limit: Max candles per ccxt call (Binance supports up to 1500 depending on market/timeframe).

    Returns:
        int: Number of price rows written/upserted.
    """
    exchange = ccxt.binance({"enableRateLimit": True})
    written = 0
    since_ms = int(since.timestamp() * 1000) if since else None
    until_ms = int(until.timestamp() * 1000) if until else None

    for asset in assets:
        try:
            market = _exchange_symbol(asset)
            cursor = since_ms
            while True:
                ohlcv = exchange.fetch_ohlcv(market, timeframe=timeframe, since=cursor, limit=limit)
                if not ohlcv:
                    break
                for ts_ms, _, _, _, close, _ in ohlcv:
                    ts = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    if until_ms and ts_ms > until_ms:
                        break
                    try:
                        price = Decimal(close)
                    except Exception:
                        continue
                    _upsert_price(session, asset, ts, price)
                    written += 1
                if len(ohlcv) < limit:
                    break
                # paginate
                cursor = ohlcv[-1][0] + 1
                if until_ms and cursor > until_ms:
                    break
        except Exception:
            continue
    return written
