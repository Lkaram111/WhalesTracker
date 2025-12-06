import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.models import BacktestRun, Whale
from app.services.hyperliquid_client import hyperliquid_client
from app.services.hyperliquid_trading import hyperliquid_trading_client
from app.services.throttle import Throttle

logger = logging.getLogger(__name__)


@dataclass
class CopierSession:
    id: int
    whale_id: str
    address: str
    leverage: float | None
    position_size_pct: float | None
    asset_symbols: list[str] | None
    asset_symbols_upper: set[str] = field(default_factory=set)
    last_seen_fill: int | None = None
    active: bool = True
    errors: list[str] = field(default_factory=list)
    notifications: list[str] = field(default_factory=list)
    initial_positions: dict[str, float] = field(default_factory=dict)
    processed: int = 0
    execute: bool = False
    is_cross: bool = True
    position_size_auto: bool = False
    leverage_auto: bool = False
    user_deposit_usd: float | None = None
    whale_account_value_usd: float | None = None
    last_computed_position_pct: float | None = None
    last_leverage_used: float | None = None


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
        leverage: float | None = None,
        user_deposit_usd: float | None = None,
        whale_account_value_usd: float | None = None,
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
        symbols = run.asset_symbols or []
        asset_symbols_upper = {s.upper() for s in symbols}
        leverage_override = (
            float(leverage)
            if leverage is not None
            else float(run.leverage)
            if run.leverage is not None
            else None
        )
        position_override = (
            float(position_size_pct)
            if position_size_pct is not None
            else float(run.position_size_pct)
            if run.position_size_pct is not None
            else None
        )
        try:
            deposit_val = (
                float(user_deposit_usd)
                if user_deposit_usd is not None
                else float(run.initial_deposit_usd)
                if run.initial_deposit_usd is not None
                else None
            )
        except Exception:
            deposit_val = None
        try:
            account_value = float(whale_account_value_usd) if whale_account_value_usd is not None else None
        except Exception:
            account_value = None
        with self._lock:
            session_id = self._next_id
            self._next_id += 1
            sess = CopierSession(
                id=session_id,
                whale_id=whale.id,
                address=whale.address,
                leverage=leverage_override,
                position_size_pct=position_override,
                asset_symbols=symbols or None,
                asset_symbols_upper=asset_symbols_upper,
                last_seen_fill=latest_ts,
                execute=execute,
                is_cross=True,
                initial_positions=initial_positions,
                position_size_auto=position_override is None,
                leverage_auto=leverage_override is None,
                user_deposit_usd=deposit_val,
                whale_account_value_usd=account_value,
            )
            if latest_ts is not None:
                sess.notifications.append(f"Skipping historical fills up to {latest_ts}")
            if initial_positions:
                sess.notifications.append(
                    f"Detected pre-session open positions: {', '.join(sorted(initial_positions.keys()))}"
                )
            self._sessions[session_id] = sess
            return sess

    def stop_session(self, session_id: int) -> None:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].active = False

    def get_session(self, session_id: int) -> Optional[CopierSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions_for_whale(self, whale_id: str) -> list[CopierSession]:
        with self._lock:
            return [s for s in self._sessions.values() if s.whale_id == whale_id and s.active]

    def list_sessions(self) -> list[CopierSession]:
        with self._lock:
            return list(self._sessions.values())

    def _loop(self) -> None:
        while self._running:
            try:
                self._tick()
            except Exception as exc:  # noqa: PERF203
                logger.exception("Copier tick failed: %s", exc)
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
            fills = hyperliquid_client.get_user_fills_paginated(
                sess.address, start_time=start_time, max_pages=1
            )
        except Exception as exc:  # noqa: PERF203
            sess.errors.append(str(exc))
            return
        if not fills:
            return
        account_value = sess.whale_account_value_usd
        if sess.position_size_auto or sess.leverage_auto:
            try:
                state = hyperliquid_client.get_clearinghouse_state(sess.address, use_cache=True, ttl=5.0) or {}
                margin_summary = state.get("marginSummary") or {}
                acct_val_raw = margin_summary.get("accountValue") or (state.get("crossMarginSummary") or {}).get(
                    "accountValue"
                )
                if acct_val_raw is not None:
                    try:
                        account_value = float(acct_val_raw)
                        sess.whale_account_value_usd = account_value
                    except Exception:
                        account_value = account_value
            except Exception as exc:
                msg = f"account value error: {exc}"
                if not sess.errors or sess.errors[-1] != msg:
                    sess.errors.append(msg)
        for fill in fills:
            ts = fill.get("time") or fill.get("timestamp")
            if ts is None:
                continue
            try:
                ts_int = int(ts)
            except Exception:
                ts_int = None
            if ts_int is not None:
                if sess.last_seen_fill is None or ts_int > sess.last_seen_fill:
                    sess.last_seen_fill = ts_int
            coin = fill.get("coin") or fill.get("asset")
            coin_key = coin.upper() if coin else None
            if sess.asset_symbols_upper and (not coin_key or coin_key not in sess.asset_symbols_upper):
                continue
            is_buy = True if fill.get("side") in ("B", "BUY", "buy") else False
            try:
                sz = float(fill.get("sz") or fill.get("size") or fill.get("qty") or 0)
            except Exception:
                sz = 0.0
            px = fill.get("px") or fill.get("price")
            try:
                px_val = float(px) if px is not None else None
            except Exception:
                px_val = None
            if sz <= 0 or not coin or px_val is None:
                continue
            whale_sz = sz
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
            scale_pct = sess.position_size_pct
            if sess.position_size_auto and sess.user_deposit_usd not in (None, 0) and account_value not in (None, 0):
                try:
                    auto_pct = (float(sess.user_deposit_usd) / float(account_value)) * 100.0
                    auto_pct = max(0.0, min(auto_pct, 200.0))
                    scale_pct = auto_pct
                    sess.last_computed_position_pct = auto_pct
                except Exception:
                    scale_pct = scale_pct
            if scale_pct is not None:
                sz = sz * (scale_pct / 100.0)
            effective_leverage = sess.leverage
            if sess.leverage_auto and account_value not in (None, 0):
                try:
                    notional_usd = abs(whale_sz * px_val)
                    eff = notional_usd / float(account_value) if account_value else None
                    if eff is not None:
                        effective_leverage = max(0.1, min(eff, 100.0))
                except Exception:
                    effective_leverage = effective_leverage
            sess.last_leverage_used = effective_leverage
            throttle_key = f"{sess.id}:{coin_key or coin}"
            if (
                sess.execute
                and effective_leverage
                and effective_leverage > 0
                and self._leverage_throttle.can_run(throttle_key)
            ):
                try:
                    hyperliquid_trading_client.update_leverage(
                        coin_key or coin, effective_leverage, is_cross=sess.is_cross
                    )
                    self._leverage_throttle.touch(throttle_key)
                except Exception as exc:
                    # log but continue; some endpoints reject leverage update when already set
                    sess.errors.append(f"leverage error (ignored): {exc}")
            try:
                order = hyperliquid_trading_client.build_ioc_order(
                    coin=coin_key or coin, is_buy=is_buy, sz=sz, px=px_val, reduce_only=False
                )
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
