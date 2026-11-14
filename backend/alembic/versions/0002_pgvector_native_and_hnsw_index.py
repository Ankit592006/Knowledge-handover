"""Ensure native pgvector vector(384) column and HNSW cosine index on PostgreSQL.

Revision ID: 0002_pgvector_hnsw
Revises: 0001_initial_schema
Create Date: 2026-11-13

Migration & Data-Integrity Strategy:
1. Checks if the PostgreSQL `vector` (pgvector) extension is installed; if not, attempts
   `CREATE EXTENSION IF NOT EXISTS vector` inside a SAVEPOINT and raises a clear, actionable
   RuntimeError if the database user lacks SUPERUSER / extension creation privileges.
2. Verifies that the `vector` type is visible on the active `search_path` (automatically
   including the extension schema via `SET LOCAL search_path` if installed in a non-default
   schema) and confirms `hnsw` + `vector_cosine_ops` support.
3. Sets a transaction-local `lock_timeout` (`15s`) before table/index DDL to avoid stalling
   production traffic indefinitely behind long-running queries.
4. When upgrading an existing `document_chunks.embedding` column from `json` / `jsonb` to
   `vector(384)`:
   - Never silently discards valid 384-dimensional float arrays.
   - Scans `document_chunks` in bounded keyset batches (`BATCH_SIZE = 500`) fetching only
     `id, embedding` so memory usage remains O(batch_size) rather than loading full table
     content into Python RAM.
   - Detects double-encoded JSON string embeddings (`'"[0.1, ...]"'`) that would otherwise fail
     PostgreSQL `(embedding::text)::vector(384)` casting, unwrapping and preserving their exact
     float values when valid.
   - For genuinely corrupted rows (NULL, malformed JSON, wrong dimension `len != 384`, or
     non-finite / non-numeric elements), fetches `content` and `source_documents.title` only for
     those specific row IDs and deterministically recomputes their 384-dim feature-hash embedding
     from `f"{title}\\n{content}"`.
   - Casts repaired payloads to the exact underlying column type (`json` or `jsonb`) before
     executing `ALTER COLUMN ... TYPE vector(384)`.
5. Creates the `ix_document_chunks_embedding_hnsw` index using `hnsw (embedding vector_cosine_ops)`.
6. On `downgrade()`, drops the HNSW index and restores `document_chunks.embedding` back to `json`
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

BATCH_SIZE: int = 500
LOCK_TIMEOUT: str = "15s"


def _validate_numeric_vector_sequence(seq: Any, expected_dim: int) -> Tuple[bool, Optional[str]]:
    """Validate that a parsed sequence is a list/tuple of finite numbers of length `expected_dim`."""
    if not isinstance(seq, (list, tuple)):
        return False, f"non_array_type:{type(seq).__name__}"

    if len(seq) != expected_dim:
        return False, f"wrong_dimension:{len(seq)}!={expected_dim}"

    for item in seq:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return False, "non_numeric_element"
        if not math.isfinite(float(item)):
            return False, "non_finite_float"

    return True, None


def _is_valid_embedding_vector(raw_val: Any, expected_dim: int) -> Tuple[bool, Optional[str]]:
    """
    Validate whether a stored JSON/JSONB embedding is ready for direct PostgreSQL
    `(embedding::text)::vector(expected_dim)` conversion.

    Note: In psycopg2, a genuine JSON/JSONB array `[0.1, ...]` is decoded to a Python `list`.
    If `raw_val` is a Python `str`, the database column stores a JSON string scalar
    (e.g. `'"[0.1, ...]"'::json`), whose `::text` representation retains outer double quotes and
    would fail `::vector` casting unless repaired first.
    """
    if raw_val is None:
        return False, "NULL"

    if isinstance(raw_val, str):
        stripped = raw_val.strip()
        if not stripped:
            return False, "empty_string"
        try:
            parsed = json.loads(stripped)
        except Exception:
            return False, "malformed_json"

        seq_ok, seq_reason = _validate_numeric_vector_sequence(parsed, expected_dim)
        if not seq_ok:
            return False, seq_reason
        return False, "double_encoded_json_string"

    return _validate_numeric_vector_sequence(raw_val, expected_dim)


def _try_unwrap_double_encoded_vector(raw_val: Any, expected_dim: int) -> Optional[List[float]]:
    """
    If `raw_val` is a single- or multi-encoded JSON string containing a valid `expected_dim`
    finite float vector, unwrap and return the exact float list so valid data is preserved.
    """
    current = raw_val
    for _ in range(3):
        if not isinstance(current, str):
            break
        stripped = current.strip()
        if not stripped:
            return None
        try:
            current = json.loads(stripped)
        except Exception:
            return None

    is_ok, _ = _validate_numeric_vector_sequence(current, expected_dim)
    if is_ok:
        return [float(x) for x in current]
    return None


def _ensure_vector_extension(bind: sa.Connection) -> None:
    """
    Ensure the pgvector extension is active, its `vector` type is visible on `search_path`,
    and the `hnsw` (`vector_cosine_ops`) operator class is available.
    """
    ext_row = bind.execute(
        sa.text(
            "SELECT e.extname, n.nspname "
            "FROM pg_extension e "
            "JOIN pg_namespace n ON n.oid = e.extnamespace "
            "WHERE e.extname = 'vector'"
        )
    ).fetchone()

    if ext_row is None:
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

        ext_row = bind.execute(
            sa.text(
                "SELECT e.extname, n.nspname "
                "FROM pg_extension e "
                "JOIN pg_namespace n ON n.oid = e.extnamespace "
                "WHERE e.extname = 'vector'"
            )
        ).fetchone()
        if ext_row is None:
            raise RuntimeError(
                "PostgreSQL 'vector' (pgvector) extension is still missing after CREATE EXTENSION attempt. "
                "Ensure pgvector is installed on the PostgreSQL server and enabled via "
                "'CREATE EXTENSION IF NOT EXISTS vector;'."
            )

    ext_schema = str(ext_row[1])
    type_check = bind.execute(sa.text("SELECT to_regtype('vector')")).fetchone()
    if type_check is None or type_check[0] is None:
        # Extension is installed in a schema not currently on search_path; append it locally
        quoted_schema = bind.execute(
            sa.text("SELECT quote_ident(:schema_name)"),
            {"schema_name": ext_schema},
        ).scalar()
        current_sp = bind.execute(sa.text("SELECT current_setting('search_path')")).scalar() or "public"
        bind.execute(sa.text(f"SET LOCAL search_path TO {current_sp}, {quoted_schema}"))

        type_check_after = bind.execute(sa.text("SELECT to_regtype('vector')")).fetchone()
        if type_check_after is None or type_check_after[0] is None:
            raise RuntimeError(
                f"PostgreSQL 'vector' extension is installed in schema '{ext_schema}', but type 'vector' "
                f"is not resolvable on search_path ('{current_sp}'). Ensure '{ext_schema}' is on the database "
                "user's search_path."
            )

    opclass_check = bind.execute(
        sa.text(
            "SELECT 1 "
            "FROM pg_opclass opc "
            "JOIN pg_am am ON am.oid = opc.opcmethod "
            "WHERE opc.opcname = 'vector_cosine_ops' AND am.amname = 'hnsw'"
        )
    ).fetchone()
    if opclass_check is None:
        raise RuntimeError(
            "PostgreSQL pgvector extension does not provide the 'vector_cosine_ops' operator class "
            "for the 'hnsw' access method. Please upgrade pgvector to >= 0.5.0."
        )


def _apply_local_lock_timeout(bind: sa.Connection) -> None:
    """Set a transaction-local lock_timeout so DDL fails fast rather than queueing indefinitely."""
    bind.execute(sa.text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    settings = get_settings()
    dim = int(settings.EMBEDDING_DIMENSION)

    _ensure_vector_extension(bind)
    _apply_local_lock_timeout(bind)

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
        cast_target = "jsonb" if udt_name == "jsonb" else "json"
        last_id: Optional[str] = None
        total_inspected = 0
        repaired_rows: List[Tuple[str, str]] = []

        # Keyset-paginated scan fetching only (id, embedding) per batch to bound memory usage
        while True:
            if last_id is None:
                batch_rows = bind.execute(
                    sa.text(
                        "SELECT dc.id, dc.embedding "
                        "FROM document_chunks dc "
                        "ORDER BY dc.id ASC "
                        "LIMIT :batch_size"
                    ),
                    {"batch_size": BATCH_SIZE},
                ).fetchall()
            else:
                batch_rows = bind.execute(
                    sa.text(
                        "SELECT dc.id, dc.embedding "
                        "FROM document_chunks dc "
                        "WHERE dc.id > :last_id "
                        "ORDER BY dc.id ASC "
                        "LIMIT :batch_size"
                    ),
                    {"last_id": last_id, "batch_size": BATCH_SIZE},
                ).fetchall()

            if not batch_rows:
                break

            total_inspected += len(batch_rows)
            last_id = str(batch_rows[-1][0])

            for chunk_id, raw_emb in batch_rows:
                is_valid, reason = _is_valid_embedding_vector(raw_emb, dim)
                if is_valid:
                    continue

                # Preserve exact float values if row is a double-encoded JSON string containing a valid vector
                repaired_vec = _try_unwrap_double_encoded_vector(raw_emb, dim)
                if repaired_vec is None:
                    # Fetch content & source document title ONLY for genuinely corrupted/missing rows
                    meta_row = bind.execute(
                        sa.text(
                            "SELECT dc.content, sd.title "
                            "FROM document_chunks dc "
                            "LEFT JOIN source_documents sd ON sd.id = dc.source_document_id "
                            "WHERE dc.id = :cid"
                        ),
                        {"cid": chunk_id},
                    ).fetchone()
                    chunk_content = meta_row[0] if meta_row is not None else ""
                    doc_title = meta_row[1] if meta_row is not None else ""
                    repaired_vec = generate_embedding_vector(
                        f"{doc_title or ''}\n{chunk_content or ''}",
                        dimension=dim,
                    )

                bind.execute(
                    sa.text(
                        f"UPDATE document_chunks "
                        f"SET embedding = CAST(:emb_json AS {cast_target}) "
                        f"WHERE id = :cid"
                    ),
                    {"emb_json": json.dumps(repaired_vec), "cid": chunk_id},
                )
                repaired_rows.append((str(chunk_id), str(reason)))

            if len(batch_rows) < BATCH_SIZE:
                break

        if repaired_rows:
            logger.warning(
                "Migration 0002_pgvector_hnsw detected and repaired %d invalid/double-encoded "
                "embedding row(s) out of %d in document_chunks (column type '%s') before vector(%d) conversion: %s",
                len(repaired_rows),
                total_inspected,
                udt_name,
                dim,
                repaired_rows,
            )
        else:
            logger.info(
                "Migration 0002_pgvector_hnsw verified %d existing document_chunks row(s) in bounded batches; all embeddings valid.",
                total_inspected,
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

    _apply_local_lock_timeout(bind)

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
