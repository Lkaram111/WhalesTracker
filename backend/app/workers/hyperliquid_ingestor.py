from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import logging
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Chain, Event, EventType, Holding, Trade, TradeDirection, TradeSource, Whale
from app.services.broadcast import broadcast_manager
from app.services.hyperliquid_client import hyperliquid_client
from app.services.metrics_service import touch_last_active
from app.services.metrics_service import recompute_wallet_metrics

logger = logging.getLogger(__name__)


class HyperliquidIngestor:
    def __init__(self, poll_interval: float = 300.0) -> None:
        self.poll_interval = poll_interval
        self._running = False

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.process_accounts()
            except Exception:
                logger.exception("Hyperliquid ingestor loop error")
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False

    async def process_accounts(self) -> None:
        with SessionLocal() as session:
            chain = session.query(Chain).filter(Chain.slug == "hyperliquid").one_or_none()
            if not chain:
                return
            whales = (
                session.query(Whale)
                .filter(Whale.chain_id == chain.id)
                .all()
            )
            for whale in whales:
                self._process_account(session, chain.id, whale)
            session.commit()

    def _process_account(self, session, chain_id: int, whale: Whale) -> None:
        now = datetime.now(timezone.utc)
        # Fills (trades)
        try:
            fills = hyperliquid_client.get_user_fills_paginated(whale.address, max_pages=20)
        except Exception:
            fills = []

        if fills:
            # Ingest oldest → newest so autoincrement IDs follow chronological order
            for fill in reversed(fills):
                tx_hash = fill.get("hash") or str(fill.get("tid") or fill.get("oid") or "")
                if tx_hash:
                    exists = session.scalar(
                        select(Trade.id).where(Trade.tx_hash == tx_hash, Trade.whale_id == whale.id)
                    )
                    if exists:
                        continue
                ts_ms = fill.get("time") or 0
                timestamp = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc) if ts_ms else now
                sz = fill.get("sz")
                px = fill.get("px")
                coin = fill.get("coin") or fill.get("ticker") or "PERP"
                try:
                    amount_base = abs(float(sz))
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
                try:
                    asyncio.create_task(
                        broadcast_manager.broadcast(
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
                    )
                except Exception:
                    pass

        # Add hyperliquid label if missing
        labels = whale.labels or []
        if "hyperliquid" not in labels:
            labels.append("hyperliquid")
            whale.labels = labels

        touch_last_active(session, whale, now)
        self._process_positions(session, chain_id, whale, now)
        recompute_wallet_metrics(session, whale)

    def _process_positions(self, session, chain_id: int, whale: Whale, now: datetime) -> None:
        try:
            state = hyperliquid_client.get_clearinghouse_state(whale.address)
        except Exception:
            return
        positions = state.get("assetPositions") if isinstance(state, dict) else []
        if not isinstance(positions, list):
            return
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
            session.add(
                Event(
                    timestamp=now,
                    chain_id=chain_id,
                    type=EventType.PERP_TRADE,
                    whale_id=whale.id,
                    summary=f"Position {coin} {direction.value} size {size}",
                    value_usd=value_usd,
                    tx_hash=None,
                    details={"mark_px": mark_px, "entry_px": entry_px, "funding": funding},
                )
            )
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
            try:
                asyncio.create_task(
                    broadcast_manager.broadcast(
                        {
                            "id": f"{whale.id}-{coin}-{now.timestamp()}",
                            "timestamp": now.isoformat(),
                            "chain": "hyperliquid",
                            "type": EventType.PERP_TRADE.value,
                            "wallet": {
                                "address": whale.address,
                                "chain": "hyperliquid",
                                "label": (whale.labels or [None])[0] if whale.labels else None,
                            },
                            "summary": f"Position {coin} {direction.value} size {size}",
                            "value_usd": value_usd or 0.0,
                            "tx_hash": None,
                            "details": {"mark_px": mark_px, "entry_px": entry_px, "funding": funding},
                        }
                    )
                )
            except Exception:
                pass
