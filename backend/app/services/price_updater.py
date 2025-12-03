from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import PriceHistory
from app.services.coingecko_client import coingecko_client


ASSETS = ["bitcoin", "ethereum"]


def update_prices(session: Session) -> None:
    prices = coingecko_client.get_simple_price(ASSETS)
    now = datetime.now(timezone.utc)
    for asset in ASSETS:
        price = prices.get(asset)
        if price is None:
            continue
        session.add(
            PriceHistory(
                asset_symbol=asset.upper(),
                timestamp=now,
                price_usd=price,
            )
        )
    session.commit()
