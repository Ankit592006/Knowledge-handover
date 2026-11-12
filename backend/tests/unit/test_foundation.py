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
        assert body["pgvector_enabled"] is True
        assert body["app_name"] == "Knowledge Handover Platform"

        # Check security headers
        assert resp_v1.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp_v1.headers.get("X-Frame-Options") == "DENY"

        # Check /api/health alias
        resp_alias = client.get("/api/health")
        assert resp_alias.status_code == 200
        assert resp_alias.json()["status"] == "healthy"
