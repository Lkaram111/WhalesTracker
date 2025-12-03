from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Chain  # noqa: E402

CHAINS = [
    {"slug": "ethereum", "name": "Ethereum"},
    {"slug": "bitcoin", "name": "Bitcoin"},
    {"slug": "hyperliquid", "name": "Hyperliquid"},
]


def main() -> None:
    with SessionLocal() as session:
        for entry in CHAINS:
            existing = session.scalar(select(Chain).where(Chain.slug == entry["slug"]))
            if existing:
                existing.name = entry["name"]
            else:
                session.add(Chain(slug=entry["slug"], name=entry["name"]))
        session.commit()


if __name__ == "__main__":
    main()
