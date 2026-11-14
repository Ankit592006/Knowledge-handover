"""Phase 1 Foundation Tests: Database initialization, ORM models, security headers, and health check."""

from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.core.database import Base, engine, init_db
from app.main import app


def test_database_tables_created() -> None:
    init_db()
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    expected_tables = {
        "users",
        "refresh_tokens",
        "projects",
        "project_members",
        "source_documents",
        "document_chunks",
        "handovers",
        "handover_sources",
        "claims",
        "claim_evidence_links",
        "risks_and_dependencies",
        "clarification_questions",
        "next_actions",
        "handover_versions",
        "audit_logs",
    }
    assert expected_tables.issubset(existing_tables)


def test_health_check_v1_and_alias_and_security_headers() -> None:
    with TestClient(app) as client:
        resp_v1 = client.get("/api/v1/health")
        assert resp_v1.status_code == 200
        body = resp_v1.json()
        assert body["status"] == "healthy"
        assert body["database_connected"] is True
        if body["database_dialect"] == "postgresql":
            assert body["pgvector_enabled"] is True
        else:
            assert body["pgvector_enabled"] is False
        assert body["app_name"] == "Knowledge Handover Platform"

        # Check security headers
        assert resp_v1.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp_v1.headers.get("X-Frame-Options") == "DENY"

        # Check /api/health alias
        resp_alias = client.get("/api/health")
        assert resp_alias.status_code == 200
        assert resp_alias.json()["status"] == "healthy"


def test_embedding_vector_type_compiles_native_pgvector_on_postgres_and_json_on_sqlite() -> None:
    from sqlalchemy.dialects import postgresql, sqlite
    from sqlalchemy.schema import CreateTable
    from app.models.entities import DocumentChunk

    pg_ddl = str(CreateTable(DocumentChunk.__table__).compile(dialect=postgresql.dialect()))
    sqlite_ddl = str(CreateTable(DocumentChunk.__table__).compile(dialect=sqlite.dialect()))

    assert "VECTOR(384)" in pg_ddl.upper()
    assert "JSON" in sqlite_ddl.upper()

    distance_expr = DocumentChunk.embedding.cosine_distance([0.0] * 384)
    compiled_distance = str(distance_expr.compile(dialect=postgresql.dialect()))
    assert "<=>" in compiled_distance


def _load_migration_0002_module():
    import importlib.util
    from pathlib import Path

    mig_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0002_pgvector_native_and_hnsw_index.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0002", mig_path)
    assert spec is not None and spec.loader is not None
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    return mig


def test_migration_0002_embedding_validator_detects_corrupt_double_encoded_and_preserves_valid() -> None:
    import json

    mig = _load_migration_0002_module()

    valid_vec = [0.01] * 384
    ok, reason = mig._is_valid_embedding_vector(valid_vec, 384)
    assert ok is True
    assert reason is None

    # Double-encoded JSON strings must be flagged for repair AND unwrapped without losing float values
    double_encoded = json.dumps([0.25] * 384)
    is_ok_de, reason_de = mig._is_valid_embedding_vector(double_encoded, 384)
    assert is_ok_de is False
    assert reason_de == "double_encoded_json_string"
    unwrapped = mig._try_unwrap_double_encoded_vector(double_encoded, 384)
    assert unwrapped == [0.25] * 384

    nested_double_encoded = json.dumps(json.dumps([0.5] * 384))
    assert mig._try_unwrap_double_encoded_vector(nested_double_encoded, 384) == [0.5] * 384

    for bad_input, expected_prefix in [
        (None, "NULL"),
        ("", "empty_string"),
        ("{not_json", "malformed_json"),
        ({"a": 1}, "non_array_type"),
        ([], "wrong_dimension:0!=384"),
        ([0.1, 0.2], "wrong_dimension:2!=384"),
        (json.dumps([0.1, 0.2]), "wrong_dimension:2!=384"),
        (["bad"] * 384, "non_numeric_element"),
        ([True] * 384, "non_numeric_element"),
        ([float("nan")] * 384, "non_finite_float"),
        ([float("inf")] * 384, "non_finite_float"),
    ]:
        is_ok, err_reason = mig._is_valid_embedding_vector(bad_input, 384)
        assert is_ok is False
        assert err_reason is not None and err_reason.startswith(expected_prefix)
        assert mig._try_unwrap_double_encoded_vector(bad_input, 384) is None


def test_migration_0002_json_jsonb_bounded_batches_and_rollback() -> None:
    """
    Verifies migration 0002 production fixes:
    1. Handles both JSON and JSONB column types with proper CAST(:emb_json AS json/jsonb).
    2. Detects and repairs double-encoded JSON strings by unwrapping and preserving exact float values.
    3. Uses bounded keyset batching (BATCH_SIZE=2) and fetches content/title ONLY for genuinely corrupted rows.
    4. Applies SET LOCAL lock_timeout and verifies pgvector schema visibility + HNSW vector_cosine_ops.
    5. Supports clean downgrade() back to JSON and re-upgrade() to vector(384) without data loss.
    """
    import json
    import uuid
    from unittest.mock import patch
    import sqlalchemy as sa
    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from app.modules.processing.service import generate_embedding_vector

    mig = _load_migration_0002_module()
    mig.BATCH_SIZE = 2

    # Part A: Deterministic harness verifying bounded batch queries, lazy metadata fetch count, and JSON vs JSONB casts
    for simulated_udt in ("json", "jsonb"):
        dataset = [
            ("chunk-001", [0.125] * 384, "Body 1", "Title 1"),
            ("chunk-002", json.dumps([0.375] * 384), "Body 2", "Title 2"),  # double-encoded valid string
            ("chunk-003", [0.5] * 384, "Body 3", "Title 3"),
            ("chunk-004", [0.9, 0.8], "Corrupted Body 4", "Corrupted Title 4"),  # wrong dimension
            ("chunk-005", None, "Null Body 5", "Null Title 5"),  # NULL embedding
        ]
        repaired_updates = {}
        batch_queries_executed = 0
        metadata_queries_executed = 0
        lock_timeout_applied = False
        ddl_statements = []

        class _FakeResult:
            def __init__(self, rows=None, scalar_val=None):
                self._rows = rows or []
                self._scalar = scalar_val

            def fetchone(self):
                return self._rows[0] if self._rows else None

            def fetchall(self):
                return list(self._rows)

            def scalar(self):
                return self._scalar

        class _FakeDialect:
            name = "postgresql"

        class _FakeConn:
            dialect = _FakeDialect()

            def execute(self, stmt, params=None):
                nonlocal batch_queries_executed, metadata_queries_executed, lock_timeout_applied
                sql = str(stmt)
                params = params or {}

                if "FROM pg_extension" in sql:
                    return _FakeResult(rows=[("vector", "public")])
                if "SELECT to_regtype('vector')" in sql:
                    return _FakeResult(rows=[("vector",)])
                if "FROM pg_opclass" in sql:
                    return _FakeResult(rows=[(1,)])
                if "SET LOCAL lock_timeout" in sql:
                    lock_timeout_applied = True
                    return _FakeResult()
                if "FROM information_schema.columns" in sql:
                    return _FakeResult(rows=[(simulated_udt, simulated_udt)])
                if "SELECT dc.id, dc.embedding FROM document_chunks dc" in sql:
                    batch_queries_executed += 1
                    limit = params["batch_size"]
                    last_id = params.get("last_id")
                    filtered = [
                        (cid, emb)
                        for cid, emb, _, _ in dataset
                        if last_id is None or cid > last_id
                    ]
                    return _FakeResult(rows=filtered[:limit])
                if "SELECT dc.content, sd.title" in sql:
                    metadata_queries_executed += 1
                    target_id = params["cid"]
                    for cid, _, body, title in dataset:
                        if cid == target_id:
                            return _FakeResult(rows=[(body, title)])
                    return _FakeResult()
                if "UPDATE document_chunks SET embedding =" in sql:
                    assert f"CAST(:emb_json AS {simulated_udt})" in sql
                    repaired_updates[params["cid"]] = json.loads(params["emb_json"])
                    return _FakeResult()
                return _FakeResult()

        fake_conn = _FakeConn()
        with patch.object(mig.op, "get_bind", return_value=fake_conn), patch.object(
            mig.op, "execute", side_effect=lambda sql: ddl_statements.append(str(sql))
        ):
            mig.upgrade()

        assert lock_timeout_applied is True
        # 5 rows with BATCH_SIZE=2 -> 3 batch queries (2 rows, 2 rows, 1 row)
        assert batch_queries_executed == 3
        # Metadata (content/title) must ONLY be fetched for the 2 genuinely corrupted rows (chunk-004, chunk-005),
        # NOT for valid rows (chunk-001, chunk-003) and NOT for double-encoded valid string (chunk-002)!
        assert metadata_queries_executed == 2
        assert set(repaired_updates.keys()) == {"chunk-002", "chunk-004", "chunk-005"}
        assert repaired_updates["chunk-002"] == [0.375] * 384
        assert repaired_updates["chunk-004"] == generate_embedding_vector(
            "Corrupted Title 4\nCorrupted Body 4", dimension=384
        )
        assert repaired_updates["chunk-005"] == generate_embedding_vector(
            "Null Title 5\nNull Body 5", dimension=384
        )
        assert any("ALTER COLUMN embedding TYPE vector(384)" in s for s in ddl_statements)
        assert any("USING hnsw (embedding vector_cosine_ops)" in s for s in ddl_statements)

    # Part B: When running against live PostgreSQL, execute real DDL transitions for JSON, JSONB, and rollback
    if engine.dialect.name == "postgresql":
        init_db()
        engine.dispose()

        uid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        sid = str(uuid.uuid4())
        c_valid = f"0002-pg-a-{uuid.uuid4().hex[:8]}"
        c_double = f"0002-pg-b-{uuid.uuid4().hex[:8]}"
        c_corrupt = f"0002-pg-c-{uuid.uuid4().hex[:8]}"
        c_null = f"0002-pg-d-{uuid.uuid4().hex[:8]}"
        chunk_ids = [c_valid, c_double, c_corrupt, c_null]

        try:
            # 1. Seed isolated test user, project, source_document, and 4 chunks in a dedicated transaction
            with engine.begin() as conn:
                conn.execute(
                    sa.text(
                        "INSERT INTO users (id, email, password_hash, full_name, platform_role, is_active, created_at) "
                        "VALUES (:id, :email, 'hash', 'Mig Test User', 'STANDARD', true, CURRENT_TIMESTAMP)"
                    ),
                    {"id": uid, "email": f"mig0002_{uid[:8]}@payflow.demo"},
                )
                conn.execute(
                    sa.text(
                        "INSERT INTO projects (id, slug, name, description, data_classification, created_by, created_at) "
                        "VALUES (:id, :slug, 'Mig Test Proj', '', 'synthetic_demo', :uid, CURRENT_TIMESTAMP)"
                    ),
                    {"id": pid, "slug": f"mig0002-{pid[:8]}", "uid": uid},
                )
                conn.execute(
                    sa.text(
                        "INSERT INTO source_documents (id, project_id, stable_source_id, source_type, title, "
                        "content_redacted, access_level, version_tag, metadata_json, redacted_secrets_count, "
                        "content_hash, source_created_at, source_updated_at, ingested_at) "
                        "VALUES (:id, :pid, 'mig-doc-1', 'technical_doc', 'PgVector Mig Title', 'Body', "
                        "'INTERNAL', 'v1', '{}'::json, 0, 'hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {"id": sid, "pid": pid},
                )

                default_vec_str = "[" + ",".join(["0.125"] * 384) + "]"
                for idx, cid in enumerate(chunk_ids):
                    conn.execute(
                        sa.text(
                            "INSERT INTO document_chunks (id, source_document_id, project_id, stable_source_id, "
                            "chunk_index, content, char_start, char_end, page_number, location_label, access_level, "
                            "source_updated_at, embedding) "
                            "VALUES (:id, :sid, :pid, 'mig-doc-1', :idx, :content, 0, 10, 1, 'body', 'INTERNAL', "
                            "CURRENT_TIMESTAMP, CAST(:vec AS vector(384)))"
                        ),
                        {
                            "id": cid,
                            "sid": sid,
                            "pid": pid,
                            "idx": idx,
                            "content": f"Chunk body {idx}",
                            "vec": default_vec_str,
                        },
                    )

            # Dispose pooled connections before ALTER TABLE in downgrade()
            engine.dispose()
            with engine.begin() as conn:
                ctx = MigrationContext.configure(conn)
                op_proxy = Operations(ctx)
                with patch.object(mig, "op", op_proxy):
                    mig.downgrade()

                col_type_after_down = conn.execute(
                    sa.text(
                        "SELECT udt_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = 'document_chunks' AND column_name = 'embedding'"
                    )
                ).scalar()
                assert col_type_after_down == "json"

            # Inject double-encoded JSON string, wrong-dimension JSON array, and JSON null into the JSON column
            with engine.begin() as conn:
                conn.execute(
                    sa.text("UPDATE document_chunks SET embedding = CAST(:val AS json) WHERE id = :cid"),
                    {"val": json.dumps(json.dumps([0.375] * 384)), "cid": c_double},
                )
                conn.execute(
                    sa.text("UPDATE document_chunks SET embedding = '[0.9, 0.8]'::json WHERE id = :cid"),
                    {"cid": c_corrupt},
                )
                conn.execute(
                    sa.text("UPDATE document_chunks SET embedding = 'null'::json WHERE id = :cid"),
                    {"cid": c_null},
                )

            # 2. Test upgrade() from json -> vector(384) after disposing pooled connections
            engine.dispose()
            with engine.begin() as conn:
                ctx = MigrationContext.configure(conn)
                op_proxy = Operations(ctx)
                with patch.object(mig, "op", op_proxy):
                    mig.upgrade()

                col_type_after_up = conn.execute(
                    sa.text(
                        "SELECT udt_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = 'document_chunks' AND column_name = 'embedding'"
                    )
                ).scalar()
                assert col_type_after_up == "vector"

                double_restored = conn.execute(
                    sa.text("SELECT (embedding::real[])[1] FROM document_chunks WHERE id = :cid"),
                    {"cid": c_double},
                ).scalar()
                assert abs(float(double_restored) - 0.375) < 1e-6

            # 3. Convert column to JSONB to test JSONB -> vector(384) upgrade path
            engine.dispose()
            with engine.begin() as conn:
                conn.execute(sa.text("SET LOCAL lock_timeout = '15s'"))
                conn.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw"))
                conn.execute(
                    sa.text(
                        "ALTER TABLE document_chunks "
                        "ALTER COLUMN embedding TYPE jsonb "
                        "USING to_jsonb(embedding::real[])"
                    )
                )

            with engine.begin() as conn:
                conn.execute(
                    sa.text("UPDATE document_chunks SET embedding = CAST(:val AS jsonb) WHERE id = :cid"),
                    {"val": json.dumps(json.dumps([0.625] * 384)), "cid": c_double},
                )
                conn.execute(
                    sa.text("UPDATE document_chunks SET embedding = '[1.0, 2.0]'::jsonb WHERE id = :cid"),
                    {"cid": c_corrupt},
                )

            engine.dispose()
            with engine.begin() as conn:
                ctx = MigrationContext.configure(conn)
                op_proxy = Operations(ctx)
                with patch.object(mig, "op", op_proxy):
                    mig.upgrade()

                col_type_from_jsonb = conn.execute(
                    sa.text(
                        "SELECT udt_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() "
                        "AND table_name = 'document_chunks' AND column_name = 'embedding'"
                    )
                ).scalar()
                assert col_type_from_jsonb == "vector"

                jsonb_double_restored = conn.execute(
                    sa.text("SELECT (embedding::real[])[1] FROM document_chunks WHERE id = :cid"),
                    {"cid": c_double},
                ).scalar()
                assert abs(float(jsonb_double_restored) - 0.625) < 1e-6

                hnsw_exists = conn.execute(
                    sa.text(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = current_schema() "
                        "AND tablename = 'document_chunks' "
                        "AND indexname = 'ix_document_chunks_embedding_hnsw'"
                    )
                ).scalar()
                assert hnsw_exists == "ix_document_chunks_embedding_hnsw"
        finally:
            engine.dispose()
            with engine.begin() as cleanup_conn:
                cleanup_conn.execute(sa.text("DELETE FROM projects WHERE id = :pid"), {"pid": pid})
                cleanup_conn.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": uid})
                # Guarantee schema is left on vector(384) + HNSW index even if an assertion failed mid-test
                ctx = MigrationContext.configure(cleanup_conn)
                op_proxy = Operations(ctx)
                with patch.object(mig, "op", op_proxy):
                    mig.upgrade()
            engine.dispose()


def test_production_cors_and_render_predeploy_migration_config() -> None:
    """
    Verifies:
    1. Wildcard CORS_ORIGINS ('*') is rejected in production configuration.
    2. Production backend allows only 'https://kh-frontend.onrender.com' and excludes localhost dev origins.
    3. Local development preserves localhost origins in development configuration only.
    4. render.yaml configures CORS_ORIGINS='https://kh-frontend.onrender.com' and runs 'alembic upgrade head'
       during the deployment build step (before startCommand), while ordinary application startup (init_db)
       does not run automatic column alterations.
    """
    from pathlib import Path
    import pytest
    import yaml
    from app.core.config import Settings
    import app.core.database as db_module

    # 1. Local development default origins
    dev_settings = Settings(APP_ENV="development")
    assert "http://localhost:5173" in dev_settings.cors_origin_list
    assert "*" not in dev_settings.cors_origin_list

    # 2. Production rejects wildcard '*'
    prod_wildcard = Settings(APP_ENV="production", CORS_ORIGINS="*")
    with pytest.raises(ValueError, match="Wildcard CORS_ORIGINS"):
        _ = prod_wildcard.cors_origin_list

    # 3. Production strips localhost and allows only https://kh-frontend.onrender.com
    prod_default = Settings(APP_ENV="production")
    assert prod_default.cors_origin_list == ["https://kh-frontend.onrender.com"]

    prod_mixed = Settings(
        APP_ENV="production",
        CORS_ORIGINS="https://kh-frontend.onrender.com,http://localhost:5173,http://127.0.0.1:5173",
    )
    assert prod_mixed.cors_origin_list == ["https://kh-frontend.onrender.com"]

    # 4. Verify render.yaml configuration
    render_path = Path(__file__).resolve().parents[3] / "render.yaml"
    render_cfg = yaml.safe_load(render_path.read_text(encoding="utf-8"))

    assert [d["name"] for d in render_cfg["databases"]] == ["kh-postgres"]
    services_by_name = {s["name"]: s for s in render_cfg["services"]}
    assert set(services_by_name.keys()) == {"kh-backend", "kh-frontend"}

    backend_svc = services_by_name["kh-backend"]
    assert backend_svc["rootDir"] == "backend"
    assert "alembic upgrade head" in backend_svc["buildCommand"]
    assert "alembic" not in backend_svc["startCommand"]

    backend_env = {e["key"]: e.get("value") for e in backend_svc["envVars"]}
    assert backend_env["CORS_ORIGINS"] == "https://kh-frontend.onrender.com"
    assert backend_env["CORS_ORIGINS"] != "*"

    # 5. Verify ordinary application startup (init_db) does not run automatic schema migrations
    assert not hasattr(db_module, "ensure_pgvector_schema_and_index")
