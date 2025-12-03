from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class BitcoinClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = base_url or settings.bitcoin_api_base_url
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def get_address(self, address: str) -> dict[str, Any]:
        with self._client() as client:
            resp = client.get(f"/address/{address}")
            resp.raise_for_status()
            return resp.json()

    def get_address_txs(self, address: str, limit: int = 25) -> list[dict[str, Any]]:
        with self._client() as client:
            resp = client.get(f"/address/{address}/txs", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()


bitcoin_client = BitcoinClient()
