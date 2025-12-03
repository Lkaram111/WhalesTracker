from __future__ import annotations

from typing import Any

from web3 import HTTPProvider, Web3
from web3.exceptions import Web3Exception
from web3.contract import Contract

from app.core.config import settings

http_provider = HTTPProvider(settings.ethereum_rpc_http_url) if settings.ethereum_rpc_http_url else None
ws_url = settings.ethereum_rpc_ws_url or None

w3_http = Web3(http_provider) if http_provider else None


def require_http() -> Web3:
    if not w3_http:
        raise RuntimeError("ETH HTTP provider not configured")
    return w3_http


def require_ws() -> Web3:
    if not ws_url:
        raise RuntimeError("ETH WS provider not configured")
    return Web3(Web3.WebsocketProvider(ws_url))


def get_balance(address: str) -> int:
    client = require_http()
    try:
        return client.eth.get_balance(Web3.to_checksum_address(address))
    except Web3Exception as exc:
        raise RuntimeError(f"Failed to fetch balance for {address}") from exc


def get_block(block_number: int | str = "latest") -> Any:
    client = require_http()
    try:
        return client.eth.get_block(block_number, full_transactions=True)
    except Web3Exception as exc:
        raise RuntimeError(f"Failed to fetch block {block_number}") from exc


def get_transaction(tx_hash: str) -> Any:
    client = require_http()
    try:
        return client.eth.get_transaction(tx_hash)
    except Web3Exception as exc:
        raise RuntimeError(f"Failed to fetch transaction {tx_hash}") from exc


def get_logs(filter_params: dict) -> list[Any]:
    client = require_http()
    try:
        return client.eth.get_logs(filter_params)
    except Web3Exception as exc:
        raise RuntimeError(f"Failed to fetch logs for filter {filter_params}") from exc


def get_transaction_receipt(tx_hash: str) -> Any:
    client = require_http()
    try:
        return client.eth.get_transaction_receipt(tx_hash)
    except Web3Exception as exc:
        raise RuntimeError(f"Failed to fetch receipt {tx_hash}") from exc


_erc20_abi = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]


def _erc20_contract(address: str) -> Contract:
    client = require_http()
    return client.eth.contract(address=Web3.to_checksum_address(address), abi=_erc20_abi)


def get_erc20_balance(contract_address: str, owner: str) -> int:
    try:
        return _erc20_contract(contract_address).functions.balanceOf(Web3.to_checksum_address(owner)).call()
    except Web3Exception as exc:
        raise RuntimeError(f"Failed to fetch balance for {owner} on {contract_address}") from exc


def get_erc20_decimals(contract_address: str) -> int | None:
    try:
        return _erc20_contract(contract_address).functions.decimals().call()
    except Exception:
        return None


def get_erc20_symbol(contract_address: str) -> str | None:
    try:
        contract = _erc20_contract(contract_address)
        sym = contract.functions.symbol().call()
        return str(sym)
    except Exception:
        return None


_pair_abi = [
    {"constant": True, "inputs": [], "name": "token0", "outputs": [{"name": "", "type": "address"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "token1", "outputs": [{"name": "", "type": "address"}], "type": "function"},
]


def get_pair_tokens(pair_address: str) -> tuple[str, str] | None:
    try:
        client = require_http()
        contract = client.eth.contract(address=Web3.to_checksum_address(pair_address), abi=_pair_abi)
        t0 = contract.functions.token0().call()
        t1 = contract.functions.token1().call()
        return str(t0).lower(), str(t1).lower()
    except Exception:
        return None
