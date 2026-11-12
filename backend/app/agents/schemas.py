"""Strict Pydantic schemas and TypedDict state for the LangGraph 3-Agent Orchestrator."""

from typing import Any, Dict, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field, field_validator


#Allowed statuses an AI agent is permitted to output (NEVER "verified")
AIAllowedEvidenceStatus = Literal[
    "source_supported",
    "conflicting",
    "potentially_outdated",
    "inferred",
    "unknown",
]


class ExtractedEvidencePointer(BaseModel):
    source_id: str = Field(..., description="Exact stable_source_id from the retrieved passage")
    location: str = Field(default="body", description="Character offset or section label")
    excerpt: str = Field(..., description="Supporting verbatim or near-verbatim excerpt from the passage")


class CandidateClaimSchema(BaseModel):
    """Output unit produced by Agent 1 (Knowledge Extraction Agent)."""
    claim_code: str
    claim_type: Literal[
        "project_overview",
        "technical_context",
        "key_decision",
        "completed_work",
        "active_work",
        "blocked_work",
        "responsibility",
        "operational_info",
    ]
    text: str
    rationale: Optional[str] = None
    owner_name: Optional[str] = None
    task_status: Optional[str] = None
    due_date: Optional[str] = None
    extraction_confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    evidence: List[ExtractedEvidencePointer] = Field(default_factory=list)
    missing_info_note: Optional[str] = None


class Agent1ExtractionOutput(BaseModel):
    project_summary: str
    candidate_claims: List[CandidateClaimSchema]
    unresolved_questions: List[Dict[str, str]] = Field(default_factory=list)


class ConflictRecordSchema(BaseModel):
    conflict_type: str
    source_a_id: str
    source_a_excerpt: str
    source_a_timestamp: str
    source_b_id: str
    source_b_excerpt: str
    source_b_timestamp: str
    explanation: str


class ClaimVerificationResultSchema(BaseModel):
    """Output unit produced by Agent 2 (Evidence Verification Agent)."""
    claim_code: str
    evidence_status: AIAllowedEvidenceStatus
    uncertainty_flags: List[str] = Field(default_factory=list)
    conflicts: List[ConflictRecordSchema] = Field(default_factory=list)

    @field_validator("evidence_status", mode="before")
    @classmethod
    def forbid_ai_verified_status(cls, v: Any) -> str:
        if str(v).lower() == "verified":
            raise ValueError("AI agents are strictly prohibited from marking a claim as 'verified'.")
        return str(v)


class Agent2VerificationOutput(BaseModel):
    verifications: List[ClaimVerificationResultSchema]


class CandidateRiskDependencySchema(BaseModel):
    """Output unit produced by Agent 3 (Risk & Dependency Analysis Agent)."""
    record_type: Literal["blocker", "risk", "dependency"]
    title: str
    description: str
    severity: Literal["high", "medium", "low"] = "high"
    source_entity: Optional[str] = None
    target_entity: Optional[str] = None
    workaround: Optional[str] = None
    owner_name: Optional[str] = None
    status: AIAllowedEvidenceStatus = "source_supported"
    evidence_source_ids: List[str] = Field(default_factory=list)
    evidence_claim_ids: List[str] = Field(default_factory=list)


class CandidateNextActionSchema(BaseModel):
    priority_rank: int
    priority: Literal["high", "medium", "low"]
    action: str
    reason: str
    owner: Optional[str] = None
    evidence_claim_ids: List[str] = Field(default_factory=list)


class Agent3RiskDependencyOutput(BaseModel):
    risks_and_dependencies: List[CandidateRiskDependencySchema]
    next_actions: List[CandidateNextActionSchema]


class HandoverGraphState(TypedDict, total=False):
    """Typed shared state coordinated by LangGraph."""
    handover_id: str
    handover_code: str
    project_id: str
    project_name: str
    departing_role: str
    allowed_classifications: List[str]
    scoped_source_ids: List[str]
    retrieved_passages: List[Dict[str, Any]]
    # Agent 1 outputs
    project_summary: str
    candidate_claims: List[Dict[str, Any]]
    unresolved_questions: List[Dict[str, str]]
    # Agent 3 outputs
    risks_and_dependencies: List[Dict[str, Any]]
    next_actions: List[Dict[str, Any]]
    # Agent 2 outputs
    verification_map: Dict[str, Dict[str, Any]]
    # Orchestrator control & telemetry
    agent_telemetry: Dict[str, Any]
    errors: List[str]
    halted: bool
    force_failure_agent: Optional[str]
