"""
One-off cleanup to remove non-Hyperliquid data and orphans.

Usage:
    python backend/testing/cleanup_non_hyperliquid.py
"""

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models import Chain, Whale, Trade, Event, Holding, WalletMetricsDaily, CurrentWalletMetrics, IngestionCheckpoint


def main() -> None:
    with SessionLocal() as session:
        hl_chain = session.query(Chain).filter(Chain.slug == "hyperliquid").one_or_none()
        if not hl_chain:
            print("No hyperliquid chain found; nothing to clean.")
            return

        # Delete non-Hyperliquid whales (should already be removed)
        removed_whales = session.query(Whale).filter(Whale.chain_id != hl_chain.id).delete(synchronize_session=False)
        print("Removed non-HL whales:", removed_whales)

        # Current HL whale ids
        hl_whale_ids = {w.id for w in session.query(Whale).filter(Whale.chain_id == hl_chain.id)}
        print("Hyperliquid whales remaining:", len(hl_whale_ids))

        # Delete non-HL trades/events/holdings
        non_hl_trades = (
            session.query(Trade)
            .filter(Trade.chain_id != hl_chain.id)
            .delete(synchronize_session=False)
        )
        non_hl_events = (
            session.query(Event)
            .filter(Event.chain_id != hl_chain.id)
            .delete(synchronize_session=False)
        )
        non_hl_holdings = (
            session.query(Holding)
            .filter(Holding.chain_id != hl_chain.id)
            .delete(synchronize_session=False)
        )
        print("Deleted non-HL trades/events/holdings:", non_hl_trades, non_hl_events, non_hl_holdings)

        # Orphan cleanup for tables keyed by whale_id
        orphan_trades = (
            session.query(Trade)
            .filter(~Trade.whale_id.in_(hl_whale_ids))
            .delete(synchronize_session=False)
        )
        orphan_events = (
            session.query(Event)
            .filter(~Event.whale_id.in_(hl_whale_ids))
            .delete(synchronize_session=False)
        )
        orphan_holdings = (
            session.query(Holding)
            .filter(~Holding.whale_id.in_(hl_whale_ids))
            .delete(synchronize_session=False)
        )
        orphan_daily = (
            session.query(WalletMetricsDaily)
            .filter(~WalletMetricsDaily.whale_id.in_(hl_whale_ids))
            .delete(synchronize_session=False)
        )
        orphan_metrics = (
            session.query(CurrentWalletMetrics)
            .filter(~CurrentWalletMetrics.whale_id.in_(hl_whale_ids))
            .delete(synchronize_session=False)
        )
        orphan_checkpoints = (
            session.query(IngestionCheckpoint)
            .filter(~IngestionCheckpoint.whale_id.in_(hl_whale_ids))
            .delete(synchronize_session=False)
        )
        print(
            "Deleted orphans trades/events/holdings/daily/metrics/checkpoints:",
            orphan_trades,
            orphan_events,
            orphan_holdings,
            orphan_daily,
            orphan_metrics,
            orphan_checkpoints,
        )

        # Normalize tx_hash to lowercase for HL trades to avoid dup clashes
        session.execute(
            text(
                "update trades set tx_hash=lower(tx_hash) where tx_hash is not null and chain_id=:cid"
            ),
            {"cid": hl_chain.id},
        )

        session.commit()
        print("Cleanup complete.")


if __name__ == "__main__":
    main()
