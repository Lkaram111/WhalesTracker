from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Sequence

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Chain, PriceHistory, Trade, TradeDirection, Whale
from app.schemas.api import (
    BacktestSummary,
    BacktestTradeResult,
    ChainId,
    CopierBacktestRequest,
    CopierBacktestResponse,
    WhaleAssetsResponse,
)
from app.services.price_service import fetch_and_store_binance_prices

router = APIRouter()


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

        closing_dirs = {
            TradeDirection.CLOSE_LONG,
            TradeDirection.CLOSE_SHORT,
            TradeDirection.SELL,
            TradeDirection.WITHDRAW,
        }
        entry_dirs = {TradeDirection.LONG, TradeDirection.SHORT, TradeDirection.BUY}
        ignore_dirs = {TradeDirection.DEPOSIT}

        trade_query = (
            session.query(Trade)
            .filter(Trade.whale_id == whale.id, Trade.direction.notin_(ignore_dirs))
            .order_by(Trade.timestamp.asc(), Trade.id.asc())
        )
        if payload.start:
            trade_query = trade_query.filter(Trade.timestamp >= payload.start)
        if payload.end:
            trade_query = trade_query.filter(Trade.timestamp <= payload.end)
        if payload.asset_symbols:
            trade_query = trade_query.filter(Trade.base_asset.in_(payload.asset_symbols))
        if payload.max_trades:
            trade_query = trade_query.limit(payload.max_trades)
        trades = trade_query.all()
        if not trades:
            raise HTTPException(status_code=404, detail="No trades available for backtest")

        entry_query = (
            session.query(Trade.value_usd)
            .filter(
                Trade.whale_id == whale.id,
                Trade.direction.in_(entry_dirs),
                Trade.value_usd.isnot(None),
            )
            .order_by(Trade.timestamp.asc())
        )
        entry_sizes = [Decimal(abs(t.value_usd)) for t in entry_query.all() if t.value_usd]
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
        assets = {t.base_asset for t in trades if t.base_asset}
        price_cache: dict[str, list[tuple[datetime, Decimal]]] = {}

        # determine backtest window for price fetch
        start_ts = trades[0].timestamp.replace(second=0, microsecond=0) if trades else None
        end_ts = trades[-1].timestamp.replace(second=0, microsecond=0) if trades else None

        if assets and start_ts and end_ts:
            try:
                # fetch 1m prices for full window (with small buffer) if missing
                fetch_and_store_binance_prices(
                    session,
                    assets=list(assets),
                    timeframe="1m",
                    since=start_ts - timedelta(minutes=1),
                    until=end_ts + timedelta(minutes=1),
                    limit=1000,
                )
                session.flush()
            except Exception:
                pass

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
                price_cache.setdefault(sym, []).append((ts, Decimal(price)))

        def _mark_price(sym: str | None, ts: datetime, fallback: Decimal | None) -> Decimal | None:
            if sym is None:
                return fallback
            series = price_cache.get(sym)
            if not series:
                return fallback
            # latest price at or before ts
            last = None
            for tstamp, p in series:
                if tstamp <= ts:
                    last = p
                else:
                    break
            return last if last is not None else fallback

        positions: dict[str, dict[str, Decimal]] = {}
        cash = initial_deposit
        cumulative_net = Decimal(0)
        total_fees = Decimal(0)
        total_slippage = Decimal(0)
        gross_pnl = Decimal(0)
        wins = 0
        results: list[BacktestTradeResult] = []
        equity_curve: list[dict] = []

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
                    # Cap exposure by available equity * leverage to avoid oversizing; also per-trade cap to preserve dry powder
                    current_unreal, current_margin = _unrealized_and_margin(t.timestamp)
                    equity_now = cash + current_margin + current_unreal
                    desired_notional = notional * scale
                    max_notional_overall = equity_now * leverage
                    per_trade_cap_ratio = Decimal("0.05")  # at most 5% of levered equity per trade
                    max_notional_per_trade = max_notional_overall * per_trade_cap_ratio
                    user_notional = min(desired_notional, max_notional_per_trade) if max_notional_overall > 0 else Decimal(0)
                    if user_notional <= 0:
                        continue
                    price = None
                    try:
                        if t.value_usd is not None and t.amount_base not in (None, 0):
                            price = Decimal(abs(t.value_usd)) / Decimal(abs(t.amount_base))
                    except Exception:
                        price = None
                    price = _mark_price(t.base_asset, t.timestamp, price)
                    if price is None:
                        continue
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
                    total_fees += fee
                    total_slippage += slip

                    qty = user_notional / price

                    base = t.base_asset or "UNKNOWN"
                    pos = positions.setdefault(base, {"qty": Decimal(0), "avg_price": Decimal(0), "margin": Decimal(0)})

                    net_change = Decimal(0)
                    pnl = Decimal(0)

                    if direction in entry_dirs:
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
                            total_fees -= fee
                            total_slippage -= slip
                            continue
                        close_qty = min(abs(qty), abs(pos_qty))
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
                        if net > 0:
                            wins += 1
                    else:
                        total_fees -= fee
                        total_slippage -= slip
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
                            notional_usd=float(user_notional),
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

                _record_equity(minute_end.replace(second=0, microsecond=0))
                ts = ts + timedelta(minutes=1)

        # Ensure at least one equity point if trades existed
        if not equity_curve and trades:
            _record_equity(trades[-1].timestamp)

        roi = float(cumulative_net / initial_deposit * Decimal(100)) if initial_deposit > 0 else 0.0
        win_rate = float(wins) / float(len([r for r in results if r.net_pnl_usd != 0])) * 100 if results else None

        summary = BacktestSummary(
            initial_deposit_usd=float(initial_deposit),
            recommended_position_pct=recommended_pct * 100.0,
            used_position_pct=used_pct * 100.0,
            total_fees_usd=float(total_fees),
            total_slippage_usd=float(total_slippage),
            gross_pnl_usd=float(gross_pnl),
            net_pnl_usd=float(cumulative_net),
            roi_percent=roi,
            trades_copied=len(results),
            win_rate_percent=win_rate,
            start=trades[0].timestamp if trades else None,
            end=trades[-1].timestamp if trades else None,
        )

        price_points = None
        if payload.include_price_points:
            price_points = {
                sym: [{"timestamp": ts, "price": float(p)} for ts, p in series]
                for sym, series in price_cache.items()
            }

        return CopierBacktestResponse(
            summary=summary,
            trades=results,
            equity_curve=equity_curve,
            price_points=price_points,
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
