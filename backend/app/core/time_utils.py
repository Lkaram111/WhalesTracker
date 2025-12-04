from datetime import datetime

from app.core.config import settings


def now() -> datetime:
    """Timezone-aware now based on configured app timezone."""
    return datetime.now(settings.tzinfo)
