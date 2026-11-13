"""Ensure native pgvector vector(384) column and HNSW cosine index on PostgreSQL.

Revision ID: 0002_pgvector_hnsw
Revises: 0001_initial_schema
Create Date: 2026-11-13

Migration & Data-Integrity Strategy:
1. Checks if the PostgreSQL `vector` (pgvector) extension is installed; if not, attempts
   `CREATE EXTENSION IF NOT EXISTS vector` inside a SAVEPOINT and raises a clear, actionable
   RuntimeError if the database user lacks SUPERUSER / extension creation privileges.
2. When upgrading an existing `document_chunks.embedding` column from `json` / `jsonb` to
   `vector(384)`:
   - Never silently discards valid 384-dimensional float arrays.
   - Inspects all existing rows in `document_chunks` paired with `source_documents.title`.
   - Identifies any rows where `embedding` is NULL, not a JSON array, of wrong dimension
     (`len != 384`), or contains non-finite / non-numeric elements.
   - Logs the exact count and chunk IDs of any invalid/corrupted embeddings and deterministically
     recomputes their 384-dim feature-hash embedding vector from `f"{title}\\n{content}"` (the exact
     same deterministic input used during ingestion) before executing the `ALTER COLUMN ... TYPE vector(384)`
     cast.
3. Creates the `ix_document_chunks_embedding_hnsw` index using `hnsw (embedding vector_cosine_ops)`.
4. On `downgrade()`, drops the HNSW index and restores `document_chunks.embedding` back to `json`
   via `to_json(embedding::real[])` so no vector values are lost.
"""

import json
import logging
import math
from typing import Any, List, Optional, Sequence, Tuple, Union

from alembic import op
import sqlalchemy as sa

from app.core.config import get_settings
from app.modules.processing.service import generate_embedding_vector

logger = logging.getLogger("alembic.runtime.migration")

revision: str = "0002_pgvector_hnsw"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_valid_embedding_vector(raw_val: Any, expected_dim: int) -> Tuple[bool, Optional[str]]:
    """Validate whether a stored JSON/list embedding is a finite numeric vector of length `expected_dim`."""
    if raw_val is None:
        return False, "NULL"

    parsed = raw_val
    if isinstance(raw_val, str):
        stripped = raw_val.strip()
        if not stripped:
            return False, "empty_string"
        try:
            parsed = json.loads(stripped)
        except Exception:
            return False, "malformed_json"

    if not isinstance(parsed, (list, tuple)):
        return False, f"non_array_type:{type(parsed).__name__}"

    if len(parsed) != expected_dim:
        return False, f"wrong_dimension:{len(parsed)}!={expected_dim}"

    for item in parsed:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return False, "non_numeric_element"
        if not math.isfinite(float(item)):
            return False, "non_finite_float"

    return True, None


def _ensure_vector_extension(bind: sa.Connection) -> None:
    """Ensure the pgvector extension is active or raise an actionable error if privileges are insufficient."""
    ext_row = bind.execute(
        sa.text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    ).fetchone()
    if ext_row is not None:
        return

    try:
        with bind.begin_nested():
            bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    except Exception as exc:
        raise RuntimeError(
            "PostgreSQL 'vector' (pgvector) extension is not installed and could not be created "
            "by the current database user. Please ask a database administrator / superuser to run "
            "'CREATE EXTENSION IF NOT EXISTS vector;' on this database before running migrations. "
            f"Underlying database error: {exc}"
        ) from exc

    ext_check = bind.execute(
        sa.text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
    ).fetchone()
    if ext_check is None:
        raise RuntimeError(
            "PostgreSQL 'vector' (pgvector) extension is still missing after CREATE EXTENSION attempt. "
            "Ensure pgvector is installed on the PostgreSQL server and enabled via "
            "'CREATE EXTENSION IF NOT EXISTS vector;'."
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    settings = get_settings()
    dim = int(settings.EMBEDDING_DIMENSION)

    _ensure_vector_extension(bind)

    col_row = bind.execute(
        sa.text(
            "SELECT data_type, udt_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'document_chunks' AND column_name = 'embedding'"
        )
    ).fetchone()

    if col_row is None:
        raise RuntimeError(
            "Column 'document_chunks.embedding' was not found. Ensure migration 0001_initial_schema "
            "has been applied before running 0002_pgvector_hnsw."
        )

    udt_name = str(col_row[1]).lower()
    if udt_name != "vector":
        # Inspect existing rows for NULL, empty, malformed, or wrong-dimension embeddings
        rows = bind.execute(
            sa.text(
                "SELECT dc.id, dc.content, dc.embedding, sd.title "
                "FROM document_chunks dc "
                "LEFT JOIN source_documents sd ON sd.id = dc.source_document_id"
            )
        ).fetchall()

        repaired_rows: List[Tuple[str, str]] = []
        for chunk_id, chunk_content, raw_emb, doc_title in rows:
            is_valid, reason = _is_valid_embedding_vector(raw_emb, dim)
            if not is_valid:
                recomputed = generate_embedding_vector(
                    f"{doc_title or ''}\n{chunk_content or ''}",
                    dimension=dim,
                )
                bind.execute(
                    sa.text(
                        "UPDATE document_chunks SET embedding = CAST(:emb_json AS json) WHERE id = :cid"
                    ),
                    {"emb_json": json.dumps(recomputed), "cid": chunk_id},
                )
                repaired_rows.append((str(chunk_id), str(reason)))

        if repaired_rows:
            logger.warning(
                "Migration 0002_pgvector_hnsw detected and deterministically repaired %d invalid/wrong-dimension "
                "embedding row(s) in document_chunks before vector(%d) conversion: %s",
                len(repaired_rows),
                dim,
                repaired_rows,
            )
        else:
            logger.info(
                "Migration 0002_pgvector_hnsw verified %d existing document_chunks row(s); all embeddings valid.",
                len(rows),
            )

        op.execute(
            f"ALTER TABLE document_chunks "
            f"ALTER COLUMN embedding TYPE vector({dim}) "
            f"USING (embedding::text)::vector({dim})"
        )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw")

    col_row = bind.execute(
        sa.text(
            "SELECT data_type, udt_name FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'document_chunks' AND column_name = 'embedding'"
        )
    ).fetchone()

    if col_row is not None and str(col_row[1]).lower() == "vector":
        op.execute(
            "ALTER TABLE document_chunks "
            "ALTER COLUMN embedding TYPE json "
            "USING to_json(embedding::real[])"
        )
