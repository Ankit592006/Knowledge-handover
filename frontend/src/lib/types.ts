/**
 * Core TypeScript contracts matching FastAPI Pydantic v2 schemas and Round 1 Proposal Listing 1.
 */

export type EvidenceStatus =
  | "source_supported"
  | "verified"
  | "conflicting"
  | "potentially_outdated"
  | "inferred"
  | "unknown";

export type ClaimReviewState =
  | "pending"
  | "edited"
  | "rejected"
  | "clarification_requested"
  | "approved";

export type ProjectRole =
  | "PROJECT_LEAD"
  | "OUTGOING_DEV"
  | "REVIEWER_SME"
  | "SUCCESSOR"
  | "GUEST_DEMO";

export type AccessClassification = "PUBLIC" | "INTERNAL" | "RESTRICTED";

export interface ProjectMembershipBrief {
  project_id: string;
  project_slug: string;
  project_name: string;
  project_role: ProjectRole;
  allowed_classifications: AccessClassification[];
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  platform_role: string;
  is_active: boolean;
  created_at: string;
  memberships: ProjectMembershipBrief[];
}

export interface EvidenceReference {
  sourceId: string;
  sourceType: string;
  location: string;
  excerpt: string;
  charStart: number;
  charEnd: number;
  versionTag: string;
  sourceUpdatedAt: string;
  deterministicVerified: boolean;
}

export interface ConflictPair {
  conflictType: string;
  sourceAId: string;
  sourceAExcerpt: string;
  sourceATimestamp: string;
  sourceBId: string;
  sourceBExcerpt: string;
  sourceBTimestamp: string;
  explanation: string;
}

export interface HandoverClaim {
  id: string;
  claimId: string;
  type: string;
  text: string;
  rationale?: string | null;
  owner?: string | null;
  taskStatus?: string | null;
  dueDate?: string | null;
  status: EvidenceStatus;
  evidence: EvidenceReference[];
  uncertainty: string[];
  conflicts: ConflictPair[];
  reviewState: ClaimReviewState;
  extractionConfidence: number;
  isAiGenerated: boolean;
  reviewerNotes?: string | null;
  reviewedBy?: string | null;
  reviewedAt?: string | null;
}

export interface RiskOrDependencyItem {
  id: string;
  recordType: "blocker" | "risk" | "dependency";
  title: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low";
  sourceEntity?: string | null;
  targetEntity?: string | null;
  workaround?: string | null;
  owner?: string | null;
  status: EvidenceStatus;
  evidenceSourceIds: string[];
  evidenceClaimIds: string[];
}

export interface OpenQuestionItem {
  id: string;
  relatedClaimId?: string | null;
  question: string;
  reason: string;
  status: "open" | "answered" | "unknown";
  answerText?: string | null;
  answeredBy?: string | null;
  answeredAt?: string | null;
}

export interface NextActionItem {
  id: string;
  priorityRank: number;
  priority: "high" | "medium" | "low";
  action: string;
  reason: string;
  owner?: string | null;
  evidenceClaimIds: string[];
}

export interface ApprovalBlock {
  status: "not_approved" | "approved" | "acknowledged";
  reviewer?: string | null;
  approvedAt?: string | null;
  acknowledgedBy?: string | null;
  acknowledgedAt?: string | null;
  acknowledgementNotes?: string | null;
}

export interface SourceDocumentItem {
  id: string;
  project_id: string;
  stable_source_id: string;
  source_type: string;
  title: string;
  content_redacted: string;
  access_level: string;
  version_tag: string;
  author_handle?: string | null;
  redacted_secrets_count: number;
  source_updated_at: string;
  chunk_count: number;
}

export interface HandoverPackage {
  id: string;
  handoverId: string;
  projectId: string;
  title: string;
  scopeDescription: string;
  departingRole: string;
  status: string;
  currentVersion: number;
  project: Record<string, unknown>;
  summary: Record<string, unknown>;
  claims: HandoverClaim[];
  risksAndDependencies: RiskOrDependencyItem[];
  openQuestions: OpenQuestionItem[];
  nextActions: NextActionItem[];
  approval: ApprovalBlock;
  agentTelemetry: Record<string, unknown>;
  scopedSources: SourceDocumentItem[];
}

export type ClaimItem = HandoverClaim;
export type HandoverDraft = HandoverPackage;

export interface SuccessorContinuationPlan {
  handoverId: string;
  title: string;
  version: number;
  accessScopeApplied: string[];
  restrictedSourcesFilteredOut: number;
  sections: Record<string, unknown>;
  claims: HandoverClaim[];
  risksAndDependencies: RiskOrDependencyItem[];
  openQuestions: OpenQuestionItem[];
  nextActions: NextActionItem[];
  approval: ApprovalBlock;
}

export interface AuditLogItem {
  id: string;
  project_id?: string | null;
  handover_id?: string | null;
  actor_user_id?: string | null;
  actor_email?: string | null;
  actor_role?: string | null;
  action: string;
  target_type: string;
  target_id: string;
  previous_state?: Record<string, unknown> | null;
  new_state?: Record<string, unknown> | null;
  created_at: string;
}
