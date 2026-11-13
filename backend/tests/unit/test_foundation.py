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


def test_migration_0002_embedding_validator_detects_corrupt_and_preserves_valid() -> None:
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

    valid_vec = [0.01] * 384
    ok, reason = mig._is_valid_embedding_vector(valid_vec, 384)
    assert ok is True
    assert reason is None

    for bad_input, expected_prefix in [
        (None, "NULL"),
        ("", "empty_string"),
        ("{not_json", "malformed_json"),
        ({"a": 1}, "non_array_type"),
        ([], "wrong_dimension:0!=384"),
        ([0.1, 0.2], "wrong_dimension:2!=384"),
        (["bad"] * 384, "non_numeric_element"),
        ([True] * 384, "non_numeric_element"),
    ]:
        is_ok, err_reason = mig._is_valid_embedding_vector(bad_input, 384)
        assert is_ok is False
        assert err_reason is not None and err_reason.startswith(expected_prefix)
