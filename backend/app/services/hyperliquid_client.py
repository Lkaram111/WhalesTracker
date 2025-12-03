from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class HyperliquidClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        # Accept either full /info URL or host; normalize to host and always POST to /info
        self.base_url = (base_url or settings.hyperliquid_info_url).rstrip("/info").rstrip("/")
        self.timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def get_clearinghouse_state(self, address: str) -> dict[str, Any]:
        payload = {"type": "clearinghouseState", "user": address}
        with self._client() as client:
            resp = client.post("/info", json=payload)
            resp.raise_for_status()
            return resp.json()

    def get_user_fills(self, address: str, start_time: int | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"type": "userFills", "user": address}
        if start_time is not None:
            payload["startTime"] = start_time
        with self._client() as client:
            resp = client.post("/info", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else []

    def get_user_fills_paginated(
        self,
        address: str,
        start_time: int | None = None,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch paginated user fills backwards in time using startTime.

        Hyperliquid returns up to ~2000 fills per call. We walk backwards by setting
        startTime to the oldest fill time minus one until we exhaust results or hit
        max_pages.
        """
        all_fills: list[dict[str, Any]] = []
        cursor = start_time
        for _ in range(max_pages):
            batch = self.get_user_fills(address, cursor)
            if not batch:
                break
            all_fills.extend(batch)
            times = [f.get("time") for f in batch if f.get("time") is not None]
            if not times:
                break
            cursor = min(times) - 1  # walk backward in time
            # If we received fewer than 2000, likely no more pages
            if len(batch) < 2000:
                break
        return all_fills

    def get_user_ledger(self, address: str, start_time: int | None = None, end_time: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": "userLedger", "user": address}
        if start_time is not None:
            payload["startTime"] = start_time
        if end_time is not None:
            payload["endTime"] = end_time
        with self._client() as client:
            resp = client.post("/info", json=payload)
            resp.raise_for_status()
            return resp.json()


hyperliquid_client = HyperliquidClient()
