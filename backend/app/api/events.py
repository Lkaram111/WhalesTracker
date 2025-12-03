from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Chain, Event, Whale
from app.schemas.api import EventsResponse
from app.services.broadcast import broadcast_manager

router = APIRouter()


@router.get("/recent", response_model=EventsResponse)
async def get_recent_events(
    limit: int = Query(default=10),
) -> EventsResponse:
    with SessionLocal() as session:
        rows = (
            session.query(Event, Whale, Chain)
            .join(Whale, Whale.id == Event.whale_id)
            .join(Chain, Chain.id == Event.chain_id)
            .order_by(Event.timestamp.desc())
            .limit(limit)
            .all()
        )
        items = [
            {
                "id": str(ev.id),
                "timestamp": ev.timestamp,
                "chain": chain.slug,  # type: ignore[arg-type]
                "type": ev.type.value if hasattr(ev.type, "value") else ev.type,
                "wallet": {
                    "address": whale.address,
                    "chain": chain.slug,  # type: ignore[arg-type]
                    "label": (whale.labels or [None])[0] if whale.labels else None,
                },
                "summary": ev.summary or "",
                "value_usd": float(ev.value_usd or 0),
                "tx_hash": ev.tx_hash.hex() if isinstance(ev.tx_hash, (bytes, bytearray)) else ev.tx_hash,
                "details": ev.details or {},
            }
            for ev, whale, chain in rows
        ]
        return EventsResponse(items=items)


@router.get("/live", response_model=EventsResponse)
async def get_live_events(
    limit: int = Query(default=50),
) -> EventsResponse:
    return await get_recent_events(limit=limit)


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await broadcast_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; we do not expect incoming messages.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcast_manager.disconnect(websocket)
