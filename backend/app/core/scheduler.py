from __future__ import annotations

from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.models import Whale
from app.services.holdings_service import refresh_holdings_for_whales
from app.services.metrics_service import recompute_all_wallet_metrics
from app.services.price_updater import update_prices
from app.workers.classifier import classifier


def _refresh_holdings_and_metrics() -> None:
    try:
        with SessionLocal() as session:
            whales = session.query(Whale).all()
            refresh_holdings_for_whales(session, whales)
            recompute_all_wallet_metrics(session)
    except Exception:
        return


def _classify_whales() -> None:
    try:
        classifier.run()
    except Exception:
        return


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
        update_prices,
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
