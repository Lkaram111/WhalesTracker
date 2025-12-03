
from fastapi import APIRouter

from app.api import dashboard, events, wallets, whales

router = APIRouter()
router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
router.include_router(whales.router, prefix="/whales", tags=["whales"])
router.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
router.include_router(events.router, prefix="/events", tags=["events"])
