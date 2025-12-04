import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.models import BacktestRun, Whale
from app.services.hyperliquid_client import hyperliquid_client
from app.services.hyperliquid_trading import hyperliquid_trading_client
from app.services.throttle import Throttle


@dataclass
class CopierSession:
    id: int
    whale_id: str
    address: str
    leverage: float
    position_size_pct: float | None
    asset_symbols: list[str] | None
    last_seen_fill: int | None = None
    active: bool = True
    errors: list[str] = field(default_factory=list)
    notifications: list[str] = field(default_factory=list)
    initial_positions: dict[str, float] = field(default_factory=dict)
    processed: int = 0
    execute: bool = False
    is_cross: bool = True


class CopierManager:
    def __init__(self, poll_interval: float = 1.0) -> None:
        self.poll_interval = poll_interval
        self._sessions: Dict[int, CopierSession] = {}
        self._lock = threading.Lock()
        self._next_id = 1
        self._worker = threading.Thread(target=self._loop, daemon=True)
        self._running = False
        self._leverage_throttle = Throttle(min_interval=2.0)  # avoid spamming leverage updates

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker.start()

    def stop(self) -> None:
        self._running = False
        if self._worker.is_alive():
            self._worker.join(timeout=2)

    def create_session(
        self,
        whale: Whale,
        run: BacktestRun,
        execute: bool = False,
        position_size_pct: float | None = None,
    ) -> CopierSession:
        # Seed the cursor to the latest known fill so we don't replay historical trades
        latest_ts: int | None = None
        initial_positions: dict[str, float] = {}
        try:
            fills = hyperliquid_client.get_user_fills(whale.address)
            times = [int(f.get("time") or f.get("timestamp")) for f in fills if f.get("time") or f.get("timestamp")]
            if times:
                latest_ts = max(times)
        except Exception as exc:  # noqa: PERF203
            # Don't block session creation if history fetch fails
            latest_ts = None
        try:
            state = hyperliquid_client.get_clearinghouse_state(whale.address) or {}
            for ap in state.get("assetPositions") or []:
                pos = ap.get("position") or {}
                coin = pos.get("coin") or ap.get("coin")
                szi = pos.get("szi")
                if coin is None or szi is None:
                    continue
                try:
                    size_val = float(szi)
                except Exception:
                    continue
                if abs(size_val) > 0:
                    initial_positions[coin.upper()] = size_val
        except Exception as exc:  # noqa: PERF203
            # Don't block session creation if history fetch fails
            initial_positions = {}
        with self._lock:
            session_id = self._next_id
            self._next_id += 1
            sess = CopierSession(
                id=session_id,
                whale_id=whale.id,
                address=whale.address,
                leverage=float(run.leverage or 1.0),
                position_size_pct=(
                    float(position_size_pct)
                    if position_size_pct is not None
                    else float(run.position_size_pct) if run.position_size_pct is not None else None
                ),
                asset_symbols=run.asset_symbols or None,
                last_seen_fill=latest_ts,
                execute=execute,
                is_cross=True,
                initial_positions=initial_positions,
            )
            if latest_ts is not None:
                sess.notifications.append(f"Skipping historical fills up to {latest_ts}")
            if initial_positions:
                sess.notifications.append(f"Detected pre-session open positions: {', '.join(sorted(initial_positions.keys()))}")
            self._sessions[session_id] = sess
            return sess

    def stop_session(self, session_id: int) -> None:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].active = False

    def get_session(self, session_id: int) -> Optional[CopierSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[CopierSession]:
        with self._lock:
            return list(self._sessions.values())

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def _tick(self) -> None:
        with self._lock:
            sessions = [s for s in self._sessions.values() if s.active]
        if not sessions:
            return
        for sess in sessions:
            self._process_session(sess)

    def _process_session(self, sess: CopierSession) -> None:
        start_time = sess.last_seen_fill
        try:
            fills = hyperliquid_client.get_user_fills(sess.address, start_time=start_time)
        except Exception as exc:  # noqa: PERF203
            sess.errors.append(str(exc))
            return
        if not fills:
            return
        for fill in fills:
            ts = fill.get('time') or fill.get('timestamp')
            if ts is None:
                continue
            try:
                ts_int = int(ts)
            except Exception:
                ts_int = None
            if ts_int is not None:
                if sess.last_seen_fill is None or ts_int > sess.last_seen_fill:
                    sess.last_seen_fill = ts_int
            coin = fill.get('coin') or fill.get('asset')
            coin_key = coin.upper() if coin else None
            if sess.asset_symbols and coin and coin.upper() not in [a.upper() for a in sess.asset_symbols]:
                continue
            is_buy = True if fill.get('side') in ('B', 'BUY', 'buy') else False
            sz = float(fill.get('sz') or fill.get('size') or fill.get('qty') or 0)
            px = fill.get('px') or fill.get('price')
            try:
                px_val = float(px) if px is not None else None
            except Exception:
                px_val = None
            if sz <= 0 or not coin or px_val is None:
                continue
            # If we started while whale already had an open position, skip closes until that position is cleared.
            if coin_key and coin_key in sess.initial_positions and sess.initial_positions[coin_key] != 0:
                signed_sz = sz if is_buy else -sz
                current = sess.initial_positions[coin_key]
                # If the trade reduces magnitude of the pre-session position, treat it as an old close and skip copying.
                if (current > 0 and signed_sz < 0) or (current < 0 and signed_sz > 0):
                    new_pos = current + signed_sz
                    sess.initial_positions[coin_key] = new_pos
                    sess.notifications.append(
                        f"Ignored close for pre-session position {coin} (remaining {new_pos:.4f}) at {ts_int}"
                    )
                    continue
            # apply position scaling if provided (percent of whale size)
            if sess.position_size_pct is not None:
                sz = sz * (sess.position_size_pct / 100.0)
            if (
                sess.execute
                and sess.leverage
                and sess.leverage > 0
                and self._leverage_throttle.can_run(f"{sess.id}:{coin}")
            ):
                try:
                    hyperliquid_trading_client.update_leverage(coin, sess.leverage, is_cross=sess.is_cross)
                    self._leverage_throttle.touch(f"{sess.id}:{coin}")
                except Exception as exc:
                    # log but continue; some endpoints reject leverage update when already set
                    sess.errors.append(f"leverage error (ignored): {exc}")
            try:
                order = hyperliquid_trading_client.build_ioc_order(coin=coin, is_buy=is_buy, sz=sz, px=px_val, reduce_only=False)
            except Exception as exc:
                sess.errors.append(f"build order error: {exc}")
                continue
            if sess.execute:
                try:
                    hyperliquid_trading_client.submit_orders([order])
                except Exception as exc:  # noqa: PERF203
                    sess.errors.append(f"order error: {exc}")
            sess.processed += 1


copier_manager = CopierManager()
