import os
import sys
from pathlib import Path

os.environ["ENABLE_INGESTORS"] = "false"
os.environ["ENABLE_SCHEDULER"] = "false"

# Point to populated SQLite db regardless of working directory
BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "whales.db"
os.environ["DATABASE_URL"] = f"sqlite:///{DB_PATH}"

if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_dashboard_summary():
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert "total_tracked_whales" in body
    assert "total_volume_24h_usd" in body


def test_whales_list():
    resp = client.get("/api/v1/whales?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "total" in body
