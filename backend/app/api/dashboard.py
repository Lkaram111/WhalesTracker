from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import func, select, String

from app.db.session import SessionLocal
from app.models import Trade, Whale, WalletMetricsDaily, Chain
from app.schemas.api import DashboardSummary

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary() -> DashboardSummary:
    with SessionLocal() as session:
        total_tracked = session.scalar(select(func.count()).select_from(Whale)) or 0

        active_since = datetime.now(timezone.utc) - timedelta(hours=24)
        active_24h = (
            session.scalar(
                select(func.count())
                .select_from(Whale)
                .where(Whale.last_active_at >= active_since)
            )
            or 0
        )

        volume_24h = (
            session.scalar(
                select(func.coalesce(func.sum(Trade.value_usd), 0)).where(
                    Trade.timestamp >= active_since
                )
            )
            or 0
        )

        hyperliquid_whales = session.scalar(
            select(func.count())
            .select_from(Whale)
            .where(func.lower(func.cast(Whale.labels, String)).like("%hyperliquid%"))
        ) or 0

        return DashboardSummary(
            total_tracked_whales=int(total_tracked),
            active_whales_24h=int(active_24h),
            total_volume_24h_usd=float(volume_24h),
            hyperliquid_whales=int(hyperliquid_whales),
        )


@router.get("/ingestion-status")
async def ingestion_status() -> dict:
    """Heartbeat: latest trade per chain and last daily snapshot."""
    with SessionLocal() as session:
        chains = {c.id: c.slug for c in session.query(Chain).all()}
        latest_by_chain = {}
        for chain_id, slug in chains.items():
            ts = session.scalar(
                select(func.max(Trade.timestamp)).where(Trade.chain_id == chain_id)
            )
            latest_by_chain[slug] = ts.isoformat() if ts else None
        latest_daily = session.scalar(select(func.max(WalletMetricsDaily.date)))
        return {
            "latest_trade_by_chain": latest_by_chain,
            "latest_wallet_metrics_daily": str(latest_daily) if latest_daily else None,
            "total_trades": int(session.scalar(select(func.count()).select_from(Trade)) or 0),
        }
