"""Health-check and system telemetry router."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.api_schemas import HealthCheckResponse

router = APIRouter(tags=["System Health"])


@router.get("/health", response_model=HealthCheckResponse)
def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    settings = get_settings()
    db_connected = False
    pgvector_enabled = False
    dialect = db.bind.dialect.name if db.bind is not None else "unknown"

    try:
        db.execute(text("SELECT 1"))
        db_connected = True
        if dialect == "postgresql":
            ext_row = db.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            ).fetchone()
            pgvector_enabled = ext_row is not None
        else:
            pgvector_enabled = False
    except Exception:
        db_connected = False

    return HealthCheckResponse(
        status="healthy" if db_connected else "degraded",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        database_dialect=dialect,
        database_connected=db_connected,
        pgvector_enabled=pgvector_enabled,
        llm_provider=settings.LLM_PROVIDER,
        llm_model=settings.LLM_MODEL_NAME,
        embedding_provider=settings.EMBEDDING_PROVIDER,
        timestamp=datetime.now(timezone.utc),
    )
