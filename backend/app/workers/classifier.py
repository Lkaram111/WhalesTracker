from __future__ import annotations

from sqlalchemy import func

from app.db.session import SessionLocal
from app.models import Trade, Whale, WhaleType


class WhaleClassifier:
    def __init__(self, trade_threshold: int = 10, volume_threshold_usd: float = 100000.0) -> None:
        self.trade_threshold = trade_threshold
        self.volume_threshold_usd = volume_threshold_usd

    def classify_whale(self, session, whale: Whale) -> WhaleType:
        trade_count = session.scalar(
            session.query(func.count(Trade.id)).filter(Trade.whale_id == whale.id)
        ) or 0
        volume = session.scalar(
            session.query(func.coalesce(func.sum(Trade.value_usd), 0)).filter(
                Trade.whale_id == whale.id
            )
        ) or 0

        if trade_count >= self.trade_threshold or float(volume) >= self.volume_threshold_usd:
            return WhaleType.TRADER
        return WhaleType.HOLDER

    def run(self) -> None:
        with SessionLocal() as session:
            whales = session.query(Whale).all()
            for whale in whales:
                new_type = self.classify_whale(session, whale)
                if whale.type != new_type:
                    whale.type = new_type
                    session.add(whale)
            session.commit()


classifier = WhaleClassifier()
