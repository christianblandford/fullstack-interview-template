# Deployment Guide

**Last updated:** 2025-12-15  
**Owner:** Platform Team  
**Status:** Current

## Environments

| Environment | Purpose | URL | Deploy Trigger |
| ----------- | ------- | --- | -------------- |
| `dev` | Local development | localhost | Manual |
| `staging` | Pre-production testing | staging.acmecorp.com | Auto on merge to `main` |
| `production` | Live customer traffic | app.acmecorp.com | Manual approval in ArgoCD |

## CI/CD Pipeline

All code changes go through GitHub Actions:

### Pull Request Checks

1. **Lint & Format** — ESLint, Prettier (frontend), Ruff, Black (backend)
2. **Type Check** — TypeScript strict mode (frontend), mypy (backend)
3. **Unit Tests** — Jest (frontend), pytest (backend), must pass 100%
4. **Integration Tests** — API contract tests against a test database
5. **Bundle Analysis** — Vite bundle size check, fails if > 10% increase
6. **Security Scan** — Snyk for dependency vulnerabilities, fails on high/critical

All checks must pass before merge. No exceptions.

### Staging Deploy (Automatic)

On merge to `main`:

1. GitHub Actions builds Docker images for all changed services
2. Images are tagged with the git SHA and pushed to ECR
3. ArgoCD detects the new image tags and deploys to staging
4. Smoke tests run automatically against staging
5. If smoke tests fail, ArgoCD automatically rolls back

Typical time from merge to staging: **4-6 minutes**.

### Production Deploy (Manual)

1. Engineer opens ArgoCD and selects the services to promote
2. ArgoCD shows a diff of what will change (image tags, config)
3. Engineer clicks "Sync" to begin the rollout
4. Kubernetes performs a rolling update (25% at a time)
5. Each batch must pass health checks before the next batch starts
6. If any batch fails health checks for 5 minutes, automatic rollback

Typical time from approval to full rollout: **8-12 minutes**.

## Service Configuration

### Environment Variables

All services read configuration from environment variables, managed via:
- **Local dev:** `.env` files (not committed to git)
- **Staging/Production:** AWS Secrets Manager, injected by Kubernetes External Secrets Operator

Required variables per service:

#### core-api
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
RABBITMQ_URL=amqp://...
JWT_PUBLIC_KEY=...
S3_BUCKET=acme-documents
AWS_REGION=us-east-1
```

#### gateway
```
JWT_PUBLIC_KEY=...
REDIS_URL=redis://...
RATE_LIMIT_ENABLED=true
INTERNAL_SERVICE_SECRET=...
```

#### worker
```
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
RABBITMQ_URL=amqp://...
S3_BUCKET=acme-documents
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
```

### Feature Flags

Feature flags are managed via LaunchDarkly:

- **Backend flags** are evaluated in `core-api` and cached in Redis for 30 seconds
- **Frontend flags** are fetched via the LaunchDarkly React SDK with streaming updates
- All new features must be behind a flag for the first 2 weeks in production
- Flags are cleaned up (removed from code) within 30 days of full rollout

## Database Migrations

### Schema Migrations (PostgreSQL)

We use Alembic for schema migrations:

```bash
# Create a new migration
cd api && alembic revision --autogenerate -m "add_column_to_workflows"

# Apply migrations
cd api && alembic upgrade head

# Rollback one migration
cd api && alembic downgrade -1
```

Migration rules:
- **Never** drop a column in the same deploy that removes the code using it. Always do it in two deploys.
- **Never** add a NOT NULL column without a default value (will lock the table).
- **Always** add indexes concurrently: `CREATE INDEX CONCURRENTLY ...`
- **Always** test migrations against a copy of production data before deploying.

Migrations run automatically during the staging deploy. For production, they run as a Kubernetes Job before the application pods are updated.

### Data Migrations

For backfilling data or transforming existing rows:

1. Write a one-off script in `api/scripts/migrations/`
2. Test against staging
3. Run in production during a maintenance window (if the migration locks rows) or as a background job (if it doesn't)
4. Document the migration in the PR description

## Rollback Procedures

### Application Rollback

```bash
# Via ArgoCD UI: click "History" → select previous version → "Rollback"

# Via CLI:
argocd app rollback <app-name> <revision>
```

ArgoCD keeps the last 10 revisions. Rollback takes ~2 minutes.

### Database Rollback

```bash
cd api && alembic downgrade -1
```

**Warning:** Not all migrations are reversible. Destructive migrations (column drops, data transforms) cannot be rolled back. Always check the `downgrade()` function before relying on this.

### Emergency Procedures

If a deploy causes a SEV-1 incident:

1. **Immediately** roll back the application via ArgoCD
2. If the issue is a database migration: assess whether `alembic downgrade` is safe
3. If the migration is not reversible: fix forward with a hotfix branch
4. Follow the [Incident Response Runbook](./incident-response.md)

## Monitoring Deploys

After every production deploy, monitor for 15 minutes:

1. **Error rate** — should not increase by more than 0.5%
2. **Latency** — p99 should not increase by more than 50ms
3. **Memory/CPU** — should not spike above normal patterns
4. **Logs** — check for new error patterns in Datadog

If any of these degrade, roll back immediately and investigate.
