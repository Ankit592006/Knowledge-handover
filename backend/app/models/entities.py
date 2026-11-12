"""SQLAlchemy 2.0 ORM entities for the Knowledge Handover Platform."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings
from app.core.database import Base

settings = get_settings()

try:
    from pgvector.sqlalchemy import Vector as PgVector
except ImportError:
    PgVector = None


class EmbeddingVectorType(TypeDecorator):
    """Cross-dialect vector column: compatible with both PostgreSQL (with or without pgvector) and SQLite."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = 384, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        return dialect.type_descriptor(JSON())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_role: Mapped[str] = mapped_column(String(50), default="STANDARD", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    memberships: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    data_classification: Mapped[str] = mapped_column(String(50), default="synthetic_demo", nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    members: Mapped[List["ProjectMember"]] = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    sources: Mapped[List["SourceDocument"]] = relationship("SourceDocument", back_populates="project", cascade="all, delete-orphan")
    handovers: Mapped[List["Handover"]] = relationship("Handover", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    project_role: Mapped[str] = mapped_column(String(50), nullable=False)
    allowed_classifications: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["PUBLIC", "INTERNAL"], nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("project_id", "stable_source_id", name="uq_project_stable_source_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    stable_source_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    access_level: Mapped[str] = mapped_column(String(50), default="INTERNAL", nullable=False)
    version_tag: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    author_handle: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    redacted_secrets_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    source_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="sources")
    chunks: Mapped[List["DocumentChunk"]] = relationship("DocumentChunk", back_populates="source_document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    stable_source_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    location_label: Mapped[str] = mapped_column(String(120), default="body", nullable=False)
    access_level: Mapped[str] = mapped_column(String(50), default="INTERNAL", nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    embedding: Mapped[List[float]] = mapped_column(EmbeddingVectorType(settings.EMBEDDING_DIMENSION), nullable=False)

    source_document: Mapped["SourceDocument"] = relationship("SourceDocument", back_populates="chunks")


class Handover(Base):
    __tablename__ = "handovers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    handover_code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    departing_role: Mapped[str] = mapped_column(String(120), default="Outgoing Developer", nullable=False)
    outgoing_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    successor_user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    allowed_classifications: Mapped[List[str]] = mapped_column(JSON, default=lambda: ["PUBLIC", "INTERNAL"], nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="initiated", nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    agent_telemetry: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledgement_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="handovers")
    scoped_sources: Mapped[List["HandoverSource"]] = relationship("HandoverSource", back_populates="handover", cascade="all, delete-orphan")
    claims: Mapped[List["Claim"]] = relationship("Claim", back_populates="handover", cascade="all, delete-orphan")
    risks_and_dependencies: Mapped[List["RiskOrDependency"]] = relationship("RiskOrDependency", back_populates="handover", cascade="all, delete-orphan")
    open_questions: Mapped[List["ClarificationQuestion"]] = relationship("ClarificationQuestion", back_populates="handover", cascade="all, delete-orphan")
    next_actions: Mapped[List["NextAction"]] = relationship("NextAction", back_populates="handover", cascade="all, delete-orphan")
    versions: Mapped[List["HandoverVersion"]] = relationship("HandoverVersion", back_populates="handover", cascade="all, delete-orphan")


class HandoverSource(Base):
    __tablename__ = "handover_sources"
    __table_args__ = (UniqueConstraint("handover_id", "source_document_id", name="uq_handover_source_doc"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    handover_id: Mapped[str] = mapped_column(String(36), ForeignKey("handovers.id", ondelete="CASCADE"), index=True, nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    included_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    handover: Mapped["Handover"] = relationship("Handover", back_populates="scoped_sources")
    source_document: Mapped["SourceDocument"] = relationship("SourceDocument")


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    claim_code: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    handover_id: Mapped[str] = mapped_column(String(36), ForeignKey("handovers.id", ondelete="CASCADE"), index=True, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    task_status: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    due_date: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="source_supported", nullable=False)
    review_state: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    extraction_confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    uncertainty_flags: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    conflict_details: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    handover: Mapped["Handover"] = relationship("Handover", back_populates="claims")
    evidence_links: Mapped[List["ClaimEvidenceLink"]] = relationship("ClaimEvidenceLink", back_populates="claim", cascade="all, delete-orphan")


class ClaimEvidenceLink(Base):
    __tablename__ = "claim_evidence_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    claim_id: Mapped[str] = mapped_column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), index=True, nullable=False)
    source_document_id: Mapped[str] = mapped_column(String(36), ForeignKey("source_documents.id", ondelete="CASCADE"), index=True, nullable=False)
    stable_source_id: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str] = mapped_column(String(120), default="body", nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version_tag: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deterministic_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    claim: Mapped["Claim"] = relationship("Claim", back_populates="evidence_links")


class RiskOrDependency(Base):
    __tablename__ = "risks_and_dependencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    handover_id: Mapped[str] = mapped_column(String(36), ForeignKey("handovers.id", ondelete="CASCADE"), index=True, nullable=False)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)  # blocker, risk, dependency
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="high", nullable=False)
    source_entity: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    target_entity: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    workaround: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="source_supported", nullable=False)
    evidence_source_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_claim_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    handover: Mapped["Handover"] = relationship("Handover", back_populates="risks_and_dependencies")


class ClarificationQuestion(Base):
    __tablename__ = "clarification_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    handover_id: Mapped[str] = mapped_column(String(36), ForeignKey("handovers.id", ondelete="CASCADE"), index=True, nullable=False)
    related_claim_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answered_by: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    handover: Mapped["Handover"] = relationship("Handover", back_populates="open_questions")


class NextAction(Base):
    __tablename__ = "next_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    handover_id: Mapped[str] = mapped_column(String(36), ForeignKey("handovers.id", ondelete="CASCADE"), index=True, nullable=False)
    priority_rank: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    priority: Mapped[str] = mapped_column(String(30), default="high", nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    evidence_claim_ids: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)

    handover: Mapped["Handover"] = relationship("Handover", back_populates="next_actions")


class HandoverVersion(Base):
    __tablename__ = "handover_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    handover_id: Mapped[str] = mapped_column(String(36), ForeignKey("handovers.id", ondelete="CASCADE"), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    change_summary: Mapped[str] = mapped_column(String(500), default="Handover version snapshot", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    handover: Mapped["Handover"] = relationship("Handover", back_populates="versions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    handover_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    actor_user_id: Mapped[Optional[str]] = mapped_column(String(36), index=True, nullable=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    target_type: Mapped[str] = mapped_column(String(80), nullable=False)
    target_id: Mapped[str] = mapped_column(String(120), nullable=False)
    previous_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    new_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
