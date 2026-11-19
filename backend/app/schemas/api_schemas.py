"""Pydantic v2 API and domain schemas for Knowledge Handover."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    AccessClassification,
    ClaimReviewState,
    ClaimType,
    ClarificationStatus,
    EvidenceStatus,
    HandoverStatus,
    PlatformRole,
    PriorityLevel,
    ProjectRole,
    RiskOrDependencyType,
    SourceType,
)


# -----------------------------------------------------------------------------
# 1. Health & System Status
# -----------------------------------------------------------------------------
class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    app_name: str
    version: str
    environment: str
    database_dialect: str
    database_connected: bool
    pgvector_enabled: bool
    llm_provider: str
    llm_model: str
    embedding_provider: str
    timestamp: datetime


# -----------------------------------------------------------------------------
# 2. Authentication & User Management
# -----------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    # Public self-registration only permits STANDARD; privileged roles are rejected by register_user
    platform_role: PlatformRole = PlatformRole.STANDARD


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)
    platform_role: PlatformRole = PlatformRole.ADMIN


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class DemoRoleSwitchRequest(BaseModel):
    project_role: ProjectRole


class ProjectMembershipBrief(BaseModel):
    project_id: str
    project_slug: str
    project_name: str
    project_role: ProjectRole
    allowed_classifications: List[str]


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    platform_role: str
    is_active: bool
    created_at: datetime
    memberships: List[ProjectMembershipBrief] = Field(default_factory=list)


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserResponse


# -----------------------------------------------------------------------------
# 3. Project & Member Management
# -----------------------------------------------------------------------------
class ProjectCreateRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=2, max_length=255)
    description: str = ""
    data_classification: str = "synthetic_demo"


class ProjectMemberAssignRequest(BaseModel):
    user_id: str
    project_role: ProjectRole
    allowed_classifications: List[AccessClassification] = Field(
        default_factory=lambda: [AccessClassification.PUBLIC, AccessClassification.INTERNAL]
    )


class ProjectMemberResponse(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    project_role: str
    allowed_classifications: List[str]
    assigned_at: datetime


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    description: str
    data_classification: str
    created_by: str
    created_at: datetime
    member_count: int = 0
    source_count: int = 0
    handover_count: int = 0
    current_user_role: Optional[str] = None
    members: List[ProjectMemberResponse] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 4. Source Ingestion & RAG Chunks
# -----------------------------------------------------------------------------
class SourceUploadRequest(BaseModel):
    stable_source_id: str = Field(..., min_length=2, max_length=120, pattern=r"^[a-zA-Z0-9_-]+$")
    source_type: SourceType
    title: str = Field(..., min_length=2, max_length=500)
    content: str = Field(..., min_length=5, max_length=200000)
    access_level: AccessClassification = AccessClassification.INTERNAL
    version_tag: str = "v1"
    author_handle: Optional[str] = None
    source_updated_at: Optional[datetime] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class SourceChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    stable_source_id: str
    chunk_index: int
    content: str
    char_start: int
    char_end: int
    page_number: int
    location_label: str
    access_level: str
    source_updated_at: datetime


class SourceDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    stable_source_id: str
    source_type: str
    title: str
    content_redacted: str
    access_level: str
    version_tag: str
    author_handle: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    redacted_secrets_count: int
    content_hash: str
    source_created_at: datetime
    source_updated_at: datetime
    ingested_at: datetime
    chunk_count: int = 0
    chunks: List[SourceChunkResponse] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# 5. Handover Output & Round 1 Proposal Schema (Listing 1 Compatible)
# -----------------------------------------------------------------------------
class HandoverCreateRequest(BaseModel):
    project_id: str
    handover_code: Optional[str] = None
    title: str = Field(..., min_length=3, max_length=255)
    scope_description: str = ""
    departing_role: str = "Outgoing Payment Integration Engineer"
    outgoing_user_id: Optional[str] = None
    successor_user_id: Optional[str] = None
    allowed_classifications: List[AccessClassification] = Field(
        default_factory=lambda: [AccessClassification.PUBLIC, AccessClassification.INTERNAL]
    )
    source_ids: List[str] = Field(default_factory=list)


class HandoverSourceImportRequest(BaseModel):
    source_ids: List[str] = Field(default_factory=list, description="List of source_document IDs or stable_source_ids to include in scope")
    seed_payflow_if_empty: bool = True


class EvidenceReferenceSchema(BaseModel):
    sourceId: str
    sourceType: str
    location: str = "body"
    excerpt: str = ""
    charStart: int = 0
    charEnd: int = 0
    versionTag: str = "v1"
    sourceUpdatedAt: datetime
    deterministicVerified: bool = True
    supportStatus: str = "supported"  # supported | weak | mismatch
    supportScore: float = 0.88
    supportExplanation: str = "Excerpt substantiates claim entities and assertion."


class ConflictPairSchema(BaseModel):
    conflictType: str
    sourceAId: str
    sourceAExcerpt: str
    sourceATimestamp: str
    sourceBId: str
    sourceBExcerpt: str
    sourceBTimestamp: str
    explanation: str


class ClaimOutputSchema(BaseModel):
    id: str
    claimId: str
    type: str
    text: str
    rationale: Optional[str] = None
    owner: Optional[str] = None
    taskStatus: Optional[str] = None
    dueDate: Optional[str] = None
    status: str  # source_supported | verified | conflicting | potentially_outdated | inferred | unknown
    evidence: List[EvidenceReferenceSchema] = Field(default_factory=list)
    uncertainty: List[str] = Field(default_factory=list)
    conflicts: List[ConflictPairSchema] = Field(default_factory=list)
    reviewState: str  # pending | edited | rejected | clarification_requested | approved
    extractionConfidence: float = 0.85
    isAiGenerated: bool = True
    reviewerNotes: Optional[str] = None
    reviewedBy: Optional[str] = None
    reviewedAt: Optional[datetime] = None
    citationSupportStatus: str = "supported"  # supported | weak | mismatch
    citationSupportScore: float = 0.88
    reviewerFlaggedMismatch: bool = False


class RiskDependencyOutputSchema(BaseModel):
    id: str
    recordType: str  # blocker | risk | dependency
    title: str
    description: str
    severity: str
    sourceEntity: Optional[str] = None
    targetEntity: Optional[str] = None
    workaround: Optional[str] = None
    owner: Optional[str] = None
    status: str  # source_supported | inferred | unknown | verified
    evidenceSourceIds: List[str] = Field(default_factory=list)
    evidenceClaimIds: List[str] = Field(default_factory=list)


class OpenQuestionOutputSchema(BaseModel):
    id: str
    relatedClaimId: Optional[str] = None
    question: str
    reason: str
    status: str  # open | answered | unknown
    answerText: Optional[str] = None
    answeredBy: Optional[str] = None
    answeredAt: Optional[datetime] = None


class NextActionOutputSchema(BaseModel):
    id: str
    priorityRank: int = 1
    priority: str  # high | medium | low
    action: str
    reason: str = ""
    owner: Optional[str] = None
    evidenceClaimIds: List[str] = Field(default_factory=list)


class ApprovalBlockSchema(BaseModel):
    status: str  # not_approved | approved | acknowledged
    reviewer: Optional[str] = None
    approvedAt: Optional[datetime] = None
    acknowledgedBy: Optional[str] = None
    acknowledgedAt: Optional[datetime] = None
    acknowledgementNotes: Optional[str] = None


class HandoverDraftResponse(BaseModel):
    """Exact superset of Round 1 Proposal Listing 1 (Section 5.2) + 13-section package."""
    id: str
    handoverId: str
    projectId: str
    title: str
    scopeDescription: str
    departingRole: str
    status: str
    currentVersion: int
    project: Dict[str, Any]
    summary: Dict[str, Any]
    claims: List[ClaimOutputSchema]
    risksAndDependencies: List[RiskDependencyOutputSchema] = Field(default_factory=list)
    openQuestions: List[OpenQuestionOutputSchema]
    nextActions: List[NextActionOutputSchema]
    approval: ApprovalBlockSchema
    agentTelemetry: Dict[str, Any] = Field(default_factory=dict)
    scopedSources: List[SourceDocumentResponse] = Field(default_factory=list)


class ClaimPatchRequest(BaseModel):
    text: Optional[str] = None
    rationale: Optional[str] = None
    owner_name: Optional[str] = None
    task_status: Optional[str] = None
    status: Optional[EvidenceStatus] = None
    review_state: Optional[ClaimReviewState] = None
    reviewer_notes: Optional[str] = None
    flag_citation_mismatch: Optional[bool] = None
    citation_support_override: Optional[str] = None  # supported | weak | mismatch


class ClarificationAnswerRequest(BaseModel):
    answer_text: str = Field(..., min_length=2, max_length=5000)
    mark_resolved: bool = True


class HandoverApproveRequest(BaseModel):
    approval_notes: str = "Reviewed and approved for successor sharing."


class SuccessorAcknowledgeRequest(BaseModel):
    acknowledgement_notes: str = "Received and reviewed the continuation plan and open questions."


class SuccessorContinuationPlanResponse(BaseModel):
    """13-section structured continuation package for Workflow E."""
    handoverId: str
    title: str
    version: int
    accessScopeApplied: List[str]
    restrictedSourcesFilteredOut: int
    revokedSourcesFilteredOut: int = 0
    sections: Dict[str, Any]
    claims: List[ClaimOutputSchema]
    risksAndDependencies: List[RiskDependencyOutputSchema]
    openQuestions: List[OpenQuestionOutputSchema]
    nextActions: List[NextActionOutputSchema]
    approval: ApprovalBlockSchema


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: Optional[str] = None
    handover_id: Optional[str] = None
    actor_user_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    target_type: str
    target_id: str
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    created_at: datetime


# -----------------------------------------------------------------------------
# 6. Round 3 Improvement 1: Live GitHub Connector & Retrieval Permission Checks
# -----------------------------------------------------------------------------
class GitHubImportRequest(BaseModel):
    repo_full_name: str = Field(
        default="Ankit592006/Knowledge-handover",
        min_length=3,
        max_length=255,
        description="GitHub repository in 'owner/repo' format",
    )
    include_issues: bool = True
    include_pulls: bool = True
    doc_paths: List[str] = Field(
        default_factory=lambda: ["README.md", "docs/DECISIONS.md"]
    )
    access_level: AccessClassification = AccessClassification.INTERNAL
    github_token: Optional[str] = None
    plant_test_secret_for_verification: bool = False
    max_items_per_category: int = Field(default=3, ge=1, le=10)


class GitHubImportResponse(BaseModel):
    repo_full_name: str
    live_github_fetched: bool
    connector_mode: str
    imported_count: int
    total_redacted_secrets_count: int
    sources: List[SourceDocumentResponse]


class SourceAccessUpdateRequest(BaseModel):
    access_revoked: Optional[bool] = None
    access_level: Optional[AccessClassification] = None
    revocation_reason: str = "Repository permission revoked or elevated at retrieval time."


# -----------------------------------------------------------------------------
# 7. Round 3 Improvement 2: Citation-Support Verification & Evaluation Harness
# -----------------------------------------------------------------------------
class EvaluationMetricsBlock(BaseModel):
    mode: str
    evidenceCoverageRate: float
    citationMismatchDetectionRate: float
    unflaggedMismatchCount: int
    extractionPrecision: float
    extractionRecall: float
    extractionF1: float
    conflictRecall: float
    avgReviewTimeSecondsPerHandover: float


class EvaluationHarnessResponse(BaseModel):
    benchmarkName: str
    evaluatedAt: str
    groundTruthSummary: Dict[str, Any]
    baselineMetrics: EvaluationMetricsBlock
    postImprovementMetrics: EvaluationMetricsBlock
    deltaImprovements: Dict[str, Any]
    caseByCaseResults: List[Dict[str, Any]]


# -----------------------------------------------------------------------------
# 8. Round 3 Improvement 3: Evidence-Backed Dependency Map & Version Comparison
# -----------------------------------------------------------------------------
class DependencyGraphNodeSchema(BaseModel):
    nodeId: str
    label: str
    category: str  # component | team_or_external | task_or_decision | person | unknown_owner_gap
    status: str  # source_supported | inferred | unknown_gap | blocked
    owner: Optional[str] = None
    evidenceSourceIds: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DependencyGraphEdgeSchema(BaseModel):
    edgeId: str
    sourceNodeId: str
    targetNodeId: str
    relationship: str  # BLOCKS | DEPENDS_ON | OWNED_BY | UNASSIGNED_OWNER_GAP | REQUIRES_RUNBOOK | SUPERSEDES
    supportStatus: str  # source_supported | inferred
    severity: str = "high"
    evidenceSourceIds: List[str] = Field(default_factory=list)
    evidenceClaimIds: List[str] = Field(default_factory=list)
    explanation: str = ""


class DependencyMapResponse(BaseModel):
    handoverId: str
    nodes: List[DependencyGraphNodeSchema]
    edges: List[DependencyGraphEdgeSchema]
    summary: Dict[str, Any]


class HandoverVersionBriefSchema(BaseModel):
    versionNumber: int
    changeSummary: str
    createdBy: str
    createdAt: datetime
    claimsCount: int = 0


class ClaimVersionDiffSchema(BaseModel):
    claimCode: str
    claimType: str
    changeTypes: List[str]
    beforeText: Optional[str] = None
    afterText: Optional[str] = None
    beforeRationale: Optional[str] = None
    afterRationale: Optional[str] = None
    beforeStatus: Optional[str] = None
    afterStatus: Optional[str] = None
    beforeReviewState: Optional[str] = None
    afterReviewState: Optional[str] = None
    beforeOwner: Optional[str] = None
    afterOwner: Optional[str] = None
    reviewerNotes: Optional[str] = None
    evidenceSourceIds: List[str] = Field(default_factory=list)


class HandoverVersionDiffResponse(BaseModel):
    handoverId: str
    baseVersion: int
    targetVersion: int
    baseChangeSummary: str
    targetChangeSummary: str
    availableVersions: List[HandoverVersionBriefSchema]
    summaryMetrics: Dict[str, int]
    claimDiffs: List[ClaimVersionDiffSchema]
