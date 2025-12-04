from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, List, Optional

import httpx
from httpx import HTTPStatusError
from eth_account import Account  # type: ignore
from eth_account.messages import encode_typed_data  # type: ignore
from eth_account.signers.local import LocalAccount  # type: ignore
from eth_utils import keccak, to_hex
import msgpack

from app.core.config import settings


def _address_to_bytes(address: str) -> bytes:
    return bytes.fromhex(address[2:] if address.startswith("0x") else address)


def _action_hash(action: dict[str, Any], vault_address: str | None, nonce: int, expires_after: int | None) -> bytes:
    data = msgpack.packb(action)
    data += nonce.to_bytes(8, "big")
    if vault_address is None:
        data += b"\x00"
    else:
        data += b"\x01"
        data += _address_to_bytes(vault_address)
    if expires_after is not None:
        data += b"\x00"
        data += expires_after.to_bytes(8, "big")
    return keccak(data)


def _construct_phantom_agent(hash_val: bytes, is_mainnet: bool) -> dict[str, Any]:
    return {"source": "a" if is_mainnet else "b", "connectionId": hash_val}


def _l1_payload(phantom_agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain": {
            "chainId": 1337,
            "name": "Exchange",
            "verifyingContract": "0x0000000000000000000000000000000000000000",
            "version": "1",
        },
        "types": {
            "Agent": [
                {"name": "source", "type": "string"},
                {"name": "connectionId", "type": "bytes32"},
            ],
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
        },
        "primaryType": "Agent",
        "message": phantom_agent,
    }


def _sign_l1_action(
    wallet: LocalAccount,
    action: dict[str, Any],
    vault_address: str | None,
    nonce: int,
    expires_after: int | None,
    is_mainnet: bool,
) -> dict[str, Any]:
    hash_val = _action_hash(action, vault_address, nonce, expires_after)
    phantom_agent = _construct_phantom_agent(hash_val, is_mainnet)
    data = _l1_payload(phantom_agent)
    structured = encode_typed_data(full_message=data)
    signed = wallet.sign_message(structured)
    return {"r": to_hex(signed["r"]), "s": to_hex(signed["s"]), "v": signed["v"]}


class HyperliquidMeta:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip('/info').rstrip('/')
        self.timeout = timeout
        self.coin_to_asset: dict[str, int] = {}
        self.asset_to_sz_decimals: dict[int, int] = {}
        self._loaded = False

    def _post_info(self, payload: dict[str, Any]) -> Any:
        with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
            resp = client.post('/info', json=payload)
            resp.raise_for_status()
            return resp.json()

    def load(self) -> None:
        meta = self._post_info({"type": "meta"})
        spot_meta = self._post_info({"type": "spotMeta"})
        self.coin_to_asset.clear()
        self.asset_to_sz_decimals.clear()
        universe = meta.get("universe") or []
        for asset_id, entry in enumerate(universe):
            name = entry.get("name")
            sz_decimals = entry.get("szDecimals")
            if name is None or sz_decimals is None:
                continue
            self.coin_to_asset[name.upper()] = asset_id
            self.asset_to_sz_decimals[asset_id] = int(sz_decimals)
        spot_universe = spot_meta.get("universe") or []
        tokens = spot_meta.get("tokens") or []
        spot_offset = 10000
        for spot in spot_universe:
            asset_id = spot.get("index")
            name = spot.get("name")
            token_indices = spot.get("tokens") or []
            if asset_id is None or name is None or not token_indices:
                continue
            asset_id = int(asset_id) + spot_offset
            token_idx = int(token_indices[0])
            sz_decimals = tokens[token_idx].get("szDecimals") if token_idx < len(tokens) else None
            if sz_decimals is None:
                continue
            self.coin_to_asset[name.upper()] = asset_id
            self.asset_to_sz_decimals[asset_id] = int(sz_decimals)
        self._loaded = True

    def asset_id(self, coin: str) -> Optional[int]:
        if not self._loaded:
            self.load()
        return self.coin_to_asset.get((coin or '').upper())

    def sz_decimals(self, asset_id: int | None) -> int:
        if not self._loaded:
            self.load()
        if asset_id is None:
            return 4
        return self.asset_to_sz_decimals.get(asset_id, 4)


class HyperliquidTradingClient:
    """Hyperliquid trading helper using wire format similar to official SDK (EIP-712 signed actions)."""

    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = (base_url or settings.hyperliquid_info_url).rstrip("/info").rstrip("/")
        self.timeout = timeout
        self._priv = settings.hyperliquid_private_key
        self._addr = settings.hyperliquid_address
        self._slippage_pct = float(settings.hyperliquid_slippage_pct or 1.0)
        self.meta = HyperliquidMeta(self.base_url, timeout=timeout)
        self._acct: LocalAccount | None = Account.from_key(self._priv) if self._priv else None
        rps = float(getattr(settings, "hyperliquid_max_rps", 3.0) or 3.0)
        self._min_interval = 1.0 / max(rps, 0.1)
        self._last_ts = 0.0
        self._lock = threading.Lock()
        self._is_mainnet = "api.hyperliquid.xyz" in self.base_url

    def _post_exchange(self, action: dict[str, Any]) -> dict[str, Any]:
        if not self._acct:
            raise RuntimeError('Hyperliquid private key not configured')
        nonce = int(time.time() * 1000)
        expires_after: int | None = None
        vault_address: str | None = None
        signature = _sign_l1_action(self._acct, action, vault_address, nonce, expires_after, self._is_mainnet)
        body = {
            'action': action,
            'nonce': nonce,
            'signature': signature,
            'vaultAddress': vault_address,
            'expiresAfter': expires_after,
        }
        last_err: Exception | None = None
        for attempt in range(1, 4):
            with self._lock:
                now = time.perf_counter()
                sleep_for = self._min_interval - (now - self._last_ts)
                if sleep_for > 0:
                    time.sleep(sleep_for)
                self._last_ts = time.perf_counter()
            try:
                with httpx.Client(base_url=self.base_url, timeout=self.timeout) as client:
                    resp = client.post('/exchange', json=body)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "0") or 0)
                    delay = retry_after if retry_after > 0 else min(2**attempt, 5)
                    time.sleep(delay)
                    last_err = httpx.HTTPStatusError("429 Too Many Requests", request=resp.request, response=resp)
                    continue
                resp.raise_for_status()
                return resp.json()
            except HTTPStatusError as exc:
                # Include server body to aid debugging (e.g., schema mismatches)
                detail = exc.response.text
                last_err = HTTPStatusError(f"{exc} body={detail}", request=exc.request, response=exc.response)
                if attempt < 3 and exc.response.status_code in (422, 500, 502, 503, 504):
                    time.sleep(min(2**attempt, 5))
                    continue
                raise last_err
            except Exception as exc:  # noqa: PERF203
                last_err = exc
                if attempt < 3:
                    time.sleep(min(2**attempt, 5))
                    continue
                raise
        if last_err:
            raise last_err

    def _round_sigfigs(self, num: float, sig_figs: int = 5) -> float:
        if num == 0:
            return 0.0
        return round(num, sig_figs - int(math.floor(math.log10(abs(num)))) - 1)

    def _round_to_decimals(self, num: float, decimals: int) -> float:
        return round(num, max(decimals, 0))

    def _slippage_price(self, coin: str, is_buy: bool, px: float) -> float:
        price = px * (1 + self._slippage_pct / 100.0) if is_buy else px * (1 - self._slippage_pct / 100.0)
        price = self._round_sigfigs(price, 5)
        asset_id = self.meta.asset_id(coin)
        asset_dec = self.meta.sz_decimals(asset_id)
        decimals = (6 if (asset_id is not None and asset_id < 10000) else 8) - asset_dec
        return self._round_to_decimals(price, decimals)

    def _round_size(self, coin: str, sz: float) -> float:
        asset_id = self.meta.asset_id(coin)
        sz_dec = self.meta.sz_decimals(asset_id)
        return self._round_to_decimals(sz, sz_dec)

    def update_leverage(self, coin: str, leverage: float, is_cross: bool = True) -> dict[str, Any]:
        if self._addr is None:
            raise RuntimeError('Hyperliquid address not configured')
        asset_id = self.meta.asset_id(coin)
        if asset_id is None:
            raise RuntimeError(f'Unknown asset {coin}')
        action: dict[str, Any] = {
            'type': 'updateLeverage',
            'asset': asset_id,
            'isCross': bool(is_cross),
            'leverage': int(leverage),
        }
        return self._post_exchange(action)

    def submit_orders(self, orders: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self._addr:
            raise RuntimeError('Hyperliquid address not configured')
        action: Dict[str, Any] = {'type': 'order', 'orders': orders, 'grouping': 'na'}
        return self._post_exchange(action)

    def build_ioc_order(self, coin: str, is_buy: bool, sz: float, px: float, reduce_only: bool = False) -> Dict[str, Any]:
        asset_id = self.meta.asset_id(coin)
        if asset_id is None:
            raise RuntimeError(f'Unknown asset {coin}')
        rounded_sz = self._round_size(coin, sz)
        px_nudged = self._slippage_price(coin, is_buy, px)
        return {
            'a': asset_id,
            'b': bool(is_buy),
            'p': str(px_nudged),
            's': str(rounded_sz),
            'r': bool(reduce_only),
            't': {'limit': {'tif': 'Ioc'}},
        }

    def mid_price(self, coin: str) -> Optional[float]:
        try:
            mids = self.meta._post_info({'type': 'allMids'}) or {}
            val = mids.get(coin.upper())
            return float(val) if val is not None else None
        except Exception:
            return None


hyperliquid_trading_client = HyperliquidTradingClient()
