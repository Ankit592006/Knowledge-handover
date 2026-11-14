"""Database engine, session factory, and pgvector / JSONB cross-dialect support."""

from typing import Any, Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
db_url = settings.normalized_database_url

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable SQLite foreign keys when running in local/test SQLite mode
if db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(target_engine: Any = None) -> None:
    """Initialize database extensions (pgvector on Postgres if available) and create missing tables."""
    active_engine = target_engine or engine
    if active_engine.dialect.name == "postgresql":
        try:
            with active_engine.begin() as conn:
                ext_row = conn.execute(
                    text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                ).fetchone()
                if ext_row is None:
                    with conn.begin_nested():
                        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            # Managed Postgres instances without superuser CREATE EXTENSION privilege will continue safely
            pass
    import app.models.entities  # noqa: F401
    Base.metadata.create_all(bind=active_engine)
