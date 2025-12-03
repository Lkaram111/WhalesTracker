from __future__ import annotations

from typing import Any, Iterable

import httpx

from app.core.config import settings


class CoinGeckoClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = base_url or settings.coingecko_api_base_url
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def get_simple_price(self, symbols: Iterable[str], vs_currency: str = "usd") -> dict[str, float]:
        symbols_list = list(symbols)
        if not symbols_list:
            return {}
        with self._client() as client:
            resp = client.get(
                "/simple/price",
                params={"ids": ",".join(symbols_list), "vs_currencies": vs_currency},
            )
            resp.raise_for_status()
            data: dict[str, dict[str, Any]] = resp.json()
            return {k: float(v.get(vs_currency, 0)) for k, v in data.items()}

    def get_market_chart(self, symbol: str, days: int = 30, vs_currency: str = "usd") -> list[tuple[float, float]]:
        with self._client() as client:
            resp = client.get(
                f"/coins/{symbol}/market_chart",
                params={"vs_currency": vs_currency, "days": days},
            )
            resp.raise_for_status()
            data = resp.json()
            prices = data.get("prices", [])
            return [(float(ts), float(price)) for ts, price in prices]

    def get_contract_price(self, chain: str, contract_address: str, vs_currency: str = "usd") -> float | None:
        with self._client() as client:
            try:
                resp = client.get(f"/coins/{chain}/contract/{contract_address}")
                resp.raise_for_status()
                data = resp.json()
                market_data = data.get("market_data", {})
                price = market_data.get("current_price", {}).get(vs_currency)
                return float(price) if price is not None else None
            except Exception:
                return None


coingecko_client = CoinGeckoClient()
