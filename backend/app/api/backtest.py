from datetime import datetime, timedelta
from types import SimpleNamespace
from bisect import bisect_right
from decimal import Decimal
from typing import Iterable, Sequence, Any

import logging
import time
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select, inspect
from sqlalchemy.exc import OperationalError

from app.db.session import SessionLocal
from app.models import BacktestRun, Chain, PriceHistory, Trade, TradeDirection, Whale
from app.core.config import settings
from app.schemas.api import (
    BacktestSummary,
    BacktestTradeResult,
    CopierSessionStatus,
    ChainId,
    CopierBacktestRequest,
    CopierBacktestResponse,
    BacktestRunSummary,
    LiveTradesResponse,
    StartCopierRequest,
    WhaleAssetsResponse,
    MultiWhaleBacktestRequest,
    MultiWhaleBacktestResponse,
)
from app.services.price_service import fetch_and_store_binance_prices
from app.services.copier_manager import copier_manager
from app.services.metrics_service import _commit_with_retry

router = APIRouter()
logger = logging.getLogger(__name__)


def _simulate_copy_trades(
    session,
    trades: Sequence,
    *,
    initial_deposit: Decimal,
    recommended_pct: float,
    used_pct: float,
    fee_rate: Decimal,
    slippage_rate: Decimal,
    leverage: Decimal,
    include_price_points: bool,
    preload_prices: bool,
    asset_filter: set[str] | None,
    trades_limit: int,
    trades_offset: int,
) -> tuple[BacktestSummary, list[BacktestTradeResult], list[dict], dict[str, list[dict]] | None, int]:
    closing_dirs = {
        TradeDirection.CLOSE_LONG,
        TradeDirection.CLOSE_SHORT,
        TradeDirection.SELL,
        TradeDirection.WITHDRAW,
    }
    entry_dirs = {TradeDirection.LONG, TradeDirection.SHORT, TradeDirection.BUY}

    # preload price history for marking open positions (best-effort)
    assets = {(getattr(t, "base_asset", None) or "").upper() for t in trades if getattr(t, "base_asset", None)}
    assets.discard("")
    assets_used = sorted(asset_filter) if asset_filter else sorted(assets)
    price_cache: dict[str, tuple[list[datetime], list[Decimal]]] = {}

    # determine backtest window for price fetch
    start_ts = trades[0].timestamp.replace(second=0, microsecond=0) if trades else None
    end_ts = trades[-1].timestamp.replace(second=0, microsecond=0) if trades else None

    if assets and start_ts and end_ts:
        if preload_prices:
            try:
                rows = (
                    session.query(
                        PriceHistory.asset_symbol, func.min(PriceHistory.timestamp), func.max(PriceHistory.timestamp)
                    )
                    .filter(PriceHistory.asset_symbol.in_(list(assets)))
                    .group_by(PriceHistory.asset_symbol)
                    .all()
                )
                covered: set[str] = set()
                for sym, min_ts, max_ts in rows:
                    if min_ts <= start_ts and max_ts >= end_ts:
                        covered.add(sym)
                missing_assets = assets - covered
                if missing_assets:
                    fetch_and_store_binance_prices(
                        session,
                        assets=list(missing_assets),
                        timeframe="1m",
                        since=start_ts - timedelta(minutes=1),
                        until=end_ts + timedelta(minutes=1),
                        limit=1500,
                    )
                    session.flush()
                    _commit_with_retry(session)
            except OperationalError as exc:
                session.rollback()
                logger.warning(
                    "price preload commit failed; continuing without new prices: %s", exc
                )
            except Exception as exc:
                session.rollback()
                logger.warning(
                    "price preload failed; continuing without new prices: %s", exc
                )

        rows = (
            session.query(PriceHistory.asset_symbol, PriceHistory.timestamp, PriceHistory.price_usd)
            .filter(
                PriceHistory.asset_symbol.in_(list(assets)),
                PriceHistory.timestamp >= start_ts - timedelta(minutes=5),
                PriceHistory.timestamp <= end_ts + timedelta(minutes=5),
            )
            .order_by(PriceHistory.asset_symbol, PriceHistory.timestamp)
            .all()
        )
        for sym, ts, price in rows:
            if price is None:
                continue
            ts_list, px_list = price_cache.setdefault(sym, ([], []))
            ts_list.append(ts)
            px_list.append(Decimal(price))

    def _mark_price(sym: str | None, ts: datetime, fallback: Decimal | None) -> Decimal | None:
        if sym is None:
            return fallback
        series = price_cache.get(sym)
        if not series:
            return fallback
        ts_list, px_list = series
        idx = bisect_right(ts_list, ts) - 1
        if idx < 0:
            return fallback
        return px_list[idx]

    positions: dict[str, dict[str, Decimal]] = {}
    cash = initial_deposit
    cumulative_net = Decimal(0)
    total_fees = Decimal(0)
    total_slippage = Decimal(0)
    gross_pnl = Decimal(0)
    wins = 0
    closing_count = 0
    results: list[BacktestTradeResult] = []
    equity_curve: list[dict] = []

    def _compute_drawdown(curve: list[dict]) -> tuple[Decimal, Decimal]:
        if not curve:
            return Decimal(0), Decimal(0)
        peak = Decimal(curve[0]["equity_usd"])
        max_dd = Decimal(0)
        max_dd_usd = Decimal(0)
        for point in curve:
            eq = Decimal(point["equity_usd"])
            if eq > peak:
                peak = eq
            drawdown_abs = peak - eq
            dd_ratio = drawdown_abs / peak if peak > 0 else Decimal(0)
            if dd_ratio > max_dd:
                max_dd = dd_ratio
                max_dd_usd = drawdown_abs
        return max_dd, max_dd_usd

    def _unrealized_and_margin(ts: datetime) -> tuple[Decimal, Decimal]:
        unreal = Decimal(0)
        margin_total = Decimal(0)
        for sym, pos in positions.items():
            qty = pos.get("qty", Decimal(0))
            margin_total += pos.get("margin", Decimal(0))
            if qty == 0:
                continue
            avg = pos.get("avg_price", Decimal(0))
            mark = _mark_price(sym, ts, avg)
            if mark is None:
                continue
            if qty > 0:
                unreal += (mark - avg) * qty
            else:
                unreal += (avg - mark) * abs(qty)
        return unreal, margin_total

    current_idx = 0
    trade_count = len(trades)
    trade_items = list(trades)

    def _record_equity(ts: datetime) -> None:
        unreal, margin_total = _unrealized_and_margin(ts)
        equity = cash + margin_total + unreal
        cumulative_net_local = equity - initial_deposit
        equity_curve.append(
            {"timestamp": ts, "equity_usd": float(equity), "unrealized_pnl_usd": float(unreal)}
        )
        return cumulative_net_local

    # iterate minute by minute and process trades that occur within or before that minute
    if start_ts and end_ts:
        delta_minutes = int((end_ts - start_ts).total_seconds() // 60)
        step_minutes = 1
        if delta_minutes > 60 * 24 * 60:
            step_minutes = 5
        if delta_minutes > 60 * 24 * 180:
            step_minutes = 15
        ts = start_ts
        while ts <= end_ts:
            # process trades with timestamp <= end of this minute
            minute_end = ts.replace(second=59, microsecond=999999)
            while current_idx < trade_count and trade_items[current_idx].timestamp <= minute_end:
                t = trade_items[current_idx]
                current_idx += 1
                direction_raw = getattr(t, "direction", None)
                direction = direction_raw if hasattr(direction_raw, "value") else TradeDirection(str(direction_raw))
                notional = Decimal(abs(getattr(t, "value_usd", 0) or 0))
                scale = Decimal(used_pct)
                current_unreal, current_margin = _unrealized_and_margin(t.timestamp)
                equity_now = cash + current_margin + current_unreal
                desired_notional = notional * scale
                per_trade_cap_ratio = Decimal("0.05")  # at most 5% of levered equity per trade
                if direction in closing_dirs:
                    user_notional = desired_notional
                else:
                    max_notional_overall = equity_now * leverage
                    max_notional_per_trade = max_notional_overall * per_trade_cap_ratio
                    user_notional = min(desired_notional, max_notional_per_trade) if max_notional_overall > 0 else Decimal(0)
                if user_notional <= 0:
                    continue
                price = None
                try:
                    amount_base = getattr(t, "amount_base", None)
                    if getattr(t, "value_usd", None) is not None and amount_base not in (None, 0):
                        price = Decimal(abs(t.value_usd)) / Decimal(abs(amount_base))
                except Exception:
                    price = None
                sym_key = (getattr(t, "base_asset", None) or "").upper() or None
                price = _mark_price(sym_key, t.timestamp, price)
                if price is None or price <= 0:
                    continue
                base_label = getattr(t, "base_asset", None) or "UNKNOWN"
                pos_key = sym_key or base_label
                pos = positions.setdefault(
                    pos_key, {"qty": Decimal(0), "avg_price": Decimal(0), "margin": Decimal(0)}
                )

                net_change = Decimal(0)
                pnl = Decimal(0)
                executed_notional = user_notional
                fee = Decimal(0)
                slip = Decimal(0)

                if direction in entry_dirs:
                    fee = user_notional * fee_rate
                    slip = user_notional * slippage_rate
                    margin_required = user_notional / leverage
                    total_cost = margin_required + fee + slip
                    if total_cost > cash:
                        afford_scale = cash / total_cost if total_cost > 0 else Decimal(0)
                        user_notional *= afford_scale
                        fee = user_notional * fee_rate
                        slip = user_notional * slippage_rate
                        margin_required = user_notional / leverage
                        total_cost = margin_required + fee + slip
                        if user_notional <= 0 or total_cost > cash:
                            continue
                    executed_notional = user_notional
                    total_fees += fee
                    total_slippage += slip

                    qty = user_notional / price
                    signed_qty = qty if direction in {TradeDirection.LONG, TradeDirection.BUY} else -qty
                    if signed_qty != 0:
                        new_qty = pos["qty"] + signed_qty
                        if new_qty == 0:
                            pos["qty"] = Decimal(0)
                            pos["avg_price"] = Decimal(0)
                            pos["margin"] = Decimal(0)
                        else:
                            existing_cost = pos["avg_price"] * pos["qty"]
                            added_cost = price * signed_qty
                            pos["qty"] = new_qty
                            pos["avg_price"] = (existing_cost + added_cost) / new_qty if new_qty != 0 else Decimal(0)
                            pos["margin"] += margin_required
                    cash -= (margin_required + fee + slip)
                    net_change -= (fee + slip)
                elif direction in closing_dirs:
                    pos_qty = pos["qty"]
                    if pos_qty == 0:
                        continue
                    qty = user_notional / price
                    close_qty = min(abs(qty), abs(pos_qty))
                    if close_qty <= 0:
                        continue
                    executed_notional = close_qty * price
                    fee = executed_notional * fee_rate
                    slip = executed_notional * slippage_rate
                    total_fees += fee
                    total_slippage += slip
                    signed_close = close_qty if pos_qty > 0 else -close_qty
                    avg = pos["avg_price"]
                    pnl = (price - avg) * signed_close if pos_qty > 0 else (avg - price) * abs(signed_close)
                    margin_release = pos["margin"] * (close_qty / abs(pos_qty)) if pos["margin"] else Decimal(0)
                    pos["qty"] = pos_qty - signed_close
                    if pos["qty"] == 0:
                        pos["avg_price"] = Decimal(0)
                        pos["margin"] = Decimal(0)
                    else:
                        pos["margin"] -= margin_release
                    net = pnl - fee - slip
                    gross_pnl += pnl
                    net_change += net
                    cash += margin_release + net
                    closing_count += 1
                    if net > 0:
                        wins += 1
                else:
                    continue

                unreal, margin_total = _unrealized_and_margin(t.timestamp)
                equity = cash + margin_total + unreal
                cumulative_net = equity - initial_deposit
                results.append(
                    BacktestTradeResult(
                        id=getattr(t, "id", None) or current_idx,
                        timestamp=t.timestamp,
                        direction=str(direction.value if hasattr(direction, "value") else direction),
                        base_asset=getattr(t, "base_asset", None),
                        notional_usd=float(executed_notional),
                        pnl_usd=float(pnl),
                        fee_usd=float(fee),
                        slippage_usd=float(slip),
                        net_pnl_usd=float(net_change if net_change != 0 else (pnl - fee - slip)),
                        cumulative_pnl_usd=float(cumulative_net),
                        equity_usd=float(equity),
                        unrealized_pnl_usd=float(unreal),
                        position_size_base=float(pos["qty"]) if pos["qty"] is not None else None,
                    )
                )

            _record_equity(ts.replace(second=0, microsecond=0))
            ts = ts + timedelta(minutes=step_minutes)

    if not equity_curve and trades:
        _record_equity(trades[-1].timestamp)

    max_dd_ratio, max_dd_usd = _compute_drawdown(equity_curve)
    roi = float(cumulative_net / initial_deposit * Decimal(100)) if initial_deposit > 0 else 0.0
    win_rate = float(wins) / float(closing_count) * 100 if closing_count > 0 else None
    max_drawdown_percent = float(max_dd_ratio * Decimal(100)) if max_dd_ratio is not None else None
    max_drawdown_usd = float(max_dd_usd) if max_dd_usd is not None else None

    summary = BacktestSummary(
        initial_deposit_usd=float(initial_deposit),
        recommended_position_pct=recommended_pct * 100.0,
        used_position_pct=used_pct * 100.0,
        leverage_used=float(leverage),
        asset_symbols=assets_used,
        total_fees_usd=float(total_fees),
        total_slippage_usd=float(total_slippage),
        gross_pnl_usd=float(gross_pnl),
        net_pnl_usd=float(cumulative_net),
        roi_percent=roi,
        trades_copied=len(results),
        win_rate_percent=win_rate,
        max_drawdown_percent=max_drawdown_percent,
        max_drawdown_usd=max_drawdown_usd,
        start=trades[0].timestamp if trades else None,
        end=trades[-1].timestamp if trades else None,
    )

    total_trades = len(results)
    start_idx = min(trades_offset, total_trades)
    end_idx = min(start_idx + trades_limit, total_trades)
    trade_slice = results[start_idx:end_idx]

    price_points = None
    if include_price_points:
        price_points = {
            sym: [{"timestamp": ts, "price": float(p)} for ts, p in zip(series[0], series[1])]
            for sym, series in price_cache.items()
        }

    return summary, trade_slice, equity_curve, price_points, total_trades


def _ensure_backtest_runs_table(session, retries: int = 3, delay: float = 1.0) -> bool:
    """Create backtest_runs table on the fly if migrations haven't been applied."""
    try:
        bind = session.get_bind()
        if bind is None:
            return False
        inspector = inspect(bind)
        if inspector.has_table(BacktestRun.__tablename__):
            return False
        for attempt in range(retries):
            try:
                BacktestRun.__table__.create(bind, checkfirst=True)
                return True
            except OperationalError as exc:
                # Handle transient SQLite locks with a short backoff
                if "database is locked" in str(exc).lower() and attempt < retries - 1:
                    time.sleep(delay)
                    continue
                raise
        return False
    except Exception as exc:  # best-effort guardrail; don't block backtests on failure
        logger.warning("ensure backtest_runs table failed: %s", exc)
        return False


def _percentile(values: Sequence[Decimal], pct: float) -> Decimal:
    if not values:
        return Decimal(0)
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    sorted_vals = sorted(values)
    k = Decimal(len(sorted_vals) - 1) * Decimal(pct) / Decimal(100)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    # linear interpolation using Decimal weights
    weight_c = k - Decimal(f)
    weight_f = Decimal(1) - weight_c
    return (sorted_vals[f] * weight_f) + (sorted_vals[c] * weight_c)


def _resolve_whale(session, chain: ChainId, address: str) -> tuple[Whale, Chain]:
    chain_obj = session.scalar(select(Chain).where(Chain.slug == chain.lower()))
    if not chain_obj:
        raise HTTPException(status_code=404, detail="Chain not found")
    whale = session.scalar(
        select(Whale).where(
            Whale.chain_id == chain_obj.id,
            func.lower(Whale.address) == address.lower(),
        )
    )
    if not whale:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return whale, chain_obj


def _recommended_position_pct(initial_deposit: Decimal, entry_sizes: Iterable[Decimal]) -> float:
    """Suggest copy size as ratio of user capital to whale's typical trade size."""
    vals = [v for v in entry_sizes if v > 0]
    if not vals:
        return 1.0
    anchor = _percentile(vals, 75)
    if anchor <= 0:
        return 1.0
    pct = float(initial_deposit / anchor)
    return max(0.0, min(pct, 1.0))


@router.post("/copier", response_model=CopierBacktestResponse)
def run_copier_backtest(payload: CopierBacktestRequest) -> CopierBacktestResponse:
    """Simulate copying a trader's opens/closes with scaling, fees, slippage, and unrealized PnL."""
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, payload.chain, payload.address)

        trades_limit = min(max(payload.trades_limit or 50, 1), 500)
        trades_offset = max(payload.trades_offset or 0, 0)

        closing_dirs = {
            TradeDirection.CLOSE_LONG,
            TradeDirection.CLOSE_SHORT,
            TradeDirection.SELL,
            TradeDirection.WITHDRAW,
        }
        entry_dirs = {TradeDirection.LONG, TradeDirection.SHORT, TradeDirection.BUY}
        ignore_dirs = {TradeDirection.DEPOSIT}
        asset_filter = {sym.upper() for sym in payload.asset_symbols} if payload.asset_symbols else None

        trade_query = (
            session.query(Trade)
            .filter(Trade.whale_id == whale.id, Trade.direction.notin_(ignore_dirs))
            .order_by(Trade.timestamp.asc(), Trade.id.asc())
        )
        if payload.start:
            trade_query = trade_query.filter(Trade.timestamp >= payload.start)
        if payload.end:
            trade_query = trade_query.filter(Trade.timestamp <= payload.end)
        if asset_filter:
            trade_query = trade_query.filter(Trade.base_asset.in_(list(asset_filter)))
        if payload.max_trades is not None:
            trade_query = trade_query.limit(payload.max_trades)
        trades = trade_query.all()

        entry_query = session.query(Trade.value_usd).filter(
            Trade.whale_id == whale.id,
            Trade.direction.in_(entry_dirs),
            Trade.value_usd.isnot(None),
        )
        if payload.start:
            entry_query = entry_query.filter(Trade.timestamp >= payload.start)
        if payload.end:
            entry_query = entry_query.filter(Trade.timestamp <= payload.end)
        if asset_filter:
            entry_query = entry_query.filter(Trade.base_asset.in_(list(asset_filter)))

        entry_query = entry_query.order_by(Trade.timestamp.asc())
        entry_sizes = [Decimal(abs(v[0])) for v in entry_query.all() if v[0] is not None]
        initial_deposit = Decimal(payload.initial_deposit_usd)
        recommended_pct = _recommended_position_pct(initial_deposit, entry_sizes)
        used_pct = (
            float(payload.position_size_pct) / 100.0
            if payload.position_size_pct is not None
            else recommended_pct
        )
        used_pct = max(0.0, min(used_pct, 2.0))  # hard cap to 200% notional copy

        fee_rate = Decimal(payload.fee_bps) / Decimal(10_000)
        slippage_rate = Decimal(payload.slippage_bps) / Decimal(10_000)
        leverage = Decimal(payload.leverage or 1.0)
        leverage = max(Decimal("0.1"), min(leverage, Decimal("100")))

        # preload price history for marking open positions (best-effort)
        assets = {(t.base_asset or "").upper() for t in trades if t.base_asset}
        assets.discard("")
        assets_used = sorted(asset_filter) if asset_filter else sorted(assets)
        price_cache: dict[str, tuple[list[datetime], list[Decimal]]] = {}

        # Gracefully return an empty backtest instead of 404 when no trades match filters.
        if not trades:
            empty_summary = BacktestSummary(
                initial_deposit_usd=float(initial_deposit),
                recommended_position_pct=recommended_pct * 100.0,
                used_position_pct=used_pct * 100.0,
                leverage_used=float(leverage),
                asset_symbols=assets_used,
                total_fees_usd=0.0,
                total_slippage_usd=0.0,
                gross_pnl_usd=0.0,
                net_pnl_usd=0.0,
                roi_percent=0.0,
                trades_copied=0,
                win_rate_percent=None,
            max_drawdown_percent=0.0,
            max_drawdown_usd=0.0,
            start=None,
            end=None,
        )
            return CopierBacktestResponse(
                summary=empty_summary,
                trades=[],
                equity_curve=[],
                price_points=None,
                trades_total=0,
                trades_limit=trades_limit,
                trades_offset=trades_offset,
            )

        # determine backtest window for price fetch
        start_ts = trades[0].timestamp.replace(second=0, microsecond=0) if trades else None
        end_ts = trades[-1].timestamp.replace(second=0, microsecond=0) if trades else None

        def _has_price_coverage(session, assets: set[str], start_ts: datetime, end_ts: datetime) -> set[str]:
            if not assets or not start_ts or not end_ts:
                return set()
            rows = (
                session.query(
                    PriceHistory.asset_symbol,
                    func.min(PriceHistory.timestamp),
                    func.max(PriceHistory.timestamp),
                )
                .filter(PriceHistory.asset_symbol.in_(list(assets)))
                .group_by(PriceHistory.asset_symbol)
                .all()
            )
            covered: set[str] = set()
            for sym, min_ts, max_ts in rows:
                if min_ts <= start_ts and max_ts >= end_ts:
                    covered.add(sym)
            return covered

        if assets and start_ts and end_ts:
            if payload.preload_prices:
                try:
                    covered = _has_price_coverage(session, assets, start_ts, end_ts)
                    missing_assets = assets - covered
                    if missing_assets:
                        fetch_and_store_binance_prices(
                            session,
                            assets=list(missing_assets),
                            timeframe="1m",
                            since=start_ts - timedelta(minutes=1),
                            until=end_ts + timedelta(minutes=1),
                            limit=1500,
                        )
                        session.flush()
                        _commit_with_retry(session)
                except OperationalError as exc:
                    session.rollback()
                    logger.warning(
                        "price preload commit failed; continuing without new prices: %s", exc
                    )
                except Exception as exc:
                    session.rollback()
                    logger.warning(
                        "price preload failed; continuing without new prices: %s", exc
                    )

            rows = (
                session.query(PriceHistory.asset_symbol, PriceHistory.timestamp, PriceHistory.price_usd)
                .filter(
                    PriceHistory.asset_symbol.in_(list(assets)),
                    PriceHistory.timestamp >= start_ts - timedelta(minutes=5),
                    PriceHistory.timestamp <= end_ts + timedelta(minutes=5),
                )
                .order_by(PriceHistory.asset_symbol, PriceHistory.timestamp)
                .all()
            )
            for sym, ts, price in rows:
                if price is None:
                    continue
                ts_list, px_list = price_cache.setdefault(sym, ([], []))
                ts_list.append(ts)
                px_list.append(Decimal(price))

        def _mark_price(sym: str | None, ts: datetime, fallback: Decimal | None) -> Decimal | None:
            if sym is None:
                return fallback
            series = price_cache.get(sym)
            if not series:
                return fallback
            ts_list, px_list = series
            idx = bisect_right(ts_list, ts) - 1
            if idx < 0:
                return fallback
            return px_list[idx]

        positions: dict[str, dict[str, Decimal]] = {}
        cash = initial_deposit
        cumulative_net = Decimal(0)
        total_fees = Decimal(0)
        total_slippage = Decimal(0)
        gross_pnl = Decimal(0)
        wins = 0
        closing_count = 0
        results: list[BacktestTradeResult] = []
        equity_curve: list[dict] = []

        def _compute_drawdown(curve: list[dict]) -> tuple[Decimal, Decimal]:
            if not curve:
                return Decimal(0), Decimal(0)
            peak = Decimal(curve[0]["equity_usd"])
            max_dd = Decimal(0)
            max_dd_usd = Decimal(0)
            for point in curve:
                eq = Decimal(point["equity_usd"])
                if eq > peak:
                    peak = eq
                drawdown_abs = peak - eq
                dd_ratio = drawdown_abs / peak if peak > 0 else Decimal(0)
                if dd_ratio > max_dd:
                    max_dd = dd_ratio
                    max_dd_usd = drawdown_abs
            return max_dd, max_dd_usd

        def _unrealized_and_margin(ts: datetime) -> tuple[Decimal, Decimal]:
            unreal = Decimal(0)
            margin_total = Decimal(0)
            for sym, pos in positions.items():
                qty = pos.get("qty", Decimal(0))
                margin_total += pos.get("margin", Decimal(0))
                if qty == 0:
                    continue
                avg = pos.get("avg_price", Decimal(0))
                mark = _mark_price(sym, ts, avg)
                if mark is None:
                    continue
                if qty > 0:
                    unreal += (mark - avg) * qty
                else:
                    unreal += (avg - mark) * abs(qty)
            return unreal, margin_total

        current_idx = 0
        trade_count = len(trades)
        # timeline minute loop
        # start_ts and end_ts already computed above when fetching prices

        def _record_equity(ts: datetime) -> None:
            unreal, margin_total = _unrealized_and_margin(ts)
            equity = cash + margin_total + unreal
            cumulative_net_local = equity - initial_deposit
            equity_curve.append(
                {"timestamp": ts, "equity_usd": float(equity), "unrealized_pnl_usd": float(unreal)}
            )
            return cumulative_net_local

        # iterate minute by minute and process trades that occur within or before that minute
        if start_ts and end_ts:
            delta_minutes = int((end_ts - start_ts).total_seconds() // 60)
            step_minutes = 1
            if delta_minutes > 60 * 24 * 60:
                step_minutes = 5
            if delta_minutes > 60 * 24 * 180:
                step_minutes = 15
            ts = start_ts
            while ts <= end_ts:
                # process trades with timestamp <= end of this minute
                minute_end = ts.replace(second=59, microsecond=999999)
                while current_idx < trade_count and trades[current_idx].timestamp <= minute_end:
                    t = trades[current_idx]
                    current_idx += 1
                    # existing processing per trade
                    direction = t.direction if hasattr(t.direction, "value") else TradeDirection(str(t.direction))
                    notional = Decimal(abs(t.value_usd or 0))
                    scale = Decimal(used_pct)
                    current_unreal, current_margin = _unrealized_and_margin(t.timestamp)
                    equity_now = cash + current_margin + current_unreal
                    desired_notional = notional * scale
                    per_trade_cap_ratio = Decimal("0.05")  # at most 5% of levered equity per trade
                    if direction in closing_dirs:
                        # Allow closes even when cash is depleted; position size will cap the executed notional.
                        user_notional = desired_notional
                    else:
                        # Cap exposure by available equity * leverage to avoid oversizing; also per-trade cap to preserve dry powder
                        max_notional_overall = equity_now * leverage
                        max_notional_per_trade = max_notional_overall * per_trade_cap_ratio
                        user_notional = (
                            min(desired_notional, max_notional_per_trade) if max_notional_overall > 0 else Decimal(0)
                        )
                    if user_notional <= 0:
                        continue
                    price = None
                    try:
                        if t.value_usd is not None and t.amount_base not in (None, 0):
                            price = Decimal(abs(t.value_usd)) / Decimal(abs(t.amount_base))
                    except Exception:
                        price = None
                    sym_key = (t.base_asset or "").upper() or None
                    price = _mark_price(sym_key, t.timestamp, price)
                    if price is None or price <= 0:
                        continue
                    base_label = t.base_asset or "UNKNOWN"
                    pos_key = sym_key or base_label
                    pos = positions.setdefault(
                        pos_key, {"qty": Decimal(0), "avg_price": Decimal(0), "margin": Decimal(0)}
                    )

                    net_change = Decimal(0)
                    pnl = Decimal(0)
                    executed_notional = user_notional
                    fee = Decimal(0)
                    slip = Decimal(0)

                    if direction in entry_dirs:
                        fee = user_notional * fee_rate
                        slip = user_notional * slippage_rate
                        # adjust size if we can't afford margin + costs
                        margin_required = user_notional / leverage
                        total_cost = margin_required + fee + slip
                        if total_cost > cash:
                            afford_scale = cash / total_cost if total_cost > 0 else Decimal(0)
                            user_notional *= afford_scale
                            fee = user_notional * fee_rate
                            slip = user_notional * slippage_rate
                            margin_required = user_notional / leverage
                            total_cost = margin_required + fee + slip
                            if user_notional <= 0 or total_cost > cash:
                                continue
                        executed_notional = user_notional
                        total_fees += fee
                        total_slippage += slip

                        qty = user_notional / price
                        signed_qty = qty if direction in {TradeDirection.LONG, TradeDirection.BUY} else -qty
                        if signed_qty != 0:
                            new_qty = pos["qty"] + signed_qty
                            if new_qty == 0:
                                pos["qty"] = Decimal(0)
                                pos["avg_price"] = Decimal(0)
                                pos["margin"] = Decimal(0)
                            else:
                                existing_cost = pos["avg_price"] * pos["qty"]
                                added_cost = price * signed_qty
                                pos["qty"] = new_qty
                                pos["avg_price"] = (existing_cost + added_cost) / new_qty if new_qty != 0 else Decimal(0)
                                pos["margin"] += margin_required
                        # pay margin + costs
                        cash -= (margin_required + fee + slip)
                        net_change -= (fee + slip)
                    elif direction in closing_dirs:
                        pos_qty = pos["qty"]
                        if pos_qty == 0:
                            continue
                        qty = user_notional / price
                        close_qty = min(abs(qty), abs(pos_qty))
                        if close_qty <= 0:
                            continue
                        executed_notional = close_qty * price
                        fee = executed_notional * fee_rate
                        slip = executed_notional * slippage_rate
                        total_fees += fee
                        total_slippage += slip
                        signed_close = close_qty if pos_qty > 0 else -close_qty
                        avg = pos["avg_price"]
                        pnl = (price - avg) * signed_close if pos_qty > 0 else (avg - price) * abs(signed_close)
                        margin_release = pos["margin"] * (close_qty / abs(pos_qty)) if pos["margin"] else Decimal(0)
                        pos["qty"] = pos_qty - signed_close
                        if pos["qty"] == 0:
                            pos["avg_price"] = Decimal(0)
                            pos["margin"] = Decimal(0)
                        else:
                            pos["margin"] -= margin_release
                        net = pnl - fee - slip
                        gross_pnl += pnl
                        net_change += net
                        cash += margin_release + net
                        closing_count += 1
                        if net > 0:
                            wins += 1
                    else:
                        continue

                    unreal, margin_total = _unrealized_and_margin(t.timestamp)
                    equity = cash + margin_total + unreal
                    cumulative_net = equity - initial_deposit
                    results.append(
                        BacktestTradeResult(
                            id=t.id,
                            timestamp=t.timestamp,
                            direction=str(direction.value if hasattr(direction, "value") else direction),
                            base_asset=t.base_asset,
                            notional_usd=float(executed_notional),
                            pnl_usd=float(pnl),
                            fee_usd=float(fee),
                            slippage_usd=float(slip),
                            net_pnl_usd=float(net_change if net_change != 0 else (pnl - fee - slip)),
                            cumulative_pnl_usd=float(cumulative_net),
                            equity_usd=float(equity),
                            unrealized_pnl_usd=float(unreal),
                            position_size_base=float(pos["qty"]) if pos["qty"] is not None else None,
                        )
                    )

                _record_equity(ts.replace(second=0, microsecond=0))
                ts = ts + timedelta(minutes=step_minutes)

        # Ensure at least one equity point if trades existed
        if not equity_curve and trades:
            _record_equity(trades[-1].timestamp)

        max_dd_ratio, max_dd_usd = _compute_drawdown(equity_curve)
        roi = float(cumulative_net / initial_deposit * Decimal(100)) if initial_deposit > 0 else 0.0
        win_rate = float(wins) / float(closing_count) * 100 if closing_count > 0 else None
        max_drawdown_percent = float(max_dd_ratio * Decimal(100)) if max_dd_ratio is not None else None
        max_drawdown_usd = float(max_dd_usd) if max_dd_usd is not None else None

        summary = BacktestSummary(
            initial_deposit_usd=float(initial_deposit),
            recommended_position_pct=recommended_pct * 100.0,
            used_position_pct=used_pct * 100.0,
            leverage_used=float(leverage),
            asset_symbols=assets_used,
            total_fees_usd=float(total_fees),
            total_slippage_usd=float(total_slippage),
            gross_pnl_usd=float(gross_pnl),
            net_pnl_usd=float(cumulative_net),
            roi_percent=roi,
            trades_copied=len(results),
            win_rate_percent=win_rate,
            max_drawdown_percent=max_drawdown_percent,
            max_drawdown_usd=max_drawdown_usd,
            start=trades[0].timestamp if trades else None,
            end=trades[-1].timestamp if trades else None,
        )

        total_trades = len(results)
        start_idx = min(trades_offset, total_trades)
        end_idx = min(start_idx + trades_limit, total_trades)
        trade_slice = results[start_idx:end_idx]

        # Persist backtest parameters and key stats for later copier creation
        run_record = BacktestRun(
            whale_id=whale.id,
            leverage=leverage,
            position_size_pct=summary.used_position_pct,
            asset_symbols=assets_used,
            win_rate_percent=win_rate,
            trades_copied=len(results),
            max_drawdown_percent=max_drawdown_percent,
            max_drawdown_usd=Decimal(max_drawdown_usd) if max_drawdown_usd is not None else None,
            initial_deposit_usd=initial_deposit,
            net_pnl_usd=cumulative_net,
            roi_percent=roi,
        )
        try:
            session.add(run_record)
            _commit_with_retry(session)
        except OperationalError as exc:
            session.rollback()
            exc_str = str(exc).lower()
            if "no such table" in exc_str and "backtest_runs" in exc_str:
                created = _ensure_backtest_runs_table(session, retries=3, delay=1.5)
                if created:
                    try:
                        session.add(run_record)
                        _commit_with_retry(session)
                        logger.info("Created missing backtest_runs table and retried commit")
                    except OperationalError as exc_retry:
                        session.rollback()
                        if "database is locked" in str(exc_retry).lower():
                            logger.warning(
                                "Could not persist backtest run due to SQLite lock after creating table; skipping persistence"
                            )
                        else:
                            raise
                else:
                    logger.error("backtest_runs table missing and automatic creation failed; skipping persistence")
            elif "database is locked" in exc_str:
                logger.warning("Could not persist backtest run due to SQLite lock; skipping persistence")
            else:
                raise
        except Exception:
            session.rollback()
            raise

        price_points = None
        if payload.include_price_points:
            price_points = {
                sym: [{"timestamp": ts, "price": float(p)} for ts, p in zip(series[0], series[1])]
                for sym, series in price_cache.items()
            }

        return CopierBacktestResponse(
            summary=summary,
            trades=trade_slice,
            equity_curve=equity_curve,
            price_points=price_points,
            trades_total=total_trades,
            trades_limit=trades_limit,
            trades_offset=trades_offset,
        )


@router.post("/copier/multi", response_model=MultiWhaleBacktestResponse)
def run_multi_whale_backtest(payload: MultiWhaleBacktestRequest) -> MultiWhaleBacktestResponse:
    with SessionLocal() as session:
        chain_obj = session.scalar(select(Chain).where(Chain.slug == payload.chain.lower()))
        if not chain_obj:
            raise HTTPException(status_code=404, detail="Chain not found")

        addresses_lc = [addr.lower() for addr in payload.addresses]
        whales = (
            session.query(Whale)
            .filter(Whale.chain_id == chain_obj.id)
            .filter(func.lower(Whale.address).in_(addresses_lc))
            .all()
        )
        if not whales:
            raise HTTPException(status_code=404, detail="No whales found for requested addresses")

        entry_dirs = {TradeDirection.LONG, TradeDirection.SHORT, TradeDirection.BUY}
        asset_filter = {sym.upper() for sym in payload.asset_symbols} if payload.asset_symbols else None

        trade_query = (
            session.query(Trade)
            .filter(Trade.whale_id.in_([w.id for w in whales]), Trade.direction.in_(entry_dirs))
            .order_by(Trade.timestamp.asc(), Trade.id.asc())
        )
        if payload.start:
            trade_query = trade_query.filter(Trade.timestamp >= payload.start)
        if payload.end:
            trade_query = trade_query.filter(Trade.timestamp <= payload.end)
        if asset_filter:
            trade_query = trade_query.filter(Trade.base_asset.in_(list(asset_filter)))
        trades = trade_query.all()

        initial_deposit = Decimal(payload.initial_deposit_usd)
        used_pct = (
            float(payload.position_size_pct) / 100.0
            if payload.position_size_pct is not None
            else 1.0
        )
        used_pct = max(0.0, min(used_pct, 2.0))
        recommended_pct = used_pct
        fee_rate = Decimal(payload.fee_bps) / Decimal(10_000)
        slippage_rate = Decimal(payload.slippage_bps) / Decimal(10_000)
        leverage = Decimal(payload.leverage or 1.0)
        leverage = max(Decimal("0.1"), min(leverage, Decimal("100")))

        window = timedelta(minutes=payload.align_window_minutes)
        entries = [
            (
                t.timestamp,
                (t.base_asset or "").upper(),
                TradeDirection(t.direction) if isinstance(t.direction, str) else t.direction,
                t.value_usd,
                t.whale_id,
            )
            for t in trades
            if t.base_asset and t.value_usd is not None
        ]
        entries.sort(key=lambda x: x[0])

        signals: list[dict[str, Any]] = []
        last_signal_time: dict[tuple[str, str], datetime] = {}
        for i, (ts, asset, direction, value_usd, wid) in enumerate(entries):
            if not asset:
                continue
            dir_sign = TradeDirection.LONG if direction in {TradeDirection.LONG, TradeDirection.BUY} else TradeDirection.SHORT
            key = (asset, dir_sign.value if hasattr(dir_sign, "value") else str(dir_sign))
            if key in last_signal_time and (ts - last_signal_time[key]) <= window:
                continue
            aligned_ids = {wid}
            notionals: list[float] = []
            try:
                notionals.append(abs(float(value_usd)))
            except Exception:
                pass
            j = i + 1
            while j < len(entries) and entries[j][0] - ts <= window:
                ts2, asset2, dir2, val2, wid2 = entries[j]
                dir2_sign = TradeDirection.LONG if dir2 in {TradeDirection.LONG, TradeDirection.BUY} else TradeDirection.SHORT
                if asset2 == asset and dir2_sign == dir_sign:
                    aligned_ids.add(wid2)
                    try:
                        notionals.append(abs(float(val2)))
                    except Exception:
                        pass
                j += 1
            if len(aligned_ids) >= payload.min_whales:
                notional_avg = sum(notionals) / len(notionals) if notionals else 0.0
                if notional_avg <= 0:
                    continue
                signals.append(
                    {
                        "timestamp": ts,
                        "asset": asset,
                        "direction": dir_sign,
                        "notional_usd": notional_avg,
                        "whales": aligned_ids,
                    }
                )
                last_signal_time[key] = ts
            if payload.max_trades and len(signals) >= payload.max_trades:
                break

        pseudo_trades: list[SimpleNamespace] = []
        for idx, sig in enumerate(signals, start=1):
            pseudo_trades.append(
                SimpleNamespace(
                    id=idx,
                    timestamp=sig["timestamp"],
                    base_asset=sig["asset"],
                    direction=sig["direction"],
                    value_usd=sig["notional_usd"],
                    amount_base=None,
                )
            )

        if not pseudo_trades:
            empty_summary = BacktestSummary(
                initial_deposit_usd=float(initial_deposit),
                recommended_position_pct=recommended_pct * 100.0,
                used_position_pct=used_pct * 100.0,
                leverage_used=float(leverage),
                asset_symbols=sorted(asset_filter) if asset_filter else [],
                total_fees_usd=0.0,
                total_slippage_usd=0.0,
                gross_pnl_usd=0.0,
                net_pnl_usd=0.0,
                roi_percent=0.0,
                trades_copied=0,
                win_rate_percent=None,
                max_drawdown_percent=0.0,
                max_drawdown_usd=0.0,
                start=None,
                end=None,
            )
            return MultiWhaleBacktestResponse(
                summary=empty_summary,
                trades=[],
                equity_curve=[],
                price_points=None,
                trades_total=0,
                signals_total=0,
            )

        summary, trade_slice, equity_curve, price_points, total_trades = _simulate_copy_trades(
            session,
            pseudo_trades,
            initial_deposit=initial_deposit,
            recommended_pct=recommended_pct,
            used_pct=used_pct,
            fee_rate=fee_rate,
            slippage_rate=slippage_rate,
            leverage=leverage,
            include_price_points=payload.include_price_points,
            preload_prices=payload.preload_prices,
            asset_filter=asset_filter,
            trades_limit=len(pseudo_trades),
            trades_offset=0,
        )

        return MultiWhaleBacktestResponse(
            summary=summary,
            trades=trade_slice,
            equity_curve=equity_curve,
            price_points=price_points,
            trades_total=total_trades,
            signals_total=len(signals),
        )


@router.get("/assets", response_model=WhaleAssetsResponse)
def list_whale_assets(chain: ChainId = Query(...), address: str = Query(...)) -> WhaleAssetsResponse:
    """List distinct assets a whale has traded to build selection UI."""
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, chain, address)
        rows = (
            session.query(Trade.base_asset)
            .filter(Trade.whale_id == whale.id, Trade.base_asset.isnot(None))
            .distinct()
            .all()
        )
        assets = sorted({r[0] for r in rows if r[0]})
        return WhaleAssetsResponse(assets=assets)


@router.get("/runs", response_model=list[BacktestRunSummary])
def list_backtest_runs(
    chain: ChainId = Query(...),
    address: str = Query(...),
    limit: int = Query(50, ge=1, le=500),
) -> list[BacktestRunSummary]:
    """List stored backtest runs for a whale to drive live copier presets."""
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, chain, address)
        rows = (
            session.query(BacktestRun)
            .filter(BacktestRun.whale_id == whale.id)
            .order_by(BacktestRun.id.desc())
            .limit(limit)
            .all()
        )
        out: list[BacktestRunSummary] = []
        for r in rows:
            out.append(
                BacktestRunSummary(
                    id=r.id,
                    whale_id=r.whale_id,
                    created_at=r.created_at,
                    leverage=float(r.leverage) if r.leverage is not None else None,
                    position_size_pct=float(r.position_size_pct) if r.position_size_pct is not None else None,
                    asset_symbols=r.asset_symbols or None,
                    win_rate_percent=float(r.win_rate_percent) if r.win_rate_percent is not None else None,
                    trades_copied=int(r.trades_copied) if r.trades_copied is not None else None,
                    max_drawdown_percent=float(r.max_drawdown_percent) if r.max_drawdown_percent is not None else None,
                    max_drawdown_usd=float(r.max_drawdown_usd) if r.max_drawdown_usd is not None else None,
                    initial_deposit_usd=float(r.initial_deposit_usd) if r.initial_deposit_usd is not None else None,
                    net_pnl_usd=float(r.net_pnl_usd) if r.net_pnl_usd is not None else None,
                    roi_percent=float(r.roi_percent) if r.roi_percent is not None else None,
                )
            )
        return out


@router.get("/live-trades", response_model=LiveTradesResponse)
def live_trades(
    chain: ChainId = Query(...),
    address: str = Query(...),
    since: datetime | None = Query(None, description="Return trades strictly after this timestamp"),
    limit: int = Query(50, ge=1, le=500),
) -> LiveTradesResponse:
    """Return latest trades for a whale to drive live copier polling."""
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, chain, address)
        q = (
            session.query(Trade)
            .filter(Trade.whale_id == whale.id)
            .order_by(Trade.timestamp.desc(), Trade.id.desc())
        )
        if since is not None:
            q = q.filter(Trade.timestamp > since)
        rows = q.limit(limit).all()
        trades_out = [
            {
                "id": t.id,
                "timestamp": t.timestamp,
                "direction": t.direction.value if hasattr(t.direction, "value") else str(t.direction),
                "base_asset": t.base_asset,
                "value_usd": float(t.value_usd) if t.value_usd is not None else None,
            }
            for t in rows
        ]
        trades_out = list(reversed(trades_out))  # return ascending
        return LiveTradesResponse(trades=trades_out)


@router.post("/live/start", response_model=CopierSessionStatus)
def start_copier_session(payload: StartCopierRequest) -> CopierSessionStatus:
    """Start a live copier session using a stored backtest run."""
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, payload.chain, payload.address)
        run = session.get(BacktestRun, payload.run_id)
        if not run or run.whale_id != whale.id:
            raise HTTPException(status_code=404, detail="Backtest run not found for whale")
        if payload.execute and (not settings.hyperliquid_private_key or not settings.hyperliquid_address):
            raise HTTPException(status_code=400, detail="Hyperliquid execution keys not configured")
        copier_manager.start()
        sess = copier_manager.create_session(
            whale=whale,
            run=run,
            execute=payload.execute,
            position_size_pct=payload.position_size_pct,
        )
        return CopierSessionStatus(
            session_id=sess.id,
            active=sess.active,
            processed=sess.processed,
            errors=sess.errors,
            notifications=sess.notifications,
        )


@router.post("/live/stop", response_model=CopierSessionStatus)
def stop_copier_session(session_id: int = Query(...)) -> CopierSessionStatus:
    copier_manager.stop_session(session_id)
    sess = copier_manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return CopierSessionStatus(
        session_id=sess.id,
        active=sess.active,
        processed=sess.processed,
        errors=sess.errors,
        notifications=sess.notifications,
    )


@router.get("/live/status", response_model=CopierSessionStatus)
def copier_session_status(session_id: int = Query(...)) -> CopierSessionStatus:
    sess = copier_manager.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return CopierSessionStatus(
        session_id=sess.id,
        active=sess.active,
        processed=sess.processed,
        errors=sess.errors,
        notifications=sess.notifications,
    )


@router.get("/live/active", response_model=list[CopierSessionStatus])
def list_active_copier_sessions(
    chain: ChainId = Query(...),
    address: str = Query(...),
) -> list[CopierSessionStatus]:
    """Return active copier sessions for a whale so the UI can resume after refresh/navigation."""
    with SessionLocal() as session:
        whale, _ = _resolve_whale(session, chain, address)
    sessions = copier_manager.list_sessions_for_whale(whale.id)
    out: list[CopierSessionStatus] = []
    for sess in sessions:
        out.append(
            CopierSessionStatus(
                session_id=sess.id,
                active=sess.active,
                processed=sess.processed,
                errors=sess.errors,
                notifications=sess.notifications,
            )
        )
    return out
