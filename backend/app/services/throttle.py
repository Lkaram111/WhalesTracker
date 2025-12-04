from __future__ import annotations

import time
from typing import Dict


class Throttle:
    """Simple named throttler to limit call frequency per key."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self.last_run: Dict[str, float] = {}

    def can_run(self, key: str) -> bool:
        now = time.perf_counter()
        last = self.last_run.get(key, 0.0)
        return (now - last) >= self.min_interval

    def touch(self, key: str) -> None:
        self.last_run[key] = time.perf_counter()
