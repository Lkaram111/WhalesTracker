from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import time
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import (
    Chain,
    CurrentWalletMetrics,
    Holding,
    Trade,
    TradeDirection,
    WalletMetricsDaily,
    Whale,
)
from app.services.hyperliquid_client import hyperliquid_client


def _safe_sum(values: Iterable[Decimal | None]) -> Decimal:
    total = Decimal(0)
    for v in values:
        if v is not None:
            total += Decimal(v)
    return total


def _volume_and_count_last_30d(session: Session, whale_id: str, days: int = 30) -> tuple[Decimal, int]:
    window_start = datetime.now(timezone.utc) - timedelta(days=days)
    trades = (
        session.query(Trade.value_usd)
        .filter(Trade.whale_id == whale_id, Trade.timestamp >= window_start)
        .all()
    )
    volume = _safe_sum((t.value_usd for t in trades))
    count = len(trades)
    return volume, count


def _cost_basis(session: Session, whale_id: str) -> tuple[Decimal, Decimal]:
    """Approximate cost basis and realized-out flows from trade values per asset."""
    trades = (
        session.query(Trade.base_asset, Trade.direction, Trade.value_usd)
        .filter(Trade.whale_id == whale_id)
        .all()
    )
    asset_costs: dict[str, Decimal] = {}
    realized_out: dict[str, Decimal] = {}

    for base_asset, direction, value_usd in trades:
        if value_usd is None or not base_asset:
            continue
        val = Decimal(value_usd)
        asset_costs.setdefault(base_asset, Decimal(0))
        realized_out.setdefault(base_asset, Decimal(0))
        if direction in {
            TradeDirection.DEPOSIT,
            TradeDirection.BUY,
            TradeDirection.LONG,
            TradeDirection.SHORT,
        }:
            asset_costs[base_asset] += abs(val)
        elif direction in {
            TradeDirection.WITHDRAW,
            TradeDirection.SELL,
            TradeDirection.CLOSE_LONG,
            TradeDirection.CLOSE_SHORT,
        }:
            realized_out[base_asset] += abs(val)

    total_cost = Decimal(0)
    for asset, cost in asset_costs.items():
        net = cost - realized_out.get(asset, Decimal(0))
        if net > 0:
            total_cost += net
    return total_cost, sum(realized_out.values(), Decimal(0))


def _positions_cost_basis(session: Session, whale_id: str) -> tuple[dict[str, dict[str, Decimal]], Decimal]:
    """Track per-asset qty and cost basis using average-cost outflows."""
    trades = (
        session.query(Trade)
        .filter(Trade.whale_id == whale_id)
        .order_by(Trade.timestamp.asc(), Trade.id.asc())
        .all()
    )
    positions: dict[str, dict[str, Decimal]] = {}
    realized = Decimal(0)

    for trade in trades:
        if not trade.base_asset or trade.amount_base is None:
            continue
        asset = trade.base_asset
        qty = abs(Decimal(trade.amount_base))
        value_usd = Decimal(trade.value_usd or 0)
        pos = positions.setdefault(asset, {"qty": Decimal(0), "cost": Decimal(0)})

        if trade.direction in {
            TradeDirection.DEPOSIT,
            TradeDirection.BUY,
            TradeDirection.LONG,
            TradeDirection.SHORT,
        }:
            pos["qty"] += qty
            pos["cost"] += abs(value_usd)
        elif trade.direction in {
            TradeDirection.WITHDRAW,
            TradeDirection.SELL,
            TradeDirection.CLOSE_LONG,
            TradeDirection.CLOSE_SHORT,
        }:
            if pos["qty"] <= 0:
                continue
            avg_cost = pos["cost"] / pos["qty"] if pos["qty"] != 0 else Decimal(0)
            qty_out = min(qty, pos["qty"])
            cost_out = avg_cost * qty_out
            pos["qty"] -= qty_out
            pos["cost"] -= cost_out
            realized += value_usd - cost_out
    return positions, realized


def _update_holdings_cost_basis(holdings: list[Holding], positions: dict[str, dict[str, Decimal]]) -> None:
    for h in holdings:
        pos = positions.get(h.asset_symbol)
        if not pos:
            h.cost_basis_usd = None
            h.avg_unit_cost_usd = None
            continue
        h.cost_basis_usd = pos["cost"]
        h.avg_unit_cost_usd = (
            pos["cost"] / pos["qty"] if pos["qty"] and pos["qty"] != 0 else None
        )


def recompute_wallet_metrics(session: Session, whale: Whale) -> None:
    chain = session.get(Chain, whale.chain_id)
    is_hyperliquid = chain is not None and chain.slug == "hyperliquid"

    holdings = session.query(Holding).filter(Holding.whale_id == whale.id).all()
    portfolio_value = _safe_sum(h.value_usd for h in holdings)

    volume_30d, trades_30d = _volume_and_count_last_30d(session, whale.id)
    volume_1d, trades_1d = _volume_and_count_last_30d(session, whale.id, days=1)

    positions: dict[str, dict[str, Decimal]] = {}
    realized_from_sales = Decimal(0)
    if not is_hyperliquid:
        positions, realized_from_sales = _positions_cost_basis(session, whale.id)
        _update_holdings_cost_basis(holdings, positions)

    realized_trades = session.query(Trade.pnl_usd).filter(
        Trade.whale_id == whale.id, Trade.pnl_usd.isnot(None)
    )
    realized_pnl = _safe_sum(t.pnl_usd for t in realized_trades) + realized_from_sales

    with_pnl = session.query(Trade.pnl_usd).filter(
        Trade.whale_id == whale.id, Trade.pnl_usd.isnot(None)
    )
    positive = [t.pnl_usd for t in with_pnl if t.pnl_usd and Decimal(t.pnl_usd) > 0]
    total_count = with_pnl.count()
    win_rate_percent = (
        float(len(positive)) / float(total_count) * 100 if total_count > 0 else None
    )

    cost_basis_total = _safe_sum(p["cost"] for p in positions.values())
    unrealized_pnl = Decimal(portfolio_value) - cost_basis_total
    roi_percent = (
        float(realized_pnl + unrealized_pnl) / float(cost_basis_total) * 100
        if cost_basis_total > 0
        else 0.0
    )

    # Hyperliquid: prefer clearinghouse state metrics to avoid inflating notional as portfolio value
    if is_hyperliquid:
        try:
            state = hyperliquid_client.get_clearinghouse_state(whale.address)
        except Exception:
            state = None
        if isinstance(state, dict):
            margin = state.get("marginSummary") or {}
            try:
                account_value = Decimal(margin.get("accountValue", "0"))
            except Exception:
                account_value = Decimal(portfolio_value)
            try:
                withdrawable = Decimal(state.get("withdrawable") or 0)
            except Exception:
                withdrawable = Decimal(0)
            positions_raw = state.get("assetPositions") if isinstance(state.get("assetPositions"), list) else []
            unrealized_positions = []
            for pos in positions_raw:
                position = pos.get("position") or {}
                try:
                    unrealized_positions.append(Decimal(position.get("unrealizedPnl", "0")))
                except Exception:
                    pass
            unrealized_pnl = sum(unrealized_positions, Decimal(0))
            portfolio_value = float(account_value)
            total_pnl = realized_pnl + unrealized_pnl
            cost_basis_total = account_value - total_pnl
            if withdrawable > 0:
                cost_basis_total = max(cost_basis_total, withdrawable)
            if cost_basis_total > 0:
                roi_percent = float(total_pnl / cost_basis_total) * 100
            else:
                cost_basis_total = Decimal(0)
                roi_percent = 0.0

    _upsert_current_metrics(
        session,
        {
            "whale_id": whale.id,
            "portfolio_value_usd": portfolio_value,
            "roi_percent": roi_percent,
            "realized_pnl_usd": realized_pnl,
            "unrealized_pnl_usd": unrealized_pnl,
            "volume_30d_usd": volume_30d,
            "trades_30d": trades_30d,
            "win_rate_percent": win_rate_percent,
        },
    )

    today = date.today()
    pending_daily = next(
        (
            d
            for d in session.new
            if isinstance(d, WalletMetricsDaily) and d.whale_id == whale.id and d.date == today
        ),
        None,
    )
    existing_daily = (
        pending_daily
        or session.query(WalletMetricsDaily)
        .filter(WalletMetricsDaily.whale_id == whale.id, WalletMetricsDaily.date == today)
        .one_or_none()
    )
    if existing_daily:
        existing_daily.portfolio_value_usd = portfolio_value
        existing_daily.roi_percent = roi_percent
        existing_daily.realized_pnl_usd = realized_pnl
        existing_daily.unrealized_pnl_usd = unrealized_pnl
        existing_daily.volume_1d_usd = volume_1d
        existing_daily.trades_1d = trades_1d
        existing_daily.win_rate_percent = win_rate_percent
    else:
        session.add(
            WalletMetricsDaily(
                whale_id=whale.id,
                date=today,
                portfolio_value_usd=portfolio_value,
                roi_percent=roi_percent,
                realized_pnl_usd=realized_pnl,
                unrealized_pnl_usd=unrealized_pnl,
                volume_1d_usd=volume_1d,
                trades_1d=trades_1d,
                win_rate_percent=win_rate_percent,
            )
        )


def _upsert_current_metrics(session: Session, payload: dict[str, Any]) -> None:
    """DB-atomic upsert to avoid duplicate current_wallet_metrics rows."""
    update_values = {k: v for k, v in payload.items() if k != "whale_id"}
    dialect = session.bind.dialect.name if session.bind else ""  # type: ignore[attr-defined]
    if dialect in {"sqlite", "postgresql", "postgres"}:
        stmt = (
            sqlite_insert(CurrentWalletMetrics)
            if dialect == "sqlite"
            else pg_insert(CurrentWalletMetrics)
        ).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[CurrentWalletMetrics.whale_id],
            set_={**update_values, "updated_at": func.now()},
        )
        session.execute(stmt)
    else:
        metrics = session.get(CurrentWalletMetrics, payload["whale_id"])
        if metrics:
            for key, value in update_values.items():
                setattr(metrics, key, value)
            metrics.updated_at = datetime.now(timezone.utc)
        else:
            session.add(CurrentWalletMetrics(**payload))


def recompute_all_wallet_metrics(session: Session) -> None:
    whales = session.query(Whale).all()
    for whale in whales:
        recompute_wallet_metrics(session, whale)
    _commit_with_retry(session)


def rebuild_all_portfolio_histories(session: Session) -> None:
    """Rebuild portfolio history for all whales from trades to restore charts."""
    whales = session.query(Whale).all()
    for whale in whales:
        rebuild_portfolio_history_from_trades(session, whale)
    _commit_with_retry(session)


def touch_last_active(session: Session, whale: Whale, ts: datetime | None = None) -> None:
    whale.last_active_at = ts or datetime.now(timezone.utc)
    session.add(whale)


def _commit_with_retry(session: Session, retries: int = 3, delay: float = 0.5) -> None:
    for attempt in range(retries):
        try:
            session.commit()
            return
        except OperationalError:
            session.rollback()
            if attempt == retries - 1:
                raise
            time.sleep(delay)


def rebuild_portfolio_history_from_trades(session: Session, whale: Whale) -> None:
    """Populate WalletMetricsDaily rows from historical trades for charting."""
    chain = session.get(Chain, whale.chain_id)
    is_hyperliquid = chain is not None and chain.slug == "hyperliquid"
    trades = (
        session.query(Trade)
        .filter(Trade.whale_id == whale.id, Trade.timestamp.isnot(None))
        .order_by(Trade.timestamp.asc(), Trade.id.asc())
        .all()
    )
    if not trades:
        return
    if is_hyperliquid:
        _rebuild_hyperliquid_history(session, whale, trades)
        return
    daily: dict[date, dict[str, Decimal | int]] = {}
    cumulative = Decimal(0)
    for t in trades:
        if t.value_usd is None:
            continue
        trade_date = t.timestamp.date()
        stats = daily.setdefault(
            trade_date, {"volume": Decimal(0), "trades": 0, "portfolio": None}
        )
        stats["volume"] += Decimal(t.value_usd)
        stats["trades"] += 1
        cumulative += Decimal(t.value_usd)
        stats["portfolio"] = cumulative

    for d, stats in daily.items():
        existing = (
            session.query(WalletMetricsDaily)
            .filter(WalletMetricsDaily.whale_id == whale.id, WalletMetricsDaily.date == d)
            .one_or_none()
        )
        portfolio_val = float(stats.get("portfolio") or 0)
        if existing:
            existing.portfolio_value_usd = portfolio_val
            existing.volume_1d_usd = float(stats.get("volume") or 0)
            existing.trades_1d = int(stats.get("trades") or 0)
            existing.roi_percent = existing.roi_percent or 0.0
            existing.realized_pnl_usd = existing.realized_pnl_usd or 0.0
            existing.unrealized_pnl_usd = existing.unrealized_pnl_usd or 0.0
        else:
            session.add(
                WalletMetricsDaily(
                    whale_id=whale.id,
                    date=d,
                    portfolio_value_usd=portfolio_val,
                    roi_percent=0.0,
                    realized_pnl_usd=0.0,
                    unrealized_pnl_usd=0.0,
                    volume_1d_usd=float(stats.get("volume") or 0),
                    trades_1d=int(stats.get("trades") or 0),
                    win_rate_percent=None,
                )
            )
    session.flush()


def _rebuild_hyperliquid_history(session: Session, whale: Whale, trades: list[Trade]) -> None:
    """Approximate daily equity for Hyperliquid accounts from fills and live state."""
    total_realized = _safe_sum(t.pnl_usd for t in trades if t.pnl_usd is not None)
    latest_unrealized = Decimal(0)
    withdrawable = Decimal(0)
    account_value: Decimal | None = None

    try:
        state = hyperliquid_client.get_clearinghouse_state(whale.address)
    except Exception:
        state = None
    if isinstance(state, dict):
        margin = state.get("marginSummary") or {}
        try:
            account_value = Decimal(margin.get("accountValue", "0"))
        except Exception:
            account_value = None
        positions_raw = state.get("assetPositions") if isinstance(state.get("assetPositions"), list) else []
        unrealized_positions: list[Decimal] = []
        for pos in positions_raw:
            position = pos.get("position") or {}
            try:
                unrealized_positions.append(Decimal(position.get("unrealizedPnl", "0")))
            except Exception:
                pass
        latest_unrealized = sum(unrealized_positions, Decimal(0))
        try:
            withdrawable = Decimal(state.get("withdrawable") or 0)
        except Exception:
            withdrawable = Decimal(0)

    if account_value is None:
        holdings = session.query(Holding).filter(Holding.whale_id == whale.id).all()
        account_value = _safe_sum(h.value_usd for h in holdings)

    cost_basis = account_value - total_realized - latest_unrealized
    if withdrawable > 0:
        cost_basis = max(cost_basis, withdrawable)
    if cost_basis <= 0:
        cost_basis = account_value if account_value and account_value > 0 else Decimal(0)
    starting_equity = cost_basis if cost_basis > 0 else account_value or Decimal(0)

    daily: dict[date, dict[str, Decimal | int]] = {}
    cumulative_realized = Decimal(0)
    for t in trades:
        trade_date = t.timestamp.date()
        stats = daily.setdefault(
            trade_date, {"volume": Decimal(0), "trades": 0, "realized": Decimal(0)}
        )
        if t.value_usd is not None:
            stats["volume"] += abs(Decimal(t.value_usd))
        stats["trades"] += 1
        if t.pnl_usd is not None:
            cumulative_realized += Decimal(t.pnl_usd)
        stats["realized"] = cumulative_realized

    last_day = max(daily.keys()) if daily else None
    for d in sorted(daily.keys()):
        stats = daily[d]
        realized_to_date = Decimal(stats.get("realized") or 0)
        equity = starting_equity + realized_to_date if starting_equity is not None else realized_to_date
        unrealized = latest_unrealized if last_day and d == last_day else Decimal(0)
        equity_with_unrealized = equity + unrealized
        roi_percent = (
            float((equity_with_unrealized - cost_basis) / cost_basis * 100)
            if cost_basis > 0
            else 0.0
        )
        existing = (
            session.query(WalletMetricsDaily)
            .filter(WalletMetricsDaily.whale_id == whale.id, WalletMetricsDaily.date == d)
            .one_or_none()
        )
        if existing:
            existing.portfolio_value_usd = float(equity_with_unrealized)
            existing.volume_1d_usd = float(stats.get("volume") or 0)
            existing.trades_1d = int(stats.get("trades") or 0)
            existing.roi_percent = roi_percent
            existing.realized_pnl_usd = float(realized_to_date)
            existing.unrealized_pnl_usd = float(unrealized)
        else:
            session.add(
                WalletMetricsDaily(
                    whale_id=whale.id,
                    date=d,
                    portfolio_value_usd=float(equity_with_unrealized),
                    roi_percent=roi_percent,
                    realized_pnl_usd=float(realized_to_date),
                    unrealized_pnl_usd=float(unrealized),
                    volume_1d_usd=float(stats.get("volume") or 0),
                    trades_1d=int(stats.get("trades") or 0),
                    win_rate_percent=None,
                )
            )
    session.flush()
