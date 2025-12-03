from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from app.db.session import SessionLocal  # noqa: E402
from app.models import Chain, Whale, WhaleType  # noqa: E402

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "ethereum_whales.yaml"


def load_whales(config_path: Path) -> list[dict[str, Any]]:
    if not config_path.exists():
        print(f"Config not found at {config_path}. Nothing to seed.")
        return []
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        print("Config must be a list of whale entries.")
        return []

    normalized: list[dict[str, Any]] = []
    for entry in raw:
        if isinstance(entry, str):
            normalized.append({"address": entry, "labels": []})
            continue
        if isinstance(entry, dict) and "address" in entry:
            labels = entry.get("labels") or []
            if isinstance(labels, str):
                labels = [labels]
            normalized.append({"address": entry["address"], "labels": labels})
            continue
        print(f"Skipping invalid entry: {entry}")
    return normalized


def ensure_chain(session, slug: str, name: str) -> Chain:
    chain = session.scalar(select(Chain).where(Chain.slug == slug))
    if chain:
        return chain
    chain = Chain(slug=slug, name=name)
    session.add(chain)
    session.flush()
    return chain


def main() -> None:
    whales = load_whales(CONFIG_PATH)
    if not whales:
        print("No whales to insert; exiting.")
        return

    with SessionLocal() as session:
        chain = ensure_chain(session, "ethereum", "Ethereum")
        inserted = 0
        for entry in whales:
            address = entry.get("address")
            labels = entry.get("labels", []) or []
            if not address:
                continue
            exists = session.scalar(
                select(Whale).where(Whale.address == address, Whale.chain_id == chain.id)
            )
            if exists:
                exists.labels = labels
                continue
            whale = Whale(
                address=address,
                chain_id=chain.id,
                type=WhaleType.HOLDER,
                labels=labels,
                first_seen_at=datetime.now(timezone.utc),
                last_active_at=None,
            )
            session.add(whale)
            inserted += 1
        session.commit()
        print(f"Seeded {inserted} Ethereum whales.")


if __name__ == "__main__":
    sys.exit(main())
