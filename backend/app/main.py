import asyncio
import logging
import signal
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.core.config import settings
from app.core.scheduler import start_scheduler
from app.workers.bitcoin_ingestor import BitcoinIngestor
from app.workers.ethereum_ingestor import EthereumIngestor
from app.workers.hyperliquid_ingestor import HyperliquidIngestor


@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:  # pragma: no cover - lifecycle wiring
    scheduler = start_scheduler() if settings.enable_scheduler else None
    tasks: list[asyncio.Task] = []
    ingestors = []
    loop = asyncio.get_running_loop()

    if settings.enable_ingestors:
        ingestors = [
            EthereumIngestor(),
            BitcoinIngestor(),
            HyperliquidIngestor(),
        ]
        for ingestor in ingestors:
            tasks.append(asyncio.create_task(ingestor.run_forever()))

    async def _graceful_shutdown() -> None:
        if scheduler:
            scheduler.shutdown(wait=False)
        for ingestor in ingestors:
            ingestor.stop()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _handle_signal() -> None:
        # Schedule cleanup promptly on CTRL+C / SIGTERM
        loop.call_soon_threadsafe(asyncio.create_task, _graceful_shutdown())

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None)):
        if sig is not None:
            try:
                loop.add_signal_handler(sig, _handle_signal)
            except NotImplementedError:
                # Windows may not support signal handlers; uvicorn will still handle Ctrl+C
                pass

    yield

    await _graceful_shutdown()
    # Ensure graceful exit on SIGINT/SIGTERM



def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    application = FastAPI(title="Whale Tracker API", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_origin_regex=".*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/health")
    async def health():
        return {"status": "ok"}

    return application


app = create_app()
