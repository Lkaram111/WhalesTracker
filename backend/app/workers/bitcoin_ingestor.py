from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import logging
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Chain, Event, EventType, Trade, TradeDirection, TradeSource, Whale
from app.services.broadcast import broadcast_manager
from app.services.bitcoin_client import bitcoin_client
from app.services.coingecko_client import coingecko_client
from app.services.metrics_service import touch_last_active

logger = logging.getLogger(__name__)


class BitcoinIngestor:
    def __init__(self, poll_interval: float = 30.0) -> None:
        self.poll_interval = poll_interval
        self._running = False
        self._btc_price_usd: float | None = None

    async def run_forever(self) -> None:
        self._running = True
        while self._running:
            try:
                await self.process_addresses()
            except Exception:
                logger.exception("Bitcoin ingestor loop error")
            await asyncio.sleep(self.poll_interval)

    def stop(self) -> None:
        self._running = False

    async def process_addresses(self) -> None:
        with SessionLocal() as session:
            btc_chain = session.query(Chain).filter(Chain.slug == "bitcoin").one_or_none()
            if not btc_chain:
                return
            whales = session.query(Whale).filter(Whale.chain_id == btc_chain.id).all()
            if not whales:
                return

            self._btc_price_usd = self._fetch_btc_price()

            for whale in whales:
                self._process_whale(session, btc_chain.id, whale)

            session.commit()

    def _fetch_btc_price(self) -> float | None:
        try:
            prices = coingecko_client.get_simple_price(["bitcoin"])
            return prices.get("bitcoin")
        except Exception:
            return None

    def _process_whale(self, session, chain_id: int, whale: Whale) -> None:
        txs = bitcoin_client.get_address_txs(whale.address, limit=20)
        for tx in txs:
            txid = tx.get("txid")
            if txid:
                existing = session.scalar(select(Trade.id).where(Trade.tx_hash == txid))
                if existing:
                    continue
            timestamp = datetime.fromtimestamp(tx.get("status", {}).get("block_time", 0), tz=timezone.utc)
            vin_addresses = {vin.get("prevout", {}).get("scriptpubkey_address") for vin in tx.get("vin", [])}
            vout_addresses = {vout.get("scriptpubkey_address") for vout in tx.get("vout", [])}
            direction = None
            if whale.address in vout_addresses and whale.address not in vin_addresses:
                direction = TradeDirection.DEPOSIT
            elif whale.address in vin_addresses and whale.address not in vout_addresses:
                direction = TradeDirection.WITHDRAW
            else:
                continue

            counterparties = vin_addresses.union(vout_addresses)
            is_exchange_flow = any(addr in EXCHANGE_ADDRESSES for addr in counterparties if addr)

            value_btc = sum(
                (vout.get("value", 0) or 0) / 1e8
                for vout in tx.get("vout", [])
                if vout.get("scriptpubkey_address") == whale.address
            )
            value_usd = None
            if self._btc_price_usd is not None:
                value_usd = value_btc * self._btc_price_usd

            source = TradeSource.EXCHANGE_FLOW if is_exchange_flow else TradeSource.ONCHAIN
            platform = "exchange_flow" if is_exchange_flow else "bitcoin"

            trade = Trade(
                whale_id=whale.id,
                timestamp=timestamp,
                chain_id=chain_id,
                source=source,
                platform=platform,
                direction=direction,
                base_asset="BTC",
                quote_asset="USD",
                amount_base=value_btc,
                amount_quote=None,
                value_usd=value_usd,
                pnl_usd=None,
                pnl_percent=None,
                tx_hash=txid,
                external_url=None,
            )
            session.add(trade)
            event_type = EventType.EXCHANGE_FLOW if is_exchange_flow else EventType.LARGE_TRANSFER
            self._record_event(
                session,
                chain_id,
                whale,
                timestamp,
                event_type,
                value_usd,
                txid,
                summary=f"BTC {direction.value}",
            )
            touch_last_active(session, whale, timestamp)

    def _record_event(
        self,
        session,
        chain_id: int,
        whale: Whale,
        timestamp: datetime,
        event_type: EventType,
        value_usd: float | None,
        tx_hash: str | None,
        summary: str,
    ) -> None:
        session.add(
            Event(
                timestamp=timestamp,
                chain_id=chain_id,
                type=event_type,
                whale_id=whale.id,
                summary=summary,
                value_usd=value_usd,
                tx_hash=tx_hash,
                details={},
            )
        )
        try:
            msg = {
                "id": tx_hash or "",
                "timestamp": timestamp.isoformat(),
                "chain": "bitcoin",
                "type": event_type.value if hasattr(event_type, "value") else str(event_type),
                "wallet": {
                    "address": whale.address,
                    "chain": "bitcoin",
                    "label": (whale.labels or [None])[0] if whale.labels else None,
                },
                "summary": summary,
                "value_usd": value_usd or 0.0,
                "tx_hash": tx_hash,
                "details": {},
            }
            asyncio.create_task(broadcast_manager.broadcast(msg))
        except Exception:
            pass


EXCHANGE_ADDRESSES = {
    "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",  # Coinbase
    "bc1qtc2gl9y0lhgs6vh7z0p4lrcxarp94x9cc57y6p",  # Binance
    "3D2oetdNuZUqQHPJmcMDDHYoqkyNVsFk9r",  # Bitfinex
    "3M219KR6QL7hjiqZ4TTMi3J3z9Cpo5Vud4",  # Kraken
    "bc1q592d4j0gyu40m6az04q9u3d0sy4p9t7dun9w6c",  # Gemini
    "bc1q0htcv84h8dl0tvkmx3spptclc373x3p3dnc3f4",  # OKX
    "bc1qn0e0y7tsawhfpyu0sn3c90d82tgkkjt2y7tsg2",  # Binance hot
    "bc1q2v9kec8sg9f3rv9p5c9pn9vyf0a9keat8wr87p",  # Bybit
}
