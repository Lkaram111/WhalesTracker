from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

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
    "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984": {
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

CACHE_PATH = Path(__file__).resolve().parents[2] / "config" / "token_cache.json"


def _load_cache() -> None:
    if CACHE_PATH.exists():
        try:
            data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, dict):
                        ERC20_METADATA.setdefault(k.lower(), v)
        except Exception:
            return


def _persist_cache() -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(ERC20_METADATA, indent=2), encoding="utf-8")
    except Exception:
        return


_load_cache()


def get_token_meta(address: str) -> dict[str, str | int | None]:
    addr = address.lower()
    if addr in ERC20_METADATA:
        return ERC20_METADATA[addr]
    return {"symbol": addr[:6], "decimals": 18, "coingecko_id": None}


def track_token(address: str, meta: dict[str, str | int | None]) -> None:
    ERC20_METADATA[address.lower()] = meta
    _persist_cache()


def ensure_token_meta(
    address: str,
    decimals_fetcher: Callable[[str], int | None] | None = None,
    symbol_fetcher: Callable[[str], str | None] | None = None,
) -> dict[str, str | int | None]:
    addr = address.lower()
    meta = get_token_meta(addr)
    updated = False
    if (meta.get("decimals") is None or meta.get("decimals") == 18) and decimals_fetcher:
        try:
            dec = decimals_fetcher(addr)
            if dec is not None:
                meta["decimals"] = dec
                updated = True
        except Exception:
            pass
    if (meta.get("symbol") is None or len(str(meta.get("symbol"))) <= 4) and symbol_fetcher:
        try:
            sym = symbol_fetcher(addr)
            if sym:
                meta["symbol"] = sym
                updated = True
        except Exception:
            pass
    ERC20_METADATA[addr] = meta
    if updated:
        _persist_cache()
    return meta


def list_tracked_tokens() -> list[str]:
    return list(ERC20_METADATA.keys())
