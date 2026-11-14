"""Domain enums for roles, evidence statuses, source classifications, and handover lifecycle."""

from enum import Enum


class PlatformRole(str, Enum):
    ADMIN = "ADMIN"
    STANDARD = "STANDARD"
    GUEST_DEMO = "GUEST_DEMO"


class ProjectRole(str, Enum):
    PROJECT_LEAD = "PROJECT_LEAD"
    OUTGOING_DEV = "OUTGOING_DEV"
    REVIEWER_SME = "REVIEWER_SME"
    SUCCESSOR = "SUCCESSOR"
    GUEST_DEMO = "GUEST_DEMO"


class AccessClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"


class SourceType(str, Enum):
    SYNTHETIC_ISSUE = "synthetic_issue"
    PULL_REQUEST = "pull_request"
    ADR = "adr"
    MEETING_NOTE = "meeting_note"
    TECHNICAL_DOC = "technical_doc"
    UPLOADED_FILE = "uploaded_file"


class HandoverStatus(str, Enum):
    INITIATED = "initiated"
    SOURCES_CONNECTED = "sources_connected"
    RECONSTRUCTING = "reconstructing"
    CLARIFICATION_NEEDED = "clarification_needed"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


class ClaimType(str, Enum):
    PROJECT_OVERVIEW = "project_overview"
    TECHNICAL_CONTEXT = "technical_context"
    KEY_DECISION = "key_decision"
    COMPLETED_WORK = "completed_work"
    ACTIVE_WORK = "active_work"
    BLOCKED_WORK = "blocked_work"
    RESPONSIBILITY = "responsibility"
    OPERATIONAL_INFO = "operational_info"


class EvidenceStatus(str, Enum):
    """Exact 6-status vocabulary from Round 1 Proposal Section 4.4."""
    SOURCE_SUPPORTED = "source_supported"
    VERIFIED = "verified"
    CONFLICTING = "conflicting"
    POTENTIALLY_OUTDATED = "potentially_outdated"
    INFERRED = "inferred"
    UNKNOWN_UNSUPPORTED = "unknown"


class ClaimReviewState(str, Enum):
    PENDING = "pending"
    EDITED = "edited"
    REJECTED = "rejected"
    CLARIFICATION_REQUESTED = "clarification_requested"
    APPROVED = "approved"


class RiskOrDependencyType(str, Enum):
    BLOCKER = "blocker"
    RISK = "risk"
    DEPENDENCY = "dependency"


class PriorityLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ClarificationStatus(str, Enum):
    OPEN = "open"
    ANSWERED = "answered"
    UNKNOWN = "unknown"
