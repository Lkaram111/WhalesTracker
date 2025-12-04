from __future__ import annotations

from datetime import datetime

import logging
from apscheduler.executors.pool import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.models import Chain, Whale
from app.services.holdings_service import refresh_holdings_for_whales
from app.services.metrics_service import rebuild_all_portfolio_histories, recompute_wallet_metrics, _commit_with_retry
from app.services.price_updater import update_prices
from app.workers.classifier import classifier
from app.core.time_utils import now

logger = logging.getLogger(__name__)


def _refresh_holdings_and_metrics() -> None:
    started = now()
    logger.info("scheduler: refresh_holdings_and_metrics start")
    try:
        with SessionLocal() as session:
            whales = session.query(Whale).all()
            chain_map = {c.id: c for c in session.query(Chain).all()}
            # Hyperliquid whales are updated by the ingestor; skip to avoid redundant /info calls.
            non_hl_whales = [
                w for w in whales if chain_map.get(w.chain_id) and chain_map[w.chain_id].slug != "hyperliquid"
            ]
            refresh_holdings_for_whales(session, non_hl_whales)
            for whale in non_hl_whales:
                recompute_wallet_metrics(session, whale)
            _commit_with_retry(session)
    except Exception:
        logger.exception("scheduler: refresh_holdings_and_metrics failed")
        return
    logger.info("scheduler: refresh_holdings_and_metrics done in %.2fs", (now() - started).total_seconds())


def _rebuild_histories_job() -> None:
    started = now()
    logger.info("scheduler: rebuild_histories start")
    try:
        with SessionLocal() as session:
            rebuild_all_portfolio_histories(session)
    except Exception:
        logger.exception("scheduler: rebuild_histories failed")
        return
    logger.info("scheduler: rebuild_histories done in %.2fs", (now() - started).total_seconds())


def _classify_whales() -> None:
    started = now()
    logger.info("scheduler: classify_whales start")
    try:
        classifier.run()
    except Exception:
        logger.exception("scheduler: classify_whales failed")
        return
    logger.info("scheduler: classify_whales done in %.2fs", (now() - started).total_seconds())


def _update_prices_job() -> None:
    started = now()
    logger.info("scheduler: update_prices start")
    try:
        with SessionLocal() as session:
            update_prices(session)
    except Exception:
        logger.exception("scheduler: update_prices failed")
        return
    logger.info("scheduler: update_prices done in %.2fs", (now() - started).total_seconds())


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(executors={"default": ThreadPoolExecutor(max_workers=5)})
    scheduler.add_job(
        _refresh_holdings_and_metrics,
        "interval",
        minutes=15,
        next_run_time=now(),
        id="refresh_holdings_and_metrics",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _update_prices_job,
        "interval",
        minutes=30,
        next_run_time=now(),
        id="price_updater",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _rebuild_histories_job,
        "cron",
        hour=3,
        minute=0,
        id="rebuild_histories",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        _classify_whales,
        "interval",
        minutes=15,
        next_run_time=now(),
        id="whale_classifier",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler
