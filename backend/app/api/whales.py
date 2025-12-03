from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import and_, func, or_, select, String, cast

from app.db.session import SessionLocal
from app.models import Chain, CurrentWalletMetrics, Whale, WhaleType
from app.schemas.api import ListResponse, WhaleSummary, WhaleCreateRequest
from app.services.hyperliquid_client import hyperliquid_client
from app.services.metrics_service import recompute_wallet_metrics
from app.services.holdings_service import refresh_holdings_for_whales
from app.workers.hyperliquid_ingestor import HyperliquidIngestor

router = APIRouter()


@router.get("", response_model=ListResponse)
async def list_whales(
    chain: str | None = Query(default=None),
    type: str | None = Query(default=None),
    sortBy: str | None = Query(default=None),
    sortDir: str | None = Query(default=None),
    minRoi: float | None = Query(default=None),
    activityWindow: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=50),
    offset: int = Query(default=0),
) -> ListResponse:
    # Normalize Query default when called internally
    if not isinstance(chain, str):
        chain = None
    if not isinstance(search, str):
        search = None
    if not isinstance(type, str):
        type = None
    if not isinstance(sortDir, str):
        sortDir = None
    if not isinstance(sortBy, str):
        sortBy = None
    if not isinstance(minRoi, (int, float)):
        minRoi = None
    with SessionLocal() as session:
        query = (
            select(Whale, CurrentWalletMetrics, Chain)
            .join(Chain, Chain.id == Whale.chain_id)
            .outerjoin(CurrentWalletMetrics, CurrentWalletMetrics.whale_id == Whale.id)
        )

        conditions = []

        if chain:
            chains = [c.strip().lower() for c in chain.split(",") if c.strip()]
            if chains:
                conditions.append(Chain.slug.in_(chains))

        if type:
            conditions.append(Whale.type == type)

        if minRoi is not None:
            conditions.append(CurrentWalletMetrics.roi_percent >= minRoi)

        if activityWindow:
            try:
                hours = int(activityWindow.replace("h", ""))
                window_start = datetime.now(timezone.utc) - timedelta(hours=hours)
                conditions.append(Whale.last_active_at >= window_start)
            except Exception:
                pass

        if search:
            pattern = f"%{search.lower()}%"
            conditions.append(
                or_(
                    func.lower(Whale.address).like(pattern),
                    func.lower(cast(Whale.labels, String)).like(pattern),
                )
            )

        if conditions:
            query = query.where(and_(*conditions))

        sort_column = CurrentWalletMetrics.roi_percent
        if sortBy == "realized_pnl_usd":
            sort_column = CurrentWalletMetrics.realized_pnl_usd
        elif sortBy == "volume_30d_usd":
            sort_column = CurrentWalletMetrics.volume_30d_usd
        elif sortBy == "last_active_at":
            sort_column = Whale.last_active_at

        if sortDir and sortDir.lower() == "asc":
            query = query.order_by(sort_column.asc().nullslast())
        else:
            query = query.order_by(sort_column.desc().nullslast())

        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.execute(query.offset(offset).limit(limit)).all()

        items: list[WhaleSummary] = []
        for whale, metrics, chain_obj in rows:
            whale_type = (
                whale.type.value if hasattr(whale.type, "value") else str(whale.type).lower()
            )
            items.append(
                WhaleSummary(
                    address=whale.address,
                    chain=chain_obj.slug,  # type: ignore[arg-type]
                    type=whale_type,
                    labels=whale.labels or [],
                    roi_percent=float(metrics.roi_percent or 0) if metrics else 0.0,
                    realized_pnl_usd=float(metrics.realized_pnl_usd or 0) if metrics else 0.0,
                    unrealized_pnl_usd=float(metrics.unrealized_pnl_usd) if metrics and metrics.unrealized_pnl_usd is not None else None,
                    portfolio_value_usd=float(metrics.portfolio_value_usd or 0) if metrics else 0.0,
                    volume_30d_usd=float(metrics.volume_30d_usd or 0) if metrics else 0.0,
                    trades_30d=int(metrics.trades_30d or 0) if metrics else 0,
                    win_rate_percent=float(metrics.win_rate_percent) if metrics and metrics.win_rate_percent is not None else None,
                    last_active_at=whale.last_active_at or whale.first_seen_at or datetime.now(timezone.utc),
                )
            )

        return ListResponse(items=items, total=int(total))


@router.get("/top", response_model=ListResponse)
async def list_top_whales(
    limit: int = Query(default=10),
    sortBy: str | None = Query(default="roi"),
) -> ListResponse:
    return await list_whales(sortBy=sortBy, limit=limit, offset=0)


def _ensure_chain(session, slug: str, name: str | None = None) -> Chain:
    chain = session.scalar(select(Chain).where(Chain.slug == slug))
    if chain:
        return chain
    chain = Chain(slug=slug, name=name or slug.capitalize())
    session.add(chain)
    session.flush()
    return chain


def _maybe_hyperliquid(address: str) -> bool:
    try:
        data = hyperliquid_client.get_user_ledger(address)
        if isinstance(data, dict) and data.get("ledger"):
            return True
    except Exception:
        return False
    return False


@router.post("", response_model=WhaleSummary)
async def create_whale(payload: WhaleCreateRequest) -> WhaleSummary:
    with SessionLocal() as session:
        chain_slug = payload.chain
        labels = payload.labels or []
        is_hl = chain_slug == "hyperliquid" or _maybe_hyperliquid(payload.address)
        if is_hl and "hyperliquid" not in labels:
            labels.append("hyperliquid")
            chain_slug = "hyperliquid"

        chain = _ensure_chain(session, chain_slug, chain_slug.capitalize())

        existing = session.scalar(
            select(Whale).where(Whale.address == payload.address, Whale.chain_id == chain.id)
        )
        if existing:
            raise HTTPException(status_code=400, detail="Whale already exists for this chain")

        whale_type = payload.type or WhaleType.TRADER if is_hl else WhaleType.HOLDER
        whale = Whale(
            address=payload.address,
            chain_id=chain.id,
            type=whale_type,
            labels=labels,
        )
        session.add(whale)
        session.flush()

        if chain_slug == "hyperliquid":
            # Synchronously ingest Hyperliquid trades/positions for newly added wallet
            ingestor = HyperliquidIngestor(poll_interval=300.0)
            try:
                ingestor._process_account(session, chain.id, whale)  # populate trades/positions immediately
            except Exception:
                pass
        else:
            # Refresh holdings for ETH/BTC
            refresh_holdings_for_whales(session, [whale])

        recompute_wallet_metrics(session, whale)
        session.commit()

        # reload metrics
        metrics = session.get(CurrentWalletMetrics, whale.id)
        return WhaleSummary(
            address=whale.address,
            chain=chain.slug,  # type: ignore[arg-type]
            type=whale.type.value if hasattr(whale.type, "value") else whale.type,
            labels=whale.labels or [],
            roi_percent=float(metrics.roi_percent or 0) if metrics else 0.0,
            realized_pnl_usd=float(metrics.realized_pnl_usd or 0) if metrics else 0.0,
            unrealized_pnl_usd=float(metrics.unrealized_pnl_usd) if metrics and metrics.unrealized_pnl_usd is not None else None,
            portfolio_value_usd=float(metrics.portfolio_value_usd or 0) if metrics else 0.0,
            volume_30d_usd=float(metrics.volume_30d_usd or 0) if metrics else 0.0,
            trades_30d=int(metrics.trades_30d or 0) if metrics else 0,
            win_rate_percent=float(metrics.win_rate_percent) if metrics and metrics.win_rate_percent is not None else None,
            last_active_at=whale.last_active_at or whale.first_seen_at or datetime.now(timezone.utc),
        )
