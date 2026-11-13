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


def ensure_pgvector_schema_and_index(target_engine: Any = None) -> bool:
    """Ensure pgvector extension, native vector(dim) column type, and HNSW cosine index exist on PostgreSQL."""
    active_engine = target_engine or engine
    if active_engine.dialect.name != "postgresql":
        return False

    dim = int(settings.EMBEDDING_DIMENSION)
    try:
        with active_engine.begin() as conn:
            ext_row = conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            if ext_row is None:
                try:
                    with conn.begin_nested():
                        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception:
                    return False
                ext_row = conn.execute(
                    text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                ).fetchone()
                if ext_row is None:
                    return False

            col_row = conn.execute(
                text(
                    "SELECT data_type, udt_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'document_chunks' AND column_name = 'embedding'"
                )
            ).fetchone()
            if col_row is not None and str(col_row[1]).lower() != "vector":
                import json
                import math
                from app.modules.processing.service import generate_embedding_vector

                rows = conn.execute(
                    text(
                        "SELECT dc.id, dc.content, dc.embedding, sd.title "
                        "FROM document_chunks dc "
                        "LEFT JOIN source_documents sd ON sd.id = dc.source_document_id"
                    )
                ).fetchall()
                for chunk_id, chunk_content, raw_emb, doc_title in rows:
                    parsed = raw_emb
                    if isinstance(raw_emb, str):
                        try:
                            parsed = json.loads(raw_emb)
                        except Exception:
                            parsed = None
                    valid = (
                        isinstance(parsed, (list, tuple))
                        and len(parsed) == dim
                        and all(
                            not isinstance(x, bool)
                            and isinstance(x, (int, float))
                            and math.isfinite(float(x))
                            for x in parsed
                        )
                    )
                    if not valid:
                        recomputed = generate_embedding_vector(
                            f"{doc_title or ''}\n{chunk_content or ''}",
                            dimension=dim,
                        )
                        conn.execute(
                            text(
                                "UPDATE document_chunks SET embedding = CAST(:emb_json AS json) WHERE id = :cid"
                            ),
                            {"emb_json": json.dumps(recomputed), "cid": chunk_id},
                        )

                conn.execute(
                    text(
                        f"ALTER TABLE document_chunks "
                        f"ALTER COLUMN embedding TYPE vector({dim}) "
                        f"USING (embedding::text)::vector({dim})"
                    )
                )

            table_exists = conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = current_schema() AND table_name = 'document_chunks'"
                )
            ).fetchone()
            if table_exists is not None:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
                        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
                    )
                )
            return True
    except Exception:
        return False


def init_db(target_engine: Any = None) -> None:
    """Initialize database extensions (pgvector on Postgres if available), tables, and vector indexes."""
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
            pass
    import app.models.entities  # noqa: F401
    Base.metadata.create_all(bind=active_engine)
    if active_engine.dialect.name == "postgresql":
        ensure_pgvector_schema_and_index(active_engine)
