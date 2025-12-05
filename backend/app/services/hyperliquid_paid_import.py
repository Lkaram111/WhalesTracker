from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable, Iterable
import tempfile
import os
from pathlib import Path

import boto3
import lz4.frame
from botocore.exceptions import NoCredentialsError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chain, Trade, TradeDirection, TradeSource, Whale
from app.services.metrics_service import recompute_wallet_metrics, _commit_with_retry, rebuild_portfolio_history_from_trades
from app.core.time_utils import now
from app.core.config import settings
from app.services.backfill_progress import BackfillProgressTracker


def _daterange(start: date, end: date) -> Iterable[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _parse_direction(dir_str: str | None, side: str | None) -> TradeDirection:
    s = (dir_str or side or "").lower()
    if "close" in s and "short" in s:
        return TradeDirection.CLOSE_SHORT
    if "close" in s and "long" in s:
        return TradeDirection.CLOSE_LONG
    if "short" in s:
        return TradeDirection.SHORT
    if "long" in s:
        return TradeDirection.LONG
    return TradeDirection.SHORT if (side or "").lower() == "a" else TradeDirection.LONG


def _maybe_float(val) -> float | None:
    try:
        return float(val)
    except Exception:
        return None


def _process_fill(session: Session, whale: Whale, chain_id: int, fill: dict) -> bool:
    ts_ms = fill.get("time") or fill.get("timestamp")
    if not ts_ms:
        return False
    try:
        timestamp = datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc)
    except Exception:
        return False
    coin = fill.get("coin") or fill.get("ticker") or "PERP"
    sz = _maybe_float(fill.get("sz"))
    px = _maybe_float(fill.get("px"))
    dir_str = fill.get("dir") or fill.get("direction")
    side = fill.get("side")
    direction = _parse_direction(dir_str, side)
    value_usd = None
    if sz is not None and px is not None:
        value_usd = abs(sz * px)
    pnl_usd = _maybe_float(fill.get("closedPnl"))

    # Avoid dropping duplicate fills from the same tx: include tid when available.
    raw_hash = fill.get("hash") or ""
    tid = fill.get("tid")
    tx_hash = f"{raw_hash}:{tid}" if tid is not None else raw_hash or str(fill.get("oid") or "")
    if tx_hash:
        exists = session.scalar(select(Trade.id).where(Trade.tx_hash == tx_hash, Trade.whale_id == whale.id))
        if exists:
            return False

    trade = Trade(
        whale_id=whale.id,
        timestamp=timestamp,
        chain_id=chain_id,
        source=TradeSource.HYPERLIQUID,
        platform="hyperliquid",
        direction=direction,
        base_asset=coin,
        quote_asset="USD",
        amount_base=Decimal(str(sz)) if sz is not None else None,
        amount_quote=None,
        value_usd=value_usd,
        pnl_usd=pnl_usd,
        pnl_percent=None,
        tx_hash=tx_hash or None,
        external_url=None,
    )
    session.add(trade)
    return True


def _iter_wallet_fills_from_line(obj: object, wallet_lower: str):
    """
    Yield fill dicts for the given wallet from a parsed JSON line.

    Supports:
    - node_fills_by_block: {"events": [[user_addr, {fill...}], ...]}
    - node_fills (API format): [user_addr, {fill...}]
    - direct dict with user (future-proof)
    """
    if isinstance(obj, dict) and "events" in obj:
        for event in obj.get("events", []):
            if not isinstance(event, list) or len(event) != 2:
                continue
            user_addr, fill = event
            if not isinstance(fill, dict):
                continue
            if str(user_addr or "").lower() != wallet_lower:
                continue
            fill_dict = dict(fill)
            fill_dict.setdefault("user", user_addr)
            yield fill_dict
        return

    if isinstance(obj, list) and len(obj) == 2 and isinstance(obj[0], str) and isinstance(obj[1], dict):
        user_addr, fill = obj
        if str(user_addr or "").lower() != wallet_lower:
            return
        fill_dict = dict(fill)
        fill_dict.setdefault("user", user_addr)
        yield fill_dict
        return

    if isinstance(obj, dict):
        user_addr = obj.get("user")
        if isinstance(user_addr, str) and user_addr.lower() == wallet_lower:
            yield obj


def import_hl_history_from_s3(
    session: Session,
    whale: Whale,
    start: date,
    end: date,
    progress_cb: Callable[[float | None, str | None], None] | None = None,
) -> dict:
    """
    Fetch Hyperliquid historical fills from public S3 (requester pays) and import for a wallet.
    Requires AWS credentials in env; requester pays egress fees.
    """
    chain = session.scalar(select(Chain).where(Chain.slug == "hyperliquid"))
    if not chain:
        return {"imported": 0, "skipped": 0, "missing_chain": True}

    # Use AWS profile from settings or environment variable
    aws_profile = settings.aws_profile or os.environ.get("AWS_PROFILE")
    if aws_profile:
        boto3_session = boto3.Session(profile_name=aws_profile)
        s3 = boto3_session.client("s3")
    else:
        s3 = boto3.client("s3")
    bucket = "hl-mainnet-node-data"
    cache_root = Path(__file__).resolve().parent.parent / "data" / "hyperliquid_s3"
    prefixes = []
    for d in _daterange(start, end):
        day_str = d.strftime("%Y%m%d")
        prefixes.append(f"node_fills_by_block/hourly/{day_str}/")
        prefixes.append(f"node_fills/hourly/{day_str}/")

    def _iter_s3_keys(prefix: str):
        continuation = None
        while True:
            resp = s3.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix,
                RequestPayer="requester",
                **({"ContinuationToken": continuation} if continuation else {}),
            )
            for obj in resp.get("Contents", []):
                yield obj["Key"]
            if not resp.get("IsTruncated"):
                break
            continuation = resp.get("NextContinuationToken")

    def _iter_cached_keys(prefix: str) -> list[str]:
        base_dir = cache_root / prefix
        if not base_dir.exists():
            return []
        return [
            str(path.relative_to(cache_root)).replace("\\", "/")
            for path in base_dir.rglob("*")
            if path.is_file()
        ]

    imported = 0
    skipped = 0
    downloaded_files = 0
    reused_files = 0
    missing_files = 0
    corrupted_files = 0
    redownloaded_files = 0
    listed_files = 0
    listed_from_cache = 0
    s3_errors: list[str] = []
    keys_to_process: list[str] = []
    seen_keys: set[str] = set()
    wallet_lower = whale.address.lower()
    s3_available = True
    def _emit(progress: float | None = None, message: str | None = None) -> None:
        if progress_cb:
            progress_cb(progress, message)

    # Phase 1: list keys for the date range (cached first, then S3) before any download.
    _emit(2.0, f"Listing Hyperliquid S3 keys for {start} to {end}")
    for prefix in prefixes:
        for key in _iter_cached_keys(prefix):
            if key in seen_keys:
                continue
            seen_keys.add(key)
            keys_to_process.append(key)
            listed_from_cache += 1
    for prefix in prefixes:
        if not s3_available:
            break
        try:
            for key in _iter_s3_keys(prefix):
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                keys_to_process.append(key)
        except NoCredentialsError:
            s3_errors.append("Missing AWS credentials: processed cached Hyperliquid files only.")
            s3_available = False
        except Exception as exc:  # noqa: BLE001
            s3_errors.append(f"S3 list failed for {prefix}: {exc}")
            continue
    listed_files = len(keys_to_process)
    # Process keys in order to keep downloads predictable.
    keys_to_process.sort()
    _emit(5.0, f"Found {listed_files} files ({listed_from_cache} cached)")

    def _read_cached_file(path: Path) -> bool:
        nonlocal imported, skipped
        try:
            with lz4.frame.open(path, "rb") as fh:
                for raw_line in fh:
                    try:
                        line = raw_line.decode("utf-8").strip()
                    except Exception:
                        skipped += 1
                        continue
                    if not line:
                        continue
                    try:
                        parsed = json.loads(line)
                    except Exception:
                        skipped += 1
                        continue

                    for fill in _iter_wallet_fills_from_line(parsed, wallet_lower):
                        if _process_fill(session, whale, chain.id, fill):
                            imported += 1
                        else:
                            skipped += 1
            return True
        except FileNotFoundError:
            return False
        except EOFError:
            return False
        except Exception:
            # Any unexpected read error should not break the whole import.
            return False

    total_keys = max(1, len(keys_to_process))
    processed_keys = 0

    for key in keys_to_process:
        cached_path = cache_root / key
        cached_path.parent.mkdir(parents=True, exist_ok=True)
        needs_download = not cached_path.exists() or cached_path.stat().st_size == 0
        if needs_download:
            if not s3_available:
                missing_files += 1
                continue
            try:
                obj = s3.get_object(Bucket=bucket, Key=key, RequestPayer="requester")
                body = obj["Body"]
                with open(cached_path, "wb") as fh:
                    fh.write(body.read())
                downloaded_files += 1
            except NoCredentialsError:
                s3_errors.append("Missing AWS credentials while downloading Hyperliquid history.")
                s3_available = False
                missing_files += 1
                continue
            except Exception as exc:  # noqa: BLE001
                s3_errors.append(f"Failed to download {key}: {exc}")
                missing_files += 1
                continue
            else:
                reused_files += 1

        read_ok = _read_cached_file(cached_path)
        if not read_ok:
            corrupted_files += 1
            if s3_available:
                try:
                    obj = s3.get_object(Bucket=bucket, Key=key, RequestPayer="requester")
                    body = obj["Body"]
                    with open(cached_path, "wb") as fh:
                        fh.write(body.read())
                    redownloaded_files += 1
                    read_ok = _read_cached_file(cached_path)
                except NoCredentialsError:
                    s3_errors.append("Missing AWS credentials while re-downloading Hyperliquid history.")
                    s3_available = False
                except Exception as exc:  # noqa: BLE001
                    s3_errors.append(f"Failed to re-download {key}: {exc}")
            if not read_ok:
                missing_files += 1
                continue
        session.flush()
        processed_keys += 1
        pct = 5.0 + (processed_keys / total_keys) * 90.0
        _emit(pct, f"Processed {processed_keys}/{total_keys} files (imported {imported}, skipped {skipped})")

    if imported > 0:
        recompute_wallet_metrics(session, whale)
        rebuild_portfolio_history_from_trades(session, whale)
    _commit_with_retry(session)
    _emit(100.0, f"Done. Imported {imported}, skipped {skipped}.")
    return {
        "imported": imported,
        "skipped": skipped,
        "downloaded_files": downloaded_files,
        "reused_files": reused_files,
        "missing_files": missing_files,
        "corrupted_files": corrupted_files,
        "redownloaded_files": redownloaded_files,
        "listed_files": listed_files,
        "listed_from_cache": listed_from_cache,
        "s3_errors": s3_errors or None,
    }
