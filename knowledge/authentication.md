# Authentication & Authorization Spec

**Last updated:** 2025-12-02  
**Owner:** Security Team  
**Status:** Current

## Overview

Acme Platform uses JWT-based authentication with short-lived access tokens and long-lived refresh tokens. Authorization is role-based (RBAC) with tenant-scoped permissions.

## Authentication Flow

### Login

1. Client sends `POST /auth/login` with email + password to `core-api`
2. `core-api` verifies credentials against bcrypt-hashed passwords in PostgreSQL
3. On success, returns:
   - `access_token` — JWT, 15-minute expiry, signed with RS256
   - `refresh_token` — opaque token, 30-day expiry, stored in Redis
4. Access token contains claims: `sub` (user ID), `tid` (tenant ID), `role`, `exp`, `iat`

### Token Refresh

1. Client sends `POST /auth/refresh` with the refresh token
2. `core-api` validates the refresh token exists in Redis and hasn't been revoked
3. Returns a new access token (and rotates the refresh token)
4. Old refresh token is immediately invalidated (rotation prevents replay)

### Token Validation (Gateway)

The `gateway` service validates every incoming request:

1. Extract `Authorization: Bearer <token>` header
2. Verify JWT signature using the public key (RS256)
3. Check `exp` claim — reject if expired
4. Extract `tid` (tenant ID) and inject as `X-Tenant-ID` header
5. Extract `role` and inject as `X-User-Role` header
6. Forward to downstream service

Downstream services **never** validate JWTs themselves — they trust the gateway headers.

## Authorization (RBAC)

### Roles

| Role | Description | Scope |
| ---- | ----------- | ----- |
| `owner` | Full access, can manage billing and delete tenant | Tenant-wide |
| `admin` | Full access except billing and tenant deletion | Tenant-wide |
| `manager` | Can manage team members and all workflows | Team-scoped |
| `member` | Can create/edit own workflows, view team workflows | Self + team read |
| `viewer` | Read-only access to assigned workflows | Explicit assignment |

### Permission Matrix

| Action | owner | admin | manager | member | viewer |
| ------ | ----- | ----- | ------- | ------ | ------ |
| Create workflow | yes | yes | yes | yes | no |
| Edit own workflow | yes | yes | yes | yes | no |
| Edit any workflow | yes | yes | yes | no | no |
| Delete workflow | yes | yes | yes (team) | own only | no |
| View all workflows | yes | yes | yes (team) | team read | assigned |
| Manage team members | yes | yes | yes | no | no |
| Manage billing | yes | no | no | no | no |
| API key management | yes | yes | no | no | no |
| View audit logs | yes | yes | yes | no | no |

### API Key Authentication

For machine-to-machine integrations, tenants can create API keys:

- API keys are prefixed with `acme_` followed by 48 random bytes (base62 encoded)
- Keys are hashed with SHA-256 before storage — the plaintext is shown once at creation
- Each key has a `role` (same RBAC roles as users) and an optional expiry date
- API keys are validated by the `gateway` the same way as JWTs, but looked up in Redis instead of signature-verified
- Rate limits for API keys are separate from user tokens (see [Rate Limiting](./rate-limiting.md))

## Session Management

- Active sessions are tracked in Redis with key pattern `session:{user_id}:{session_id}`
- Maximum 5 concurrent sessions per user
- Sessions are invalidated on password change
- Admins can revoke all sessions for a user via `DELETE /auth/sessions/{user_id}`

## Security Notes

- All passwords require minimum 12 characters, checked against HaveIBeenPwned API on registration
- Failed login attempts are rate-limited: 5 attempts per 15 minutes per email, then 30-minute lockout
- MFA is supported via TOTP (Google Authenticator, etc.) — required for `owner` and `admin` roles
- JWTs use RS256 (asymmetric) so downstream services only need the public key
- Refresh tokens are bound to the user-agent — changing browsers requires re-login

## Known Issues

- **ACME-4521:** Refresh token rotation occasionally fails under high concurrency, causing users to be logged out. Workaround: retry the refresh once before redirecting to login. Fix planned for v2.8.
- **ACME-5102:** API key rate limits are not enforced in the eu-west-1 region due to a Redis replication lag issue. Tracking in the Q1 2026 sprint.
