# Authentication & Authorization — Knowledge Handover Platform

## 1. Authentication Architecture (`backend/app/core/security.py`)
- **Password Hashing**: Argon2id via `argon2-cffi`. Plaintext passwords are never stored or logged.
- **JWT Access Tokens**: Signed with `HS256` (`JWT_SECRET_KEY`), short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES=30`).
- **Rotating Refresh Tokens**: Cryptographically random 48-byte URL-safe tokens; only the `SHA-256` digest is stored in `refresh_tokens`. Re-using a rotated or revoked refresh token immediately returns `401 Unauthorized`.
- **Frontend Token Handling**: Stored in memory (`frontend/src/lib/apiClient.ts`), never in plaintext `localStorage`.

## 2. Role & Clearance Matrix
- **`PROJECT_LEAD`**: Full project setup, source import, reconstruction, conflict resolution, `verified` marking, approval, and audit log viewing.
- **`OUTGOING_DEV`**: Source import, reconstruction trigger, draft review, and answering clarification questions. Cannot mark claims `verified` or approve packages.
- **`REVIEWER_SME`**: Evidence inspection, claim editing/rejection, marking claims `verified`, and approving the handover package.
- **`SUCCESSOR`**: Blocked (`403 Forbidden`) from viewing drafts before human approval; post-approval, views only the 13-section Continuation Plan filtered by `allowed_classifications` (`PUBLIC`, `INTERNAL`) and acknowledges receipt.
