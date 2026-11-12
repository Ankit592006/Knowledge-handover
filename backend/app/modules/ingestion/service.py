"""Source Ingestion, Secret Redaction, Chunk Indexing & Permission-Filtered RAG Retrieval (Modules 4, 6, 7)."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_project_membership
from app.models.entities import DocumentChunk, Project, SourceDocument, User
from app.models.enums import ProjectRole
from app.modules.audit.service import record_audit_event
from app.modules.processing.service import (
    compute_content_hash,
    cosine_similarity,
    generate_embedding_vector,
    scan_and_redact_secrets,
    split_document_into_chunks,
)
from app.schemas.api_schemas import (
    SourceChunkResponse,
    SourceDocumentResponse,
    SourceUploadRequest,
)
from app.seeds.payflow_data import PAYFLOW_SYNTHETIC_SOURCES

settings = get_settings()


def format_source_document(doc: SourceDocument, include_chunks: bool = False) -> SourceDocumentResponse:
    chunks_list: List[SourceChunkResponse] = []
    if include_chunks:
        chunks_list = [
            SourceChunkResponse(
                id=c.id,
                stable_source_id=c.stable_source_id,
                chunk_index=c.chunk_index,
                content=c.content,
                char_start=c.char_start,
                char_end=c.char_end,
                page_number=c.page_number,
                location_label=c.location_label,
                access_level=c.access_level,
                source_updated_at=c.source_updated_at,
            )
            for c in sorted(doc.chunks, key=lambda x: x.chunk_index)
        ]

    return SourceDocumentResponse(
        id=doc.id,
        project_id=doc.project_id,
        stable_source_id=doc.stable_source_id,
        source_type=doc.source_type,
        title=doc.title,
        content_redacted=doc.content_redacted,
        access_level=doc.access_level,
        version_tag=doc.version_tag,
        author_handle=doc.author_handle,
        metadata_json=doc.metadata_json or {},
        redacted_secrets_count=doc.redacted_secrets_count,
        content_hash=doc.content_hash,
        source_created_at=doc.source_created_at,
        source_updated_at=doc.source_updated_at,
        ingested_at=doc.ingested_at,
        chunk_count=len(doc.chunks),
        chunks=chunks_list,
    )


def ingest_single_source(
    db: Session,
    project_id: str,
    stable_source_id: str,
    source_type: str,
    title: str,
    raw_content: str,
    access_level: str = "INTERNAL",
    version_tag: str = "v1",
    author_handle: Optional[str] = None,
    source_created_at: Optional[datetime] = None,
    source_updated_at: Optional[datetime] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
    actor: Optional[User] = None,
) -> SourceDocument:
    """Parse, scan/redact secrets, deduplicate, chunk with offsets, embed, and persist a source document."""
    redacted_content, redaction_count = scan_and_redact_secrets(raw_content)
    content_hash = compute_content_hash(redacted_content)
    now = datetime.now(timezone.utc)
    created_ts = source_created_at or now
    updated_ts = source_updated_at or created_ts

    existing = (
        db.query(SourceDocument)
        .filter(
            SourceDocument.project_id == project_id,
            SourceDocument.stable_source_id == stable_source_id,
        )
        .first()
    )

    if existing:
        existing.title = title
        existing.source_type = source_type
        existing.content_redacted = redacted_content
        existing.access_level = access_level
        existing.version_tag = version_tag
        existing.author_handle = author_handle
        existing.metadata_json = metadata_json or {}
        existing.redacted_secrets_count = redaction_count
        existing.content_hash = content_hash
        existing.source_updated_at = updated_ts
        # Rebuild chunks
        db.query(DocumentChunk).filter(DocumentChunk.source_document_id == existing.id).delete()
        doc = existing
    else:
        doc = SourceDocument(
            project_id=project_id,
            stable_source_id=stable_source_id,
            source_type=source_type,
            title=title,
            content_redacted=redacted_content,
            access_level=access_level,
            version_tag=version_tag,
            author_handle=author_handle,
            metadata_json=metadata_json or {},
            redacted_secrets_count=redaction_count,
            content_hash=content_hash,
            source_created_at=created_ts,
            source_updated_at=updated_ts,
        )
        db.add(doc)
        db.flush()

    raw_chunks = split_document_into_chunks(
        redacted_content,
        chunk_size=settings.CHUNK_SIZE_CHARS,
        chunk_overlap=settings.CHUNK_OVERLAP_CHARS,
    )
    for ch in raw_chunks:
        emb = generate_embedding_vector(
            f"{title}\n{ch['content']}",
            dimension=settings.EMBEDDING_DIMENSION,
        )
        chunk_entity = DocumentChunk(
            source_document_id=doc.id,
            project_id=project_id,
            stable_source_id=stable_source_id,
            chunk_index=ch["chunk_index"],
            content=ch["content"],
            char_start=ch["char_start"],
            char_end=ch["char_end"],
            page_number=ch["page_number"],
            location_label=ch["location_label"],
            access_level=access_level,
            source_updated_at=updated_ts,
            embedding=emb,
        )
        db.add(chunk_entity)

    db.flush()

    if redaction_count > 0:
        record_audit_event(
            db=db,
            action="SOURCE_SECRETS_REDACTED",
            target_type="source_document",
            target_id=doc.stable_source_id,
            actor=actor,
            project_id=project_id,
            new_state={"redacted_secrets_count": redaction_count, "access_level": access_level},
        )

    return doc


def seed_payflow_sources_for_project(
    db: Session,
    project_id: str,
    actor: User,
) -> List[SourceDocumentResponse]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    get_project_membership(
        db,
        project_id,
        actor,
        allowed_roles=[ProjectRole.PROJECT_LEAD.value, ProjectRole.OUTGOING_DEV.value],
    )

    ingested_docs: List[SourceDocument] = []
    for item in PAYFLOW_SYNTHETIC_SOURCES:
        doc = ingest_single_source(
            db=db,
            project_id=project_id,
            stable_source_id=item["stable_source_id"],
            source_type=item["source_type"],
            title=item["title"],
            raw_content=item["content"],
            access_level=item["access_level"],
            version_tag=item["version_tag"],
            author_handle=item["author_handle"],
            source_created_at=item["source_created_at"],
            source_updated_at=item["source_updated_at"],
            metadata_json=item["metadata_json"],
            actor=actor,
        )
        ingested_docs.append(doc)

    record_audit_event(
        db=db,
        action="PAYFLOW_SYNTHETIC_SOURCES_SEEDED",
        target_type="project",
        target_id=project_id,
        actor=actor,
        project_id=project_id,
        new_state={"seeded_count": len(ingested_docs)},
    )
    db.commit()
    return [format_source_document(d, include_chunks=False) for d in ingested_docs]


def upload_custom_source(
    db: Session,
    project_id: str,
    req: SourceUploadRequest,
    actor: User,
) -> SourceDocumentResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    membership = get_project_membership(
        db,
        project_id,
        actor,
        allowed_roles=[ProjectRole.PROJECT_LEAD.value, ProjectRole.OUTGOING_DEV.value],
    )
    if req.access_level.value not in membership.allowed_classifications and actor.platform_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You are not authorised to upload sources with classification '{req.access_level.value}'.",
        )

    if len(req.content.encode("utf-8")) > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document exceeds maximum allowed upload size.",
        )

    doc = ingest_single_source(
        db=db,
        project_id=project_id,
        stable_source_id=req.stable_source_id,
        source_type=req.source_type.value,
        title=req.title,
        raw_content=req.content,
        access_level=req.access_level.value,
        version_tag=req.version_tag,
        author_handle=req.author_handle or actor.email,
        source_updated_at=req.source_updated_at,
        metadata_json=req.metadata_json,
        actor=actor,
    )
    record_audit_event(
        db=db,
        action="SOURCE_DOCUMENT_UPLOADED",
        target_type="source_document",
        target_id=doc.stable_source_id,
        actor=actor,
        project_id=project_id,
        new_state={
            "stable_source_id": doc.stable_source_id,
            "source_type": doc.source_type,
            "access_level": doc.access_level,
            "redacted_secrets_count": doc.redacted_secrets_count,
        },
    )
    db.commit()
    db.refresh(doc)
    return format_source_document(doc, include_chunks=True)


def list_project_sources_for_user(
    db: Session,
    project_id: str,
    user: User,
) -> List[SourceDocumentResponse]:
    membership = get_project_membership(db, project_id, user)
    docs = (
        db.query(SourceDocument)
        .filter(
            SourceDocument.project_id == project_id,
            SourceDocument.access_level.in_(membership.allowed_classifications),
        )
        .order_by(SourceDocument.source_updated_at.desc())
        .all()
    )
    return [format_source_document(d, include_chunks=False) for d in docs]


def get_source_detail_for_user(
    db: Session,
    source_id_or_stable_id: str,
    user: User,
    project_id: Optional[str] = None,
) -> SourceDocumentResponse:
    query = db.query(SourceDocument)
    if project_id:
        query = query.filter(SourceDocument.project_id == project_id)
    doc = query.filter(
        (SourceDocument.id == source_id_or_stable_id)
        | (SourceDocument.stable_source_id == source_id_or_stable_id)
    ).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found.")

    membership = get_project_membership(db, doc.project_id, user)
    if doc.access_level not in membership.allowed_classifications and user.platform_role != "ADMIN":
        record_audit_event(
            db=db,
            action="UNAUTHORIZED_SOURCE_ACCESS_BLOCKED",
            target_type="source_document",
            target_id=doc.stable_source_id,
            actor=user,
            project_id=doc.project_id,
            new_state={"required_access_level": doc.access_level},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Source classification exceeds your clearance.",
        )

    return format_source_document(doc, include_chunks=True)


def retrieve_scoped_chunks(
    db: Session,
    project_id: str,
    scoped_source_doc_ids: List[str],
    allowed_classifications: List[str],
    query_text: str,
    top_k: int = 12,
    source_types: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Permission-filtered semantic retrieval (Module 7). Enforces access scope BEFORE retrieval."""
    query = (
        db.query(DocumentChunk, SourceDocument)
        .join(SourceDocument, SourceDocument.id == DocumentChunk.source_document_id)
        .filter(
            DocumentChunk.project_id == project_id,
            DocumentChunk.access_level.in_(allowed_classifications),
        )
    )
    if scoped_source_doc_ids:
        query = query.filter(DocumentChunk.source_document_id.in_(scoped_source_doc_ids))
    if source_types:
        query = query.filter(SourceDocument.source_type.in_(source_types))

    rows = query.all()
    if not rows:
        return []

    query_vec = generate_embedding_vector(query_text, dimension=settings.EMBEDDING_DIMENSION)
    scored: List[Dict[str, Any]] = []
    for chunk, doc in rows:
        emb = list(chunk.embedding) if chunk.embedding is not None else []
        sim = cosine_similarity(query_vec, emb)
        scored.append(
            {
                "chunk_id": chunk.id,
                "source_document_id": doc.id,
                "stable_source_id": doc.stable_source_id,
                "source_type": doc.source_type,
                "title": doc.title,
                "version_tag": doc.version_tag,
                "access_level": doc.access_level,
                "location_label": chunk.location_label,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "source_updated_at": doc.source_updated_at.isoformat(),
                "metadata_json": doc.metadata_json or {},
                "similarity": round(sim, 4),
            }
        )

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]
