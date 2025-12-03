from __future__ import annotations

from datetime import datetime

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.models import Whale
from app.services.holdings_service import refresh_holdings_for_whales
from app.services.metrics_service import recompute_all_wallet_metrics
from app.services.price_updater import update_prices
from app.workers.classifier import classifier

logger = logging.getLogger(__name__)


def _refresh_holdings_and_metrics() -> None:
    started = datetime.now()
    logger.info("scheduler: refresh_holdings_and_metrics start")
    try:
        with SessionLocal() as session:
            whales = session.query(Whale).all()
            refresh_holdings_for_whales(session, whales)
            recompute_all_wallet_metrics(session)
    except Exception:
        logger.exception("scheduler: refresh_holdings_and_metrics failed")
        return
    logger.info("scheduler: refresh_holdings_and_metrics done in %.2fs", (datetime.now() - started).total_seconds())


def _classify_whales() -> None:
    started = datetime.now()
    logger.info("scheduler: classify_whales start")
    try:
        classifier.run()
    except Exception:
        logger.exception("scheduler: classify_whales failed")
        return
    logger.info("scheduler: classify_whales done in %.2fs", (datetime.now() - started).total_seconds())


def _update_prices_job() -> None:
    started = datetime.now()
    logger.info("scheduler: update_prices start")
    try:
        with SessionLocal() as session:
            update_prices(session)
    except Exception:
        logger.exception("scheduler: update_prices failed")
        return
    logger.info("scheduler: update_prices done in %.2fs", (datetime.now() - started).total_seconds())


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _refresh_holdings_and_metrics,
        "interval",
        minutes=5,
        next_run_time=datetime.now(),
        id="refresh_holdings_and_metrics",
        replace_existing=True,
        coalesce=True,
    )
    scheduler.add_job(
        _update_prices_job,
        "interval",
        minutes=30,
        next_run_time=datetime.now(),
        id="price_updater",
        replace_existing=True,
        coalesce=True,
    )
    scheduler.add_job(
        _classify_whales,
        "interval",
        minutes=15,
        next_run_time=datetime.now(),
        id="whale_classifier",
        replace_existing=True,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
