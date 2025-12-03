from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from decimal import Decimal
from typing import Iterable

import logging
from sqlalchemy import select
from web3 import Web3

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Chain, Event, EventType, Trade, TradeDirection, TradeSource, Whale
from app.services.coingecko_client import coingecko_client
from app.services.ethereum_client import (
    get_block,
    get_erc20_decimals,
    get_erc20_symbol,
    get_pair_tokens,
    get_transaction_receipt,
)
from app.services.broadcast import broadcast_manager
from app.services.token_meta import ensure_token_meta
from app.services.metrics_service import touch_last_active

logger = logging.getLogger(__name__)

class EthereumIngestor:
    def __init__(self, poll_interval: float = 5.0) -> None:
        self.poll_interval = poll_interval
        self._running = False
        self._eth_price_usd: float | None = None
        self._token_prices: dict[str, float] = {}
        self._warned_no_provider = False
        self._loop: asyncio.AbstractEventLoop | None = None

    async def run_forever(self) -> None:
        self._running = True
        self._loop = asyncio.get_running_loop()
        logger.info("Ethereum ingestor started (interval=%ss)", self.poll_interval)
        while self._running:
            started = time.perf_counter()
            try:
                await asyncio.to_thread(self.process_latest_block)
                logger.debug("Ethereum ingestor tick finished in %.2fs", time.perf_counter() - started)
            except Exception:
                logger.exception("Ethereum ingestor loop error")
            await asyncio.sleep(self.poll_interval)
        logger.info("Ethereum ingestor stopped")

    def stop(self) -> None:
        self._running = False

    def process_latest_block(self) -> None:
        if not settings.ethereum_rpc_http_url:
            if not self._warned_no_provider:
                logger.warning("Ethereum RPC HTTP URL not configured; skipping ingestion.")
                self._warned_no_provider = True
            return
        try:
            block = get_block("latest")
        except RuntimeError as exc:
            logger.warning("Ethereum ingestor could not fetch block: %s", exc)
            return
        if not block:
            return

        txs = block.get("transactions", [])
        timestamp = datetime.fromtimestamp(block.get("timestamp", 0), tz=timezone.utc)
        tx_list = txs if isinstance(txs, Iterable) else []
        logger.debug("Ethereum ingestor fetched block with %s txs", len(tx_list))

        with SessionLocal() as session:
            eth_chain = session.query(Chain).filter(Chain.slug == "ethereum").one_or_none()
            if not eth_chain:
                logger.debug("Ethereum chain missing in DB; skipping tick")
                return
            whales = {
                w.address.lower(): w
                for w in session.query(Whale).filter(Whale.chain_id == eth_chain.id).all()
            }
            if not whales:
                logger.debug("No Ethereum whales configured; skipping tick")
                return

            self._eth_price_usd = self._fetch_eth_price()
            whale_addresses = set(whales.keys())

            for tx in tx_list:
                tx_hash = tx.get("hash")
                from_addr = tx.get("from", "").lower()
                to_addr = (tx.get("to") or "").lower()

                # ERC20 via receipt logs (broader than direct transfer call)
                if tx_hash:
                    try:
                        receipt = get_transaction_receipt(tx_hash)
                        self._record_receipt_transfers(
                            session, eth_chain.id, receipt, whales, whale_addresses, timestamp
                        )
                    except Exception:
                        pass

                # Native ETH transfer path
                if from_addr in whale_addresses or to_addr in whale_addresses:
                    whale = whales.get(from_addr) or whales.get(to_addr)
                    if whale:
                        self._record_transfer(session, eth_chain.id, whale, tx, timestamp)

            session.commit()

    def backfill_whale(self, session, chain_id: int, whale: Whale) -> bool:
        if not settings.ethereum_rpc_http_url:
            logger.warning("Ethereum RPC HTTP URL not configured; skipping backfill for %s", whale.address)
            return False
        logger.info("Ethereum backfill is not yet implemented; configure an RPC scanner to populate %s", whale.address)
        return False

    def _record_transfer(
        self,
        session,
        chain_id: int,
        whale: Whale,
        tx: dict,
        timestamp: datetime,
    ) -> None:
        value_wei = tx.get("value", 0)
        value_eth = Web3.from_wei(value_wei, "ether")
        direction = (
            TradeDirection.DEPOSIT
            if tx.get("to", "").lower() == whale.address.lower()
            else TradeDirection.WITHDRAW
        )
        counterparty = (
            tx.get("to", "").lower()
            if direction == TradeDirection.WITHDRAW
            else tx.get("from", "").lower()
        )

        source, platform = self._classify(counterparty)
        value_usd = None
        if self._eth_price_usd is not None:
            value_usd = float(value_eth) * float(self._eth_price_usd)

        if self._trade_exists(session, tx.get("hash"), "ETH"):
            return

        trade = Trade(
            whale_id=whale.id,
            timestamp=timestamp,
            chain_id=chain_id,
            source=source,
            platform=platform,
            direction=direction,
            base_asset="ETH",
            quote_asset="USD",
            amount_base=value_eth,
            amount_quote=None,
            value_usd=value_usd,
            pnl_usd=None,
            pnl_percent=None,
            tx_hash=tx.get("hash"),
            external_url=None,
        )
        session.add(trade)
        self._record_event(
            session,
            chain_id,
            whale,
            timestamp,
            EventType.LARGE_TRANSFER,
            value_usd,
            tx.get("hash"),
            summary=f"ETH {direction.value}",
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
        msg = {
            "id": tx_hash or "",
            "timestamp": timestamp.isoformat(),
            "chain": "ethereum",
            "type": event_type.value if hasattr(event_type, "value") else str(event_type),
            "wallet": {
                "address": whale.address,
                "chain": "ethereum",
                "label": (whale.labels or [None])[0] if whale.labels else None,
            },
            "summary": summary,
            "value_usd": value_usd or 0.0,
            "tx_hash": tx_hash,
            "details": {},
        }
        self._schedule_broadcast(msg)

    def _schedule_broadcast(self, msg: dict) -> None:
        try:
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(asyncio.create_task, broadcast_manager.broadcast(msg))
        except Exception:
            logger.debug("Ethereum broadcast scheduling failed", exc_info=True)

    def _record_receipt_transfers(
        self,
        session,
        chain_id: int,
        receipt: dict,
        whales: dict[str, Whale],
        whale_addresses: set[str],
        timestamp: datetime,
    ) -> None:
        logs = receipt.get("logs", []) if isinstance(receipt, dict) else []
        tx_hash = receipt.get("transactionHash") if isinstance(receipt, dict) else None
        tx_hash_hex = tx_hash.hex() if hasattr(tx_hash, "hex") else tx_hash
        for log in logs:
            address = (log.get("address") or "").lower()
            topics = [t.hex() if hasattr(t, "hex") else str(t) for t in log.get("topics", [])]
            if not topics:
                continue
            topic0 = topics[0].lower()

            if topic0 == TRANSFER_TOPIC:
                meta = ensure_token_meta(
                    address, decimals_fetcher=get_erc20_decimals, symbol_fetcher=get_erc20_symbol
                )
                if len(topics) < 3:
                    continue
                sender = "0x" + topics[1][-40:]
                recipient = "0x" + topics[2][-40:]
                data = log.get("data") or "0x0"
                try:
                    amount_int = int(data, 16)
                except Exception:
                    continue
                sender_l = sender.lower()
                recipient_l = recipient.lower()

                whale: Whale | None = None
                direction: TradeDirection | None = None
                if sender_l in whale_addresses:
                    whale = whales[sender_l]
                    direction = TradeDirection.WITHDRAW
                if recipient_l in whale_addresses:
                    whale = whales.get(recipient_l) or whale
                    direction = direction or TradeDirection.DEPOSIT

                if not whale or not direction:
                    continue

                decimals = meta.get("decimals") or 18
                amount_base = Decimal(amount_int) / Decimal(10**int(decimals))
                coingecko_id = meta.get("coingecko_id")
                price_usd = self._fetch_token_price(
                    str(coingecko_id) if coingecko_id else None,
                    contract_address=address,
                )
                value_usd = float(amount_base) * float(price_usd) if price_usd is not None else None

                source, platform = self._classify(
                    sender_l if direction == TradeDirection.DEPOSIT else recipient_l
                )

                tx_key = f"{tx_hash_hex}:{log.get('logIndex')}"
                if self._trade_exists(session, tx_key, str(meta.get("symbol") or "ERC20")):
                    continue

                trade = Trade(
                    whale_id=whale.id,
                    timestamp=timestamp,
                    chain_id=chain_id,
                    source=source,
                    platform=platform,
                    direction=direction,
                    base_asset=str(meta.get("symbol") or "ERC20"),
                    quote_asset="USD",
                    amount_base=amount_base,
                    amount_quote=None,
                    value_usd=value_usd,
                    pnl_usd=None,
                    pnl_percent=None,
                    tx_hash=tx_key,
                    external_url=None,
                )
                session.add(trade)
                self._record_event(
                    session,
                    chain_id,
                    whale,
                    timestamp,
                    EventType.LARGE_SWAP,
                    value_usd,
                    tx_key,
                    summary=f"{meta.get('symbol') or 'ERC20'} {direction.value}",
                )
                touch_last_active(session, whale, timestamp)

            elif topic0 == SWAP_TOPIC:
                self._record_swap(session, chain_id, whales, whale_addresses, log, tx_hash_hex, timestamp)

    def _fetch_eth_price(self) -> float | None:
        try:
            prices = coingecko_client.get_simple_price(["ethereum"])
            return prices.get("ethereum")
        except Exception:
            return None

    def _fetch_token_price(self, coingecko_id: str | None, contract_address: str | None = None) -> float | None:
        if coingecko_id and coingecko_id in self._token_prices:
            return self._token_prices[coingecko_id]
        price: float | None = None
        try:
            if coingecko_id:
                prices = coingecko_client.get_simple_price([coingecko_id])
                price = prices.get(coingecko_id)
            if price is None and contract_address:
                price = coingecko_client.get_contract_price("ethereum", contract_address)
            if price is not None and coingecko_id:
                self._token_prices[coingecko_id] = price
            return price
        except Exception:
            return None

    def _trade_exists(self, session, tx_hash: str | None, base_asset: str) -> bool:
        if not tx_hash:
            return False
        exists = session.scalar(
            select(Trade.id).where(Trade.tx_hash == tx_hash, Trade.base_asset == base_asset)
        )
        return bool(exists)

    def _record_swap(
        self,
        session,
        chain_id: int,
        whales: dict[str, Whale],
        whale_addresses: set[str],
        log: dict,
        tx_hash_hex: str | None,
        timestamp: datetime,
    ) -> None:
        topics = [t.hex() if hasattr(t, "hex") else str(t) for t in log.get("topics", [])]
        if len(topics) < 3:
            return
        sender = "0x" + topics[1][-40:]
        recipient = "0x" + topics[2][-40:]
        sender_l = sender.lower()
        recipient_l = recipient.lower()
        if sender_l not in whale_addresses and recipient_l not in whale_addresses:
            return
        whale = whales.get(sender_l) or whales.get(recipient_l)
        if not whale:
            return

        data = (log.get("data") or "0x")[2:]
        if len(data) < 64 * 4:
            return
        try:
            chunks = [int(data[i : i + 64], 16) for i in range(0, 64 * 4, 64)]
            amount0_in, amount1_in, amount0_out, amount1_out = chunks
        except Exception:
            return

        pair_addr = (log.get("address") or "").lower()
        tokens = get_pair_tokens(pair_addr)
        if not tokens:
            return
        token0, token1 = tokens
        meta0 = ensure_token_meta(token0, get_erc20_decimals, get_erc20_symbol)
        meta1 = ensure_token_meta(token1, get_erc20_decimals, get_erc20_symbol)

        dec0 = meta0.get("decimals") or 18
        dec1 = meta1.get("decimals") or 18
        amt0_in = Decimal(amount0_in) / Decimal(10**int(dec0))
        amt1_in = Decimal(amount1_in) / Decimal(10**int(dec1))
        amt0_out = Decimal(amount0_out) / Decimal(10**int(dec0))
        amt1_out = Decimal(amount1_out) / Decimal(10**int(dec1))

        # Determine swap direction (approximate)
        if amt0_in > 0 and amt1_out > 0:
            sold_symbol, bought_symbol = meta0.get("symbol") or "TOKEN0", meta1.get("symbol") or "TOKEN1"
            sold_amount, bought_amount = amt0_in, amt1_out
            sold_price = self._fetch_token_price(str(meta0.get("coingecko_id")), token0)
            bought_price = self._fetch_token_price(str(meta1.get("coingecko_id")), token1)
        elif amt1_in > 0 and amt0_out > 0:
            sold_symbol, bought_symbol = meta1.get("symbol") or "TOKEN1", meta0.get("symbol") or "TOKEN0"
            sold_amount, bought_amount = amt1_in, amt0_out
            sold_price = self._fetch_token_price(str(meta1.get("coingecko_id")), token1)
            bought_price = self._fetch_token_price(str(meta0.get("coingecko_id")), token0)
        else:
            return

        direction = TradeDirection.SELL if sender_l == whale.address.lower() else TradeDirection.BUY
        base_asset = bought_symbol if direction == TradeDirection.BUY else sold_symbol
        amount_base = bought_amount if direction == TradeDirection.BUY else sold_amount
        price_usd = bought_price if direction == TradeDirection.BUY else sold_price
        value_usd = float(amount_base) * float(price_usd) if price_usd is not None else None

        tx_key = f"{tx_hash_hex}:{log.get('logIndex')}:swap"
        if self._trade_exists(session, tx_key, base_asset):
            return

        trade = Trade(
            whale_id=whale.id,
            timestamp=timestamp,
            chain_id=chain_id,
            source=TradeSource.ONCHAIN,
            platform="uniswap_v2",
            direction=direction,
            base_asset=base_asset,
            quote_asset="USD",
            amount_base=amount_base,
            amount_quote=None,
            value_usd=value_usd,
            pnl_usd=None,
            pnl_percent=None,
            tx_hash=tx_key,
            external_url=None,
        )
        session.add(trade)
        self._record_event(
            session,
            chain_id,
            whale,
            timestamp,
            EventType.LARGE_SWAP,
            value_usd,
            tx_key,
            summary=f"Swap {sold_symbol}->{bought_symbol}",
        )
        touch_last_active(session, whale, timestamp)

    def _classify(self, counterparty: str) -> tuple[TradeSource, str]:
        counterparty = counterparty.lower()
        if counterparty in EXCHANGE_ADDRESSES:
            return TradeSource.EXCHANGE_FLOW, "exchange_flow"
        if counterparty in BRIDGE_ADDRESSES:
            return TradeSource.EXCHANGE_FLOW, "bridge"
        return TradeSource.ONCHAIN, "ethereum"


EXCHANGE_ADDRESSES = {
    "0xbe0eb53f46cd790cd13851d5eff43d12404d33e8",
    "0x40b38765696e3d5d8d9d834d8aad4bb6e418e489",
    "0x73af3bcf944a6559933396c1577b257e2054d935",
    "0x0e58e8993100f1cbe45376c410f97f4893d9bfcd",
    "0xf977814e90da44bfa03b6295a0616a897441acec",
    "0x47ac0fb4f2d84898e4d9e7b4dab3c24507a6d503",
    "0xafcd96e580138cfa2332c632e66308eacd45c5da",
    "0xe92d1a43df510f82c66382592a047d288f85226f",
    "0x742d35cc6634c0532925a3b844bc454e4438f44e",
    "0x8d05d9924fe935bd533a844271a1b2078eae6fcf",
    "0x564286362092d8e7936f0549571a803b203aaced",  # Binance 7
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45",  # Uniswap Router
    "0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f",  # Uniswap Factory
    "0xd551234ae421e3bcba99a0da6d736074f22192ff",  # Huobi
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549",  # OKX
    "0x4e83362442b8d1bec281594cea3050c8eb01311c",  # Binance 14
    "0x28c6c06298d514db089934071355e5743bf21d60",  # Binance 14 alt
    "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",  # Binance 8
}

BRIDGE_ADDRESSES = {
    "0x49048044d57e1c92a77f79988d21fa8faf74e97e",
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a",
    "0x3bfc20f0b9afcac e800d73d2191166ff16540258".replace(" ", ""),
    "0xa160cdab225685da1d56aa342ad8841c3b53f291",
}

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
SWAP_TOPIC = "0xd78ad95fa46c994b6551d0da85fc275fe6136a68d02d1a17e0c7d7f38d07c6c8"  # Uniswap V2 Swap

ERC20_METADATA: dict[str, dict[str, str | int | None]] = {
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": {
        "symbol": "USDC",
        "decimals": 6,
        "coingecko_id": "usd-coin",
    },
    "0xdac17f958d2ee523a2206206994597c13d831ec7": {
        "symbol": "USDT",
        "decimals": 6,
        "coingecko_id": "tether",
    },
    "0x6b175474e89094c44da98b954eedeac495271d0f": {
        "symbol": "DAI",
        "decimals": 18,
        "coingecko_id": "dai",
    },
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2": {
        "symbol": "WETH",
        "decimals": 18,
        "coingecko_id": "weth",
    },
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599": {
        "symbol": "WBTC",
        "decimals": 8,
        "coingecko_id": "wrapped-bitcoin",
    },
    "0x514910771af9ca656af840dff83e8264ecf986ca": {
        "symbol": "LINK",
        "decimals": 18,
        "coingecko_id": "chainlink",
    },
    "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9": {
        "symbol": "AAVE",
        "decimals": 18,
        "coingecko_id": "aave",
    },
    "0x5a98fcbea516cf06857215779fd812ca3bef1b32": {
        "symbol": "LDO",
        "decimals": 18,
        "coingecko_id": "lido-dao",
    },
    "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984".lower(): {
        "symbol": "UNI",
        "decimals": 18,
        "coingecko_id": "uniswap",
    },
    "0x0baba1ad5cc0c5b6d5c7e5e9f04f0416f21eb4ba": {
        "symbol": "ARB",
        "decimals": 18,
        "coingecko_id": "arbitrum",
    },
    "0x4200000000000000000000000000000000000042": {
        "symbol": "OP",
        "decimals": 18,
        "coingecko_id": "optimism",
    },
    "0x7d1afa7b718fb893db30a3abc0cfc608aacfebb0": {
        "symbol": "MATIC",
        "decimals": 18,
        "coingecko_id": "matic-network",
    },
    "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce": {
        "symbol": "SHIB",
        "decimals": 18,
        "coingecko_id": "shiba-inu",
    },
    "0xbebb9cc92c78ef8a7a48e7ec3d8f5f8ce7b4f2cc": {
        "symbol": "PEPE",
        "decimals": 18,
        "coingecko_id": "pepe",
    },
}
