from __future__ import annotations

import logging
from typing import Callable

from sqlalchemy.orm import Session

from app.models import Chain, Whale
from app.services.metrics_service import (
    _commit_with_retry,
    recompute_wallet_metrics,
    rebuild_portfolio_history_from_trades,
)
from app.workers.bitcoin_ingestor import BitcoinIngestor
from app.workers.ethereum_ingestor import EthereumIngestor
from app.workers.hyperliquid_ingestor import HyperliquidIngestor

logger = logging.getLogger(__name__)


ProgressCb = Callable[[float, str | None], None]


def backfill_wallet_history(session: Session, whale: Whale, progress_cb: ProgressCb | None = None) -> bool:
    """Ensure historical trades/events exist for a newly added whale before returning."""
    chain = session.get(Chain, whale.chain_id)
    if not chain:
        return False

    backfilled = False
    progress = progress_cb or (lambda pct, msg=None: None)
    progress(5.0, "backfill: starting")
    if chain.slug == "bitcoin":
        backfilled = BitcoinIngestor().backfill_whale(session, chain.id, whale, progress_cb=progress_cb)
        _commit_with_retry(session)
    elif chain.slug == "ethereum":
        progress(50.0, "backfill: ethereum not implemented; skipping")
        backfilled = EthereumIngestor().backfill_whale(session, chain.id, whale)
        _commit_with_retry(session)
    elif chain.slug == "hyperliquid":
        try:
            ingestor = HyperliquidIngestor(poll_interval=300.0)
            backfilled = ingestor._process_account(session, chain.id, whale, max_pages=50, progress_cb=progress_cb)
            _commit_with_retry(session)
        except Exception as exc:
            logger.exception("Failed to backfill Hyperliquid whale %s: %s", whale.address, exc)

    if backfilled:
        recompute_wallet_metrics(session, whale)
        rebuild_portfolio_history_from_trades(session, whale)
        _commit_with_retry(session)
    progress(100.0, "backfill: done" if backfilled else "backfill: completed with no data")
    return backfilled
