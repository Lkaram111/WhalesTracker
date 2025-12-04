from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import time
from typing import Any, Callable

import logging
from httpx import HTTPStatusError
from sqlalchemy.exc import OperationalError
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import (
    Base,
    Chain,
    Event,
    EventType,
    Holding,
    IngestionCheckpoint,
    Trade,
    TradeDirection,
    TradeSource,
    Whale,
)
from app.services.broadcast import broadcast_manager
from app.services.hyperliquid_client import hyperliquid_client
from app.services.metrics_service import touch_last_active
from app.services.metrics_service import recompute_wallet_metrics

logger = logging.getLogger(__name__)


class HyperliquidIngestor:
    def __init__(self, poll_interval: float = 300.0, max_pages_per_tick: int = 3) -> None:
        self.poll_interval = poll_interval
        self.max_pages_per_tick = max_pages_per_tick
        self._running = False
        self._failure_backoff: dict[str, tuple[int, datetime]] = {}
        self._max_backoff_seconds = 60
        self._loop: asyncio.AbstractEventLoop | None = None
        self._schema_ready = False
        # Cache last seen positions to avoid spamming live feed with unchanged snapshots
        self._positions_cache: dict[str, dict[str, tuple[float, float | None]]] = {}

    def _backoff_active(self, address: str) -> bool:
        entry = self._failure_backoff.get(address)
        if not entry:
            return False
        _, until = entry
        return datetime.now(timezone.utc) < until

    def _record_backoff(self, address: str, exc: Exception) -> None:
        count, _ = self._failure_backoff.get(address, (0, datetime.now(timezone.utc)))
        count += 1
        delay = min(self._max_backoff_seconds, (2**count) * 5)
        until = datetime.now(timezone.utc) + timedelta(seconds=delay)
        self._failure_backoff[address] = (count, until)
        logger.warning(
            "Hyperliquid API error for %s (%s); backing off for %s seconds",
            address,
            exc,
            delay,
        )

    def _clear_backoff(self, address: str) -> None:
        self._failure_backoff.pop(address, None)

    async def run_forever(self) -> None:
        self._running = True
        self._loop = asyncio.get_running_loop()
        logger.info("Hyperliquid ingestor started (interval=%ss)", self.poll_interval)
        while self._running:
            started = time.perf_counter()
            try:
                await asyncio.to_thread(self.process_accounts)
                logger.debug("Hyperliquid ingestor tick finished in %.2fs", time.perf_counter() - started)
            except Exception:
                logger.exception("Hyperliquid ingestor loop error")
            await asyncio.sleep(self.poll_interval)
        logger.info("Hyperliquid ingestor stopped")

    def stop(self) -> None:
        self._running = False

    def process_accounts(self) -> None:
        logger.debug("Hyperliquid ingestor polling accounts")
        with SessionLocal() as session:
            self._ensure_checkpoint_table(session)
            chain = session.query(Chain).filter(Chain.slug == "hyperliquid").one_or_none()
            if not chain:
                logger.debug("Hyperliquid chain missing in DB; skipping tick")
                return
            whales = (
                session.query(Whale)
                .filter(Whale.chain_id == chain.id)
                .all()
            )
            if not whales:
                logger.debug("No Hyperliquid whales configured; skipping tick")
                return
            for whale in whales:
                logger.info("HL ingest start whale=%s", whale.address)
                wrote = self._process_account(session, chain.id, whale, max_pages=self.max_pages_per_tick)
                logger.info("HL ingest end whale=%s wrote=%s", whale.address, wrote)
                # Commit after each whale to release SQLite locks quickly and avoid blocking API reads.
                self._commit_with_retry(session)

    def _commit_with_retry(self, session, retries: int = 3, delay: float = 0.5) -> None:
        for attempt in range(retries):
            try:
                session.commit()
                return
            except OperationalError:
                session.rollback()
                if attempt == retries - 1:
                    raise
                time.sleep(delay)

    def _process_account(
        self,
        session,
        chain_id: int,
        whale: Whale,
        max_pages: int = 20,
        progress_cb: Callable[[float, str | None], None] | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        progress = progress_cb or (lambda pct, msg=None: None)
        progress(5.0, "hyperliquid: fetching fills")
        wrote = False
        checkpoint = self._get_or_create_checkpoint(session, whale)
        if checkpoint.last_fill_time is None:
            self._seed_checkpoint_from_trades(session, whale, checkpoint)
        start_time = checkpoint.last_fill_time
        logger.debug(
            "HL ingest fills whale=%s start_time=%s",
            whale.address,
            start_time,
        )
        # Fills (trades)
        if self._backoff_active(whale.address):
            logger.warning("Skipping Hyperliquid fill fetch for %s due to backoff", whale.address)
            progress(100.0, "hyperliquid: skipped due to backoff")
            return False
        try:
            page_limit = 1 if start_time is not None else max_pages
            cursor = (start_time + 1) if start_time is not None else None
            fills = hyperliquid_client.get_user_fills_paginated(
                whale.address, start_time=cursor, max_pages=page_limit
            )
            self._clear_backoff(whale.address)
        except HTTPStatusError as exc:
            self._record_backoff(whale.address, exc)
            fills = []
        except Exception as exc:
            fills = []
            self._record_backoff(whale.address, exc)

        new_fills = [
            f for f in fills if checkpoint.last_fill_time is None or (f.get("time") or 0) > checkpoint.last_fill_time
        ]

        if new_fills:
            progress(25.0, f"hyperliquid: processing {len(new_fills)} fills")
            max_time = start_time or 0
            # Ingest oldest -> newest so autoincrement IDs follow chronological order
            seen_tx: set[str] = set()
            for fill in sorted(new_fills, key=lambda f: f.get("time") or 0):
                tx_hash = fill.get("hash") or str(fill.get("tid") or fill.get("oid") or "")
                if tx_hash:
                    if tx_hash in seen_tx:
                        continue
                    exists = session.scalar(
                        select(Trade.id).where(Trade.tx_hash == tx_hash, Trade.whale_id == whale.id)
                    )
                    if exists:
                        seen_tx.add(tx_hash)
                        continue
                    seen_tx.add(tx_hash)
                ts_ms = fill.get("time") or 0
                timestamp = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc) if ts_ms else now
                sz = fill.get("sz")
                px = fill.get("px")
                coin = fill.get("coin") or fill.get("ticker") or "PERP"
                try:
                    amount_base = float(sz)
                except Exception:
                    amount_base = None
                value_usd = None
                try:
                    value_usd = abs(float(sz) * float(px))
                except Exception:
                    pass
                dir_str = str(fill.get("dir") or "").lower()
                if "close" in dir_str and "short" in dir_str:
                    direction = TradeDirection.CLOSE_SHORT
                elif "close" in dir_str and "long" in dir_str:
                    direction = TradeDirection.CLOSE_LONG
                elif "short" in dir_str:
                    direction = TradeDirection.SHORT
                elif "long" in dir_str:
                    direction = TradeDirection.LONG
                else:
                    direction = TradeDirection.SHORT if str(fill.get("side") or "").lower() == "a" else TradeDirection.LONG
                session.add(
                    Trade(
                        whale_id=whale.id,
                        timestamp=timestamp,
                        chain_id=chain_id,
                        source=TradeSource.HYPERLIQUID,
                        platform="hyperliquid",
                        direction=direction,
                        base_asset=coin,
                        quote_asset="USD",
                        amount_base=amount_base,
                        amount_quote=None,
                        value_usd=value_usd,
                        pnl_usd=float(fill.get("closedPnl")) if fill.get("closedPnl") is not None else None,
                        pnl_percent=None,
                        tx_hash=tx_hash or None,
                        external_url=None,
                    )
                )
                session.add(
                    Event(
                        timestamp=timestamp,
                        chain_id=chain_id,
                        type=EventType.PERP_TRADE,
                        whale_id=whale.id,
                        summary=f"Hyperliquid {coin} {direction.value}",
                        value_usd=value_usd,
                        tx_hash=tx_hash or None,
                        details={"tid": fill.get("tid"), "oid": fill.get("oid"), "fee": fill.get("fee")},
                    )
                )
                self._schedule_broadcast(
                    {
                        "id": tx_hash or "",
                        "timestamp": timestamp.isoformat(),
                        "chain": "hyperliquid",
                        "type": EventType.PERP_TRADE.value,
                        "wallet": {
                            "address": whale.address,
                            "chain": "hyperliquid",
                            "label": (whale.labels or [None])[0] if whale.labels else None,
                        },
                        "summary": f"Hyperliquid {coin} {direction.value}",
                        "value_usd": value_usd or 0.0,
                        "tx_hash": tx_hash,
                        "details": {"tid": fill.get("tid"), "oid": fill.get("oid"), "fee": fill.get("fee")},
                    }
                )
            wrote = wrote or bool(new_fills)
            try:
                times = [int(f.get("time") or 0) for f in new_fills if f.get("time") is not None]
                if times:
                    max_time = max(times)
            except Exception:
                pass
            checkpoint.last_fill_time = max(checkpoint.last_fill_time or 0, max_time)
            checkpoint.updated_at = datetime.now(timezone.utc)
            logger.info(
                "HL ingest fills whale=%s processed=%s new_last_fill_time=%s",
                whale.address,
                len(new_fills),
                checkpoint.last_fill_time,
            )
        else:
            logger.debug("HL ingest fills whale=%s no new fills", whale.address)
            # Record that we checked up to the current cursor so we don't scan behind it next tick.
            checkpoint.updated_at = datetime.now(timezone.utc)

        # Add hyperliquid label if missing
        labels = whale.labels or []
        if "hyperliquid" not in labels:
            labels.append("hyperliquid")
            whale.labels = labels

        touch_last_active(session, whale, now)
        progress(85.0, "hyperliquid: fetching positions")
        positions_written = self._process_positions(session, chain_id, whale, now)
        wrote = wrote or positions_written
        if positions_written:
            checkpoint.last_position_time = now
            checkpoint.updated_at = datetime.now(timezone.utc)
            logger.info("HL ingest positions whale=%s wrote_positions=True", whale.address)
        else:
            logger.debug("HL ingest positions whale=%s no positions written", whale.address)
        recompute_wallet_metrics(session, whale)
        progress(100.0, "hyperliquid: backfill done")
        return wrote

    def _process_positions(self, session, chain_id: int, whale: Whale, now: datetime) -> bool:
        wrote = False
        if self._backoff_active(whale.address):
            logger.warning("Skipping Hyperliquid position fetch for %s due to backoff", whale.address)
            return False
        try:
            state = hyperliquid_client.get_clearinghouse_state(whale.address, use_cache=True, ttl=5.0)
            self._clear_backoff(whale.address)
        except HTTPStatusError as exc:
            self._record_backoff(whale.address, exc)
            return False
        except Exception as exc:
            self._record_backoff(whale.address, exc)
            return False
        positions = state.get("assetPositions") if isinstance(state, dict) else []
        logger.debug("HL positions whale=%s positions_len=%s", whale.address, len(positions) if positions else 0)
        if not isinstance(positions, list):
            return False
        cache = self._positions_cache.setdefault(whale.address, {})
        for pos in positions:
            position = pos.get("position") or {}
            coin = pos.get("coin") or position.get("coin")
            szi = position.get("szi")
            entry_px = position.get("entryPx")
            mark_px = position.get("markPx") or pos.get("markPx") or entry_px
            funding = position.get("funding") or pos.get("funding")
            if coin is None or szi in (None, 0):
                continue
            size = float(szi)
            prev_size, prev_entry = cache.get(coin.upper(), (None, None))  # type: ignore
            direction = TradeDirection.LONG if size >= 0 else TradeDirection.SHORT
            value_usd = None
            # Prefer reported position value (notional); otherwise mark*size
            if position.get("positionValue") is not None:
                try:
                    value_usd = float(position.get("positionValue"))
                except Exception:
                    value_usd = None
            if value_usd is None and isinstance(mark_px, (int, float, str)):
                try:
                    mp = float(mark_px)
                    value_usd = abs(size * mp)
                except Exception:
                    pass
            changed = prev_size is None or abs(prev_size - size) > 1e-9 or (prev_entry is None and entry_px is not None)
            cache[coin.upper()] = (size, entry_px if isinstance(entry_px, (int, float)) else prev_entry)
            holding = (
                session.query(Holding)
                .filter(Holding.whale_id == whale.id, Holding.asset_symbol == coin)
                .one_or_none()
            )
            if holding:
                holding.amount = abs(size)
                holding.value_usd = value_usd
            else:
                session.add(
                    Holding(
                        whale_id=whale.id,
                        asset_symbol=coin,
                        asset_name=coin,
                        chain_id=chain_id,
                        amount=abs(size),
                        value_usd=value_usd,
                        portfolio_percent=None,
                    )
                )
            # Do not emit position snapshots to the live feed; only update holdings/metrics.
            if changed:
                wrote = True
        return wrote

    def _schedule_broadcast(self, msg: dict) -> None:
        try:
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(asyncio.create_task, broadcast_manager.broadcast(msg))
        except Exception:
            logger.debug("Hyperliquid broadcast scheduling failed", exc_info=True)

    def _ensure_checkpoint_table(self, session) -> None:
        if self._schema_ready:
            return
        try:
            Base.metadata.create_all(session.bind, tables=[IngestionCheckpoint.__table__])
            self._schema_ready = True
        except Exception:
            # best-effort; we will try again next tick if it fails
            self._schema_ready = False

    def _get_or_create_checkpoint(self, session, whale: Whale) -> IngestionCheckpoint:
        cp = session.query(IngestionCheckpoint).filter(IngestionCheckpoint.whale_id == whale.id).one_or_none()
        if cp:
            return cp
        cp = IngestionCheckpoint(
            whale_id=whale.id,
            chain_slug="hyperliquid",
            last_fill_time=None,
            last_position_time=None,
        )
        session.add(cp)
        session.flush()
        return cp

    def _seed_checkpoint_from_trades(self, session, whale: Whale, checkpoint: IngestionCheckpoint) -> None:
        try:
            latest = session.scalar(
                select(Trade.timestamp)
                .where(Trade.whale_id == whale.id, Trade.source == TradeSource.HYPERLIQUID)
                .order_by(Trade.timestamp.desc())
            )
            if latest:
                checkpoint.last_fill_time = int(latest.timestamp() * 1000) + 1
                checkpoint.updated_at = datetime.now(timezone.utc)
        except Exception:
            pass
