from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any


class BackfillProgressTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._progress: dict[str, dict[str, Any]] = {}

    def start(self, whale_id: str, chain: str | None = None) -> None:
        with self._lock:
            self._progress[whale_id] = {
                "whale_id": whale_id,
                "chain": chain,
                "status": "running",
                "progress": 0.0,
                "message": "starting",
                "updated_at": datetime.now(timezone.utc),
            }

    def update(self, whale_id: str, progress: float | None = None, message: str | None = None) -> None:
        with self._lock:
            entry = self._progress.get(whale_id)
            if not entry:
                return
            if progress is not None:
                entry["progress"] = max(0.0, min(100.0, float(progress)))
            if message is not None:
                entry["message"] = message
            entry["updated_at"] = datetime.now(timezone.utc)

    def finish(self, whale_id: str, success: bool = True, message: str | None = None) -> None:
        with self._lock:
            entry = self._progress.get(whale_id)
            if not entry:
                return
            entry["status"] = "done" if success else "error"
            entry["progress"] = 100.0 if success else entry.get("progress", 0.0)
            if message is not None:
                entry["message"] = message
            entry["updated_at"] = datetime.now(timezone.utc)

    def error(self, whale_id: str, message: str | None = None) -> None:
        self.finish(whale_id, success=False, message=message or "error")

    def get(self, whale_id: str) -> dict[str, Any] | None:
        with self._lock:
            entry = self._progress.get(whale_id)
            if not entry:
                return None
            return dict(entry)


backfill_progress = BackfillProgressTracker()
