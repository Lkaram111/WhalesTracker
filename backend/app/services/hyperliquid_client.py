from __future__ import annotations

from typing import Any
import threading
import time

import httpx
from httpx import HTTPStatusError, RequestError

from app.core.config import settings


class HyperliquidClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        # Accept either full /info URL or host; normalize to host and always POST to /info
        self.base_url = (base_url or settings.hyperliquid_info_url).rstrip("/info").rstrip("/")
        self.timeout = timeout
        self.max_rps = max(0.1, float(getattr(settings, "hyperliquid_max_rps", 3.0) or 3.0))
        self._min_interval = 1.0 / self.max_rps
        self._last_request_ts = 0.0
        self._lock = threading.Lock()
        self._max_retries = 3

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.perf_counter()
            sleep_for = self._min_interval - (now - self._last_request_ts)
            if sleep_for > 0:
                time.sleep(sleep_for)
            self._last_request_ts = time.perf_counter()

    @staticmethod
    def _retry_after_seconds(headers: httpx.Headers) -> float:
        try:
            return float(headers.get("Retry-After", "0") or 0)
        except Exception:
            return 0.0

    def _post_info(self, payload: dict[str, Any]) -> Any:
        """POST to /info with global rate limiting and limited retries on 429/5xx."""
        last_err: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            self._throttle()
            try:
                with self._client() as client:
                    resp = client.post("/info", json=payload)
                resp.raise_for_status()
                return resp.json()
            except HTTPStatusError as exc:  # noqa: PERF203
                status = exc.response.status_code
                retry_after = self._retry_after_seconds(exc.response.headers)
                last_err = exc
                if status in (429, 502, 503, 504) and attempt < self._max_retries:
                    # Respect server-provided Retry-After if present; otherwise exponential backoff.
                    delay = max(retry_after, min(30.0, 2.0**attempt))
                    time.sleep(delay)
                    continue
                raise
            except RequestError as exc:
                last_err = exc
                if attempt < self._max_retries:
                    time.sleep(min(30.0, 2.0**attempt))
                    continue
                raise
        if last_err:
            raise last_err

    def get_clearinghouse_state(self, address: str) -> dict[str, Any]:
        payload = {"type": "clearinghouseState", "user": address}
        data = self._post_info(payload)
        return data if isinstance(data, dict) else {}

    def get_user_fills(self, address: str, start_time: int | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"type": "userFills", "user": address}
        if start_time is not None:
            payload["startTime"] = start_time
        data = self._post_info(payload)
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
        last_min_time: int | None = None
        for _ in range(max_pages):
            batch = self.get_user_fills(address, cursor)
            if not batch:
                break
            all_fills.extend(batch)
            times = [f.get("time") for f in batch if f.get("time") is not None]
            if not times:
                break
            min_time = min(times)
            # Stop if the API is ignoring startTime and returning the same window repeatedly.
            if last_min_time is not None and min_time >= last_min_time:
                break
            last_min_time = min_time
            # If we were given a checkpoint and we have paged past it, stop early.
            if start_time is not None and min_time <= start_time:
                break
            cursor = min_time - 1  # walk backward in time
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
        data = self._post_info(payload)
        return data if isinstance(data, dict) else {}


hyperliquid_client = HyperliquidClient()
