from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy.orm import Session
from web3 import Web3

from app.core.config import settings
from app.models import Chain, Holding, Whale
from app.services.bitcoin_client import bitcoin_client
from app.services.coingecko_client import coingecko_client
from app.services.ethereum_client import get_balance, get_erc20_balance, get_erc20_decimals
from app.services.token_meta import ERC20_METADATA, ensure_token_meta, get_token_meta, list_tracked_tokens


def _eth_price_usd() -> float | None:
    try:
        prices = coingecko_client.get_simple_price(["ethereum"])
        return prices.get("ethereum")
    except Exception:
        return None


def _fetch_token_price(token_address: str, coingecko_id: str | None) -> float | None:
    try:
        if coingecko_id:
            prices = coingecko_client.get_simple_price([coingecko_id])
            price = prices.get(coingecko_id)
            if price is not None:
                return price
        return coingecko_client.get_contract_price("ethereum", token_address)
    except Exception:
        return None


def refresh_eth_holdings(session: Session, whale: Whale, chain: Chain) -> None:
    if not settings.ethereum_rpc_http_url or "your-key" in settings.ethereum_rpc_http_url:
        return
    address = whale.address
    try:
        raw_balance = get_balance(address)
    except Exception:
        # Skip if RPC is unreachable
        return
    eth_amount = Decimal(Web3.from_wei(raw_balance, "ether"))
    eth_price = _eth_price_usd()
    value_usd = Decimal(eth_price) * eth_amount if eth_price is not None else None

    holding = (
        session.query(Holding)
        .filter(Holding.whale_id == whale.id, Holding.asset_symbol == "ETH")
        .one_or_none()
    )

    if holding:
        holding.amount = eth_amount
        holding.value_usd = value_usd
    else:
        session.add(
            Holding(
                whale_id=whale.id,
                asset_symbol="ETH",
                asset_name="Ether",
                chain_id=chain.id,
                amount=eth_amount,
                value_usd=value_usd,
                portfolio_percent=None,
            )
        )
    # ERC20 balances for tracked tokens (heuristic: tokens seen in metadata map/cache)
    for token_address in list_tracked_tokens():
        meta = ensure_token_meta(
            token_address,
            decimals_fetcher=get_erc20_decimals,
            symbol_fetcher=None,
        )
        try:
            raw_balance = get_erc20_balance(token_address, address)
        except Exception:
            continue
        if raw_balance is None or raw_balance == 0:
            continue
        decimals = get_erc20_decimals(token_address) or meta.get("decimals") or 18
        amount = Decimal(raw_balance) / Decimal(10**int(decimals))
        coingecko_id = meta.get("coingecko_id")
        price_usd = _fetch_token_price(token_address, coingecko_id)
        value_usd = Decimal(price_usd) * amount if price_usd is not None else None

        asset_symbol = str(meta.get("symbol") or token_address[:6])
        holding = (
            session.query(Holding)
            .filter(Holding.whale_id == whale.id, Holding.asset_symbol == asset_symbol)
            .one_or_none()
        )
        if holding:
            holding.amount = amount
            holding.value_usd = value_usd
        else:
            session.add(
                Holding(
                    whale_id=whale.id,
                    asset_symbol=asset_symbol,
                    asset_name=asset_symbol,
                    chain_id=chain.id,
                    amount=amount,
                    value_usd=value_usd,
                    portfolio_percent=None,
                )
            )


def refresh_btc_holdings(session: Session, whale: Whale, chain: Chain) -> None:
    try:
        data = bitcoin_client.get_address(whale.address)
    except Exception:
        return

    stats = data.get("chain_stats") or data.get("mempool_stats") or {}
    funded = stats.get("funded_txo_sum", 0) or 0
    spent = stats.get("spent_txo_sum", 0) or 0
    sats_balance = funded - spent
    btc_amount = Decimal(sats_balance) / Decimal(1e8)
    btc_price = _btc_price_usd()
    value_usd = Decimal(btc_price) * btc_amount if btc_price is not None else None

    holding = (
        session.query(Holding)
        .filter(Holding.whale_id == whale.id, Holding.asset_symbol == "BTC")
        .one_or_none()
    )

    if holding:
        holding.amount = btc_amount
        holding.value_usd = value_usd
    else:
        session.add(
            Holding(
                whale_id=whale.id,
                asset_symbol="BTC",
                asset_name="Bitcoin",
                chain_id=chain.id,
                amount=btc_amount,
                value_usd=value_usd,
                portfolio_percent=None,
            )
        )


def _btc_price_usd() -> float | None:
    try:
        prices = coingecko_client.get_simple_price(["bitcoin"])
        return prices.get("bitcoin")
    except Exception:
        return None


def refresh_holdings_for_whales(session: Session, whales: Iterable[Whale]) -> None:
    chain_map = {c.id: c for c in session.query(Chain).all()}
    for whale in whales:
        chain = chain_map.get(whale.chain_id)
        if not chain:
            continue
        if chain.slug == "ethereum":
            refresh_eth_holdings(session, whale, chain)
        elif chain.slug == "bitcoin":
            refresh_btc_holdings(session, whale, chain)
    session.commit()
