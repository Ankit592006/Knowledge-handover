# Authentication, Authorization & Role Switching (`SEC-01`)

## 1. Authentication Architecture (`backend/app/core/security.py`)
- **Password Hashing**: Argon2id via `argon2-cffi`. Plaintext passwords are never stored or logged.
- **JWT Access Tokens**: Signed with `HS256` (`JWT_SECRET_KEY`), short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES=30`).
- **Rotating Refresh Tokens**: Cryptographically random 48-byte URL-safe tokens; only the `SHA-256` digest is stored in `refresh_tokens`. Re-using a rotated or revoked refresh token immediately returns `401 Unauthorized`.
- **Frontend Token Handling & Centered Auth Modal**: Tokens are managed via `frontend/src/lib/apiClient.ts` and `frontend/src/hooks/useAuth.tsx`. Clicking **Login / Register** opens a centered modal dialog supporting both custom account registration/login and one-click persona switching.

## 2. Genuine 4-Persona Backend Role Switcher (`POST /api/v1/demo/switch-role`)
For seamless multi-role evaluation, the backend provisions 4 dedicated PayFlow user accounts and issues real JWT + refresh tokens when switching roles:
- **`PROJECT_LEAD` (`preeti.lead@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL", "RESTRICTED"]`. Full governance across all 8 PayFlow sources (including `restricted-vendor-note`), source upload, 3-agent reconstruction, claim verification, package approval, Audit Trail inspection, and demo reset to `v1`.
- **`OUTGOING_DEV` (`arjun.outgoing@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL"]`. Accesses Outgoing Studio, uploads sources, runs reconstruction, answers open Clarification Questions, and flags/annotates draft claims. Blocked (`403`) from marking claims `verified` or approving packages.
- **`REVIEWER_SME` (`kavita.reviewer@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL"]`. Accesses Reviewer Console, inspects source evidence, marks claims `verified` or `rejected`, formally approves the handover package, and inspects the Audit Trail.
- **`SUCCESSOR` (`ankit.successor@payflow.demo`)**: Clearance `["PUBLIC", "INTERNAL"]`. Blocked (`403 Forbidden`) from viewing unapproved drafts; post-approval, unlocks the 13-Section Continuation Plan (`PUBLIC` and `INTERNAL` scope), exports Markdown/JSON, and holds **exclusive permission** to acknowledge handover receipt (`POST /api/handovers/{id}/acknowledge`).
- **`GUEST_DEMO` (Anonymous Read-Only Evaluator)**: Unauthenticated requests on permitted PayFlow read endpoints resolve to `GUEST_DEMO` with `["PUBLIC", "INTERNAL"]` clearance and zero write, review, approval, or audit permissions.
