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
        # Simple TTL cache to avoid hitting /info repeatedly for the same address within a short window
        self._state_cache: dict[str, tuple[float, dict[str, Any]]] = {}

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

    def get_clearinghouse_state(self, address: str, use_cache: bool = True, ttl: float = 10.0) -> dict[str, Any]:
        """Fetch clearinghouse state with an optional short-lived cache to reduce duplicate calls."""
        now_ts = time.time()
        if use_cache:
            cached = self._state_cache.get(address.lower())
            if cached:
                ts, payload = cached
                if now_ts - ts <= ttl:
                    return payload
        payload = {"type": "clearinghouseState", "user": address}
        data = self._post_info(payload)
        state = data if isinstance(data, dict) else {}
        if use_cache:
            self._state_cache[address.lower()] = (now_ts, state)
        return state

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
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch user fills forward in time using the `userFillsByTime` windowed API.

        The standard `userFills` endpoint ignores pagination parameters and only returns the
        latest ~2000 fills. `userFillsByTime` accepts a `startTime` cursor (ms) and returns fills
        in ascending time order up to an optional `endTime`, capped at ~2000 per response.
        We advance the cursor to the max timestamp + 1 on each page until we exhaust results
        or hit `max_pages`.
        """
        cursor = start_time or 0
        all_fills: list[dict[str, Any]] = []
        last_max_time: int | None = None

        for _ in range(max_pages):
            payload: dict[str, Any] = {"type": "userFillsByTime", "user": address, "startTime": cursor}
            if end_time is not None:
                payload["endTime"] = end_time
            batch = self._post_info(payload)
            if not isinstance(batch, list) or not batch:
                break
            all_fills.extend(batch)

            times = [f.get("time") for f in batch if f.get("time") is not None]
            if not times:
                break
            max_time = max(times)
            # Prevent infinite loops if the API stops advancing
            if last_max_time is not None and max_time <= last_max_time:
                break
            last_max_time = max_time

            cursor = max_time + 1  # walk forward in time
            # If we received fewer than 2000, we've likely reached the end of the window
            if len(batch) < 2000:
                break
            if end_time is not None and cursor > end_time:
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
