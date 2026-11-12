"""Append-only audit logging service (Module 15)."""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.entities import AuditLog, User


def record_audit_event(
    db: Session,
    action: str,
    target_type: str,
    target_id: str,
    actor: Optional[User] = None,
    actor_role: Optional[str] = None,
    project_id: Optional[str] = None,
    handover_id: Optional[str] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    new_state: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Append an immutable audit record to audit_logs."""
    entry = AuditLog(
        project_id=project_id,
        handover_id=handover_id,
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        actor_role=actor_role or (actor.platform_role if actor else "ANONYMOUS"),
        action=action,
        target_type=target_type,
        target_id=target_id,
        previous_state=previous_state,
        new_state=new_state,
    )
    db.add(entry)
    db.flush()
    return entry


def list_audit_events(
    db: Session,
    project_id: Optional[str] = None,
    handover_id: Optional[str] = None,
    limit: int = 100,
) -> List[AuditLog]:
    query = db.query(AuditLog)
    if project_id:
        query = query.filter(AuditLog.project_id == project_id)
    if handover_id:
        query = query.filter(AuditLog.handover_id == handover_id)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
