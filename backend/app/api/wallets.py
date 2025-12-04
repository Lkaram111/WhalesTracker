from datetime import datetime, timedelta, timezone
from typing import Iterable
import time

from fastapi import APIRouter, HTTPException, Path, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import OperationalError

from app.db.session import SessionLocal
from app.models import (
    Chain,
    CurrentWalletMetrics,
    Holding,
    Trade,
    TradeDirection,
    WalletMetricsDaily,
    Whale,
)
from app.schemas.api import (
    OpenPosition,
    PortfolioHistoryResponse,
    PositionsResponse,
    RoiHistoryResponse,
    TradesResponse,
    WalletDetail,
    WalletMetrics,
    WalletSummary,
)
from app.services.hyperliquid_client import hyperliquid_client
from app.services.metrics_service import (
    recompute_wallet_metrics,
    rebuild_portfolio_history_from_trades,
)
from app.core.time_utils import now

router = APIRouter()

EXPLORER_BASES = {
    "ethereum": "https://etherscan.io/address/",
    "bitcoin": "https://mempool.space/address/",
    "hyperliquid": "https://explorer.hyperliquid.xyz/account/",
}


def _commit_with_retry(session, retries: int = 3, delay: float = 0.5) -> None:
    for attempt in range(retries):
        try:
            session.commit()
            return
        except OperationalError:
            session.rollback()
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def build_explorer_url(chain: str, address: str) -> str:
    base = EXPLORER_BASES.get(chain.lower())
    return f"{base}{address}" if base else address


def _ensure_metrics_up_to_date(session, whale: Whale) -> CurrentWalletMetrics | None:
    """Recompute metrics if missing or stale compared to latest trades/holdings."""
    metrics = session.get(CurrentWalletMetrics, whale.id)
    last_trade = session.scalar(select(func.max(Trade.timestamp)).where(Trade.whale_id == whale.id))
    last_holding = session.scalar(
        select(func.max(Holding.updated_at)).where(Holding.whale_id == whale.id)
    )
    if (
        metrics is None
        or (last_trade and (metrics.updated_at is None or metrics.updated_at < last_trade))
        or (last_holding and (metrics.updated_at is None or metrics.updated_at < last_holding))
    ):
        recompute_wallet_metrics(session, whale)
        _commit_with_retry(session)
        metrics = session.get(CurrentWalletMetrics, whale.id)
    return metrics


def _resolve_whale(session, chain_slug: str, address: str) -> tuple[Whale, Chain]:
    chain_obj = session.scalar(select(Chain).where(Chain.slug == chain_slug.lower()))
    if not chain_obj:
        raise HTTPException(status_code=404, detail="Chain not found")
    whale = session.scalar(
        select(Whale).where(
            Whale.chain_id == chain_obj.id, func.lower(Whale.address) == address.lower()
        )
    )
    if not whale:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return whale, chain_obj


def _serialize_trades(trades: Iterable[Trade], chain_slug: str):
    items = []
    for t in trades:
        tx_hash = t.tx_hash.hex() if isinstance(t.tx_hash, (bytes, bytearray)) else t.tx_hash
        price = None
        try:
            if t.value_usd is not None and t.amount_base not in (None, 0):
                price = float(t.value_usd) / float(t.amount_base)
        except Exception:
            price = None
        direction = (
            t.direction.value if hasattr(t.direction, "value") else str(t.direction)
        ).lower()
        open_price = None
        close_price = None
        open_dirs = {
            TradeDirection.BUY.value,
            TradeDirection.LONG.value,
            TradeDirection.SHORT.value,
        }
        close_dirs = {
            TradeDirection.SELL.value,
            TradeDirection.WITHDRAW.value,
            TradeDirection.CLOSE_LONG.value,
            TradeDirection.CLOSE_SHORT.value,
        }
        if direction in open_dirs:
            open_price = price
        if direction in close_dirs:
            close_price = price
            # Back-solve entry price for closes when pnl and size are available
            if (
                open_price is None
                and price is not None
                and t.pnl_usd is not None
                and t.amount_base not in (None, 0)
            ):
                try:
                    size = abs(float(t.amount_base))
                    pnl = float(t.pnl_usd)
                    if size > 0:
                        if direction == TradeDirection.CLOSE_LONG.value:
                            open_price = price - (pnl / size)
                        elif direction == TradeDirection.CLOSE_SHORT.value:
                            open_price = price + (pnl / size)
                except Exception:
                    pass
        items.append(
            {
                "id": str(t.id),
                "timestamp": t.timestamp,
                "chain": chain_slug,
                "source": t.source.value if hasattr(t.source, "value") else t.source,
                "platform": t.platform or "",
                "direction": direction,
                "base_asset": t.base_asset,
                "quote_asset": t.quote_asset,
                "amount_base": str(t.amount_base) if t.amount_base is not None else None,
                "amount_quote": str(t.amount_quote) if t.amount_quote is not None else None,
                "value_usd": float(t.value_usd or 0),
                "pnl_usd": float(t.pnl_usd) if t.pnl_usd is not None else None,
                "pnl_percent": float(t.pnl_percent) if t.pnl_percent is not None else None,
                "tx_hash": tx_hash,
                "external_url": t.external_url,
                "price_usd": price,
                "open_price_usd": open_price,
                "close_price_usd": close_price,
            }
        )
    return items


@router.get(
    "/{chain}/{address}",
    response_model=WalletDetail,
)
async def get_wallet_detail(
    chain: str = Path(..., description="Chain identifier"),
    address: str = Path(..., description="Wallet address"),
) -> WalletDetail:
    with SessionLocal() as session:
        whale, chain_obj = _resolve_whale(session, chain, address)
        cm = _ensure_metrics_up_to_date(session, whale)
        holdings = session.query(Holding).filter(Holding.whale_id == whale.id).all()

        whale_type = whale.type.value if hasattr(whale.type, "value") else str(whale.type).lower()
        summary = WalletSummary(
            id=whale.id,
            address=whale.address,
            chain=chain_obj.slug,  # type: ignore[arg-type]
            type=whale_type,
            labels=whale.labels or [],
            external_explorer_url=build_explorer_url(chain_obj.slug, whale.address),
        )

        metrics = WalletMetrics(
            roi_percent=float(cm.roi_percent or 0) if cm else 0.0,
            realized_pnl_usd=float(cm.realized_pnl_usd or 0) if cm else 0.0,
            unrealized_pnl_usd=float(cm.unrealized_pnl_usd) if cm and cm.unrealized_pnl_usd is not None else None,
            portfolio_value_usd=float(cm.portfolio_value_usd or 0) if cm else 0.0,
            volume_30d_usd=float(cm.volume_30d_usd or 0) if cm else 0.0,
            trades_30d=int(cm.trades_30d or 0) if cm else 0,
            win_rate_percent=float(cm.win_rate_percent) if cm and cm.win_rate_percent is not None else None,
            first_seen_at=whale.first_seen_at or now(),
            last_active_at=whale.last_active_at or whale.first_seen_at or now(),
        )

        holdings_payload = [
            {
                "asset_symbol": h.asset_symbol,
                "asset_name": h.asset_name or h.asset_symbol,
                "chain": chain_obj.slug,  # type: ignore[arg-type]
                "amount": str(h.amount) if h.amount is not None else "0",
                "value_usd": float(h.value_usd or 0),
                "portfolio_percent": float(h.portfolio_percent) if h.portfolio_percent is not None else 0,
            }
            for h in holdings
        ]

        return WalletDetail(wallet=summary, metrics=metrics, holdings=holdings_payload, notes=None)


@router.get(
    "/{chain}/{address}/roi-history",
    response_model=RoiHistoryResponse,
)
async def get_roi_history(
    chain: str,
    address: str,
    days: int = Query(default=30),
) -> RoiHistoryResponse:
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, chain, address)
        from app.models import WalletMetricsDaily

        since = now().date() - timedelta(days=days)

        def _fetch():
            return (
                session.query(WalletMetricsDaily)
                .filter(WalletMetricsDaily.whale_id == whale.id, WalletMetricsDaily.date >= since)
                .order_by(WalletMetricsDaily.date.asc())
                .all()
            )

        rows = _fetch()
        if not rows:
            rebuild_portfolio_history_from_trades(session, whale)
            recompute_wallet_metrics(session, whale)
            _commit_with_retry(session)
            rows = _fetch()
        points = [
            {"timestamp": datetime.combine(r.date, datetime.min.time(), tzinfo=timezone.utc), "roi_percent": float(r.roi_percent or 0)}
            for r in rows
        ]
        return RoiHistoryResponse(points=points)


@router.get(
    "/{chain}/{address}/portfolio-history",
    response_model=PortfolioHistoryResponse,
)
async def get_portfolio_history(
    chain: str,
    address: str,
    days: int = Query(default=30),
) -> PortfolioHistoryResponse:
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, chain, address)
        from app.models import WalletMetricsDaily

        since = now().date() - timedelta(days=days)
        def _fetch():
            return (
                session.query(WalletMetricsDaily)
                .filter(WalletMetricsDaily.whale_id == whale.id, WalletMetricsDaily.date >= since)
                .order_by(WalletMetricsDaily.date.asc())
                .all()
            )

        rows = _fetch()
        if len(rows) < 2:
            rebuild_portfolio_history_from_trades(session, whale)
            recompute_wallet_metrics(session, whale)
            _commit_with_retry(session)
            rows = _fetch()
        points = [
            {
                "timestamp": datetime.combine(r.date, datetime.min.time(), tzinfo=timezone.utc),
                "value_usd": float(r.portfolio_value_usd or 0),
            }
            for r in rows
        ]
        return PortfolioHistoryResponse(points=points)


@router.get(
    "/{chain}/{address}/positions",
    response_model=PositionsResponse,
)
async def get_wallet_positions(
    chain: str,
    address: str,
) -> PositionsResponse:
    if chain.lower() != "hyperliquid":
        return PositionsResponse(items=[])

    try:
        state = hyperliquid_client.get_clearinghouse_state(address)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Failed to fetch positions") from exc

    positions_raw = state.get("assetPositions") if isinstance(state, dict) else []
    items: list[OpenPosition] = []
    if isinstance(positions_raw, list):
        for pos in positions_raw:
            position = pos.get("position") or {}
            coin = pos.get("coin") or position.get("coin")
            szi = position.get("szi")
            entry_px = position.get("entryPx")
            mark_px = position.get("markPx") or pos.get("markPx")
            position_value = position.get("positionValue")
            if coin is None or szi in (None, 0):
                continue
            try:
                size = float(szi)
            except Exception:
                continue
            direction = "long" if size >= 0 else "short"
            try:
                entry = float(entry_px) if entry_px is not None else None
            except Exception:
                entry = None
            try:
                mark = float(mark_px) if mark_px is not None else None
            except Exception:
                mark = None
            if mark is None and position_value is not None:
                try:
                    mark = float(position_value) / abs(size)
                except Exception:
                    mark = entry
            value_usd = None
            if position_value is not None:
                try:
                    value_usd = float(position_value)
                except Exception:
                    value_usd = None
            if value_usd is None and mark is not None:
                value_usd = abs(size * mark)
            pnl_usd = None
            if "unrealizedPnl" in position:
                try:
                    pnl_usd = float(position["unrealizedPnl"])
                except Exception:
                    pnl_usd = None
            if pnl_usd is None and entry is not None and mark is not None:
                if size >= 0:
                    pnl_usd = (mark - entry) * size
                else:
                    pnl_usd = (entry - mark) * abs(size)
            items.append(
                OpenPosition(
                    asset=coin,
                    direction=direction,  # type: ignore[arg-type]
                    size=abs(size),
                    entry_price_usd=entry,
                    mark_price_usd=mark,
                    value_usd=value_usd,
                    unrealized_pnl_usd=pnl_usd,
                )
            )

    return PositionsResponse(items=items)


@router.get(
    "/{chain}/{address}/trades",
    response_model=TradesResponse,
)
async def get_wallet_trades(
    chain: str,
    address: str,
    source: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    cursor: str | None = Query(default=None),
) -> TradesResponse:
    with SessionLocal() as session:
        whale, chain_obj = _resolve_whale(session, chain, address)
        query = session.query(Trade).filter(Trade.whale_id == whale.id)
        if source:
            query = query.filter(Trade.source == source)
        if direction:
            direction_value = direction.lower()
            try:
                direction_enum = TradeDirection(direction_value)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid direction")
            query = query.filter(Trade.direction == direction_enum)
        query = query.order_by(Trade.timestamp.desc(), Trade.id.desc())

        if cursor:
            try:
                cursor_ts = None
                cursor_id = None
                if "|" in cursor:
                    ts_part, id_part = cursor.split("|", 1)
                    cursor_ts = datetime.fromisoformat(ts_part)
                    cursor_id = int(id_part)
                else:
                    cursor_id = int(cursor)

                if cursor_ts:
                    query = query.filter(
                        or_(
                            Trade.timestamp < cursor_ts,
                            and_(Trade.timestamp == cursor_ts, Trade.id < cursor_id),
                        )
                    )
                elif cursor_id:
                    query = query.filter(Trade.id < cursor_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid cursor")

        rows = query.limit(limit + 1).all()
        has_more = len(rows) > limit
        trades = rows[:limit]
        items = _serialize_trades(trades, chain_obj.slug)
        next_cursor = (
            f"{trades[-1].timestamp.isoformat()}|{trades[-1].id}" if has_more and trades else None
        )
        return TradesResponse(items=items, next_cursor=next_cursor)
