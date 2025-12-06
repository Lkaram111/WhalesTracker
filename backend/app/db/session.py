from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings, PROJECT_ROOT

db_url = settings.database_url

connect_args: dict = {}
if db_url.startswith("sqlite"):
    raw_path = make_url(db_url).database or "."
    path = Path(raw_path)
    if not path.is_absolute():
        # Anchor relative paths to the backend project root to avoid cwd drift
        parts = path.parts
        if parts and parts[0].lower() == PROJECT_ROOT.name.lower():
            path = Path(*parts[1:])
        path = (PROJECT_ROOT / path).resolve()
    else:
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Give SQLite more breathing room under concurrent writers (scheduler + API)
    connect_args = {"check_same_thread": False, "timeout": 60}
    db_url = f"sqlite:///{path}"

engine_kwargs = {
    "future": True,
    "echo": False,
    "connect_args": connect_args,
    # pre_ping keeps connections fresh across idle periods; pool_recycle defends against MySQL timeouts.
    "pool_pre_ping": True,
}

if not db_url.startswith("sqlite"):
    engine_kwargs.update({"pool_recycle": 2800, "pool_timeout": 30})

engine = create_engine(db_url, **engine_kwargs)

# Improve SQLite concurrency (WAL + reasonable fsync)
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):  # pragma: no cover - DB wiring
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA busy_timeout=60000;")
            cursor.close()
        except Exception:
            pass
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
