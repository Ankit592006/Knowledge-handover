"""Standalone CLI script to initialize the database and seed the PayFlow demonstration workspace."""

from app.core.database import SessionLocal, init_db
from app.models.enums import PlatformRole
from app.modules.auth.service import register_user
from app.modules.handovers.service import (
    create_scoped_handover,
    import_sources_into_handover,
    reconstruct_handover_with_agents,
)
from app.modules.ingestion.service import seed_payflow_sources_for_project
from app.modules.projects.service import create_project
from app.schemas.api_schemas import (
    AccessClassification,
    HandoverCreateRequest,
    HandoverSourceImportRequest,
    ProjectCreateRequest,
    UserRegisterRequest,
)


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        auth_resp = register_user(
            db,
            UserRegisterRequest(
                email="preeti.lead@payflow.demo",
                password="StrongPassword!123",
                full_name="Preeti Satish Mittal (Project Lead)",
                platform_role=PlatformRole.ADMIN,
            ),
        )
        from app.models.entities import User
        lead_user = db.query(User).filter(User.id == auth_resp.user.id).first()
        proj = create_project(
            db,
            ProjectCreateRequest(
                slug="payflow",
                name="PayFlow Payment Gateway & Settlement Service",
                description="Synthetic microservice project for Knowledge Handover evaluation.",
            ),
            lead_user,
        )
        seed_payflow_sources_for_project(db, proj.id, lead_user)
        handover = create_scoped_handover(
            db,
            HandoverCreateRequest(
                project_id=proj.id,
                handover_code="payflow-handover-001",
                title="PayFlow v2.1 Release Transition",
                scope_description="Payment integration, 3DS2 timeout handling, and settlement ledger migrations.",
                allowed_classifications=[AccessClassification.PUBLIC, AccessClassification.INTERNAL],
            ),
            lead_user,
        )
        import_sources_into_handover(
            db,
            handover.handoverId,
            HandoverSourceImportRequest(source_ids=[], seed_payflow_if_empty=True),
            lead_user,
        )
        draft = reconstruct_handover_with_agents(db, handover.handoverId, lead_user)
        print(f"Successfully seeded PayFlow handover '{draft.handoverId}' with {len(draft.claims)} claims.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
