from pathlib import Path

from sqlalchemy import create_engine
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
    connect_args = {"check_same_thread": False}
    db_url = f"sqlite:///{path}"

engine = create_engine(db_url, future=True, echo=False, connect_args=connect_args)
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
