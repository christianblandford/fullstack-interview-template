# Architecture Overview

**Last updated:** 2025-11-15  
**Owner:** Platform Team  
**Status:** Current

## System Overview

Acme Corp runs a multi-tenant SaaS platform ("Acme Platform") serving ~2,400 B2B customers. The platform provides workflow automation, document management, and analytics for mid-market logistics companies.

## High-Level Architecture

The system follows a service-oriented architecture with the following primary services:

| Service | Language | Runtime | Purpose |
| ------- | -------- | ------- | ------- |
| `gateway` | Go | Kubernetes | API gateway, rate limiting, auth token validation |
| `core-api` | Python (FastAPI) | Kubernetes | Business logic, CRUD operations |
| `worker` | Python (Celery) | Kubernetes | Async job processing (reports, exports, notifications) |
| `realtime` | Node.js | Kubernetes | WebSocket connections for live updates |
| `analytics` | Python (FastAPI) | Kubernetes | Read-only analytics queries, dashboards |
| `ml-pipeline` | Python | AWS SageMaker | Document classification, anomaly detection |

## Infrastructure

- **Cloud:** AWS (us-east-1 primary, eu-west-1 for EU customers)
- **Orchestration:** Kubernetes (EKS) with Karpenter for autoscaling
- **Database:** PostgreSQL 16 (RDS) — primary data store, one writer + 3 read replicas
- **Cache:** Redis 7 (ElastiCache) — session store, rate limit counters, pub/sub for realtime
- **Queue:** RabbitMQ — task queue for Celery workers
- **Object Storage:** S3 — document uploads, report exports, ML model artifacts
- **CDN:** CloudFront — static assets, pre-signed document URLs
- **Search:** OpenSearch — full-text search across documents and audit logs

## Data Flow

1. All external traffic enters through CloudFront → ALB → `gateway`
2. `gateway` validates JWT tokens (see [Authentication Spec](./authentication.md)), applies rate limits, and routes to downstream services
3. `core-api` handles all write operations and publishes events to RabbitMQ
4. `worker` consumes events for async processing (email, PDF generation, webhook delivery)
5. `realtime` subscribes to Redis pub/sub channels and pushes updates to connected WebSocket clients
6. `analytics` reads from PostgreSQL read replicas only — never touches the writer

## Tenant Isolation

All data is tenant-scoped using a `tenant_id` column. Row-level security (RLS) is enforced at the PostgreSQL level. The `gateway` injects `X-Tenant-ID` headers after JWT validation, and downstream services trust this header.

There is no per-tenant database isolation. All tenants share the same PostgreSQL cluster. This is a known limitation — see the Q3 2026 roadmap for the planned migration to per-tenant schemas.

## Deployment

- All services are deployed via ArgoCD with GitOps
- CI/CD runs on GitHub Actions
- Staging deploys on every merge to `main`
- Production deploys require manual approval in ArgoCD
- Rollbacks are automatic if health checks fail within 5 minutes

## Key Metrics

| Metric | Current Value | SLA Target |
| ------ | ------------- | ---------- |
| API p99 latency | 180ms | < 250ms |
| Uptime (30d rolling) | 99.97% | 99.95% |
| Deploy frequency | ~8/day | — |
| Mean time to recovery | 4 min | < 15 min |

## Related Documents

- [Authentication Spec](./authentication.md)
- [API Rate Limiting](./rate-limiting.md)
- [Data Pipeline Spec](./data-pipeline.md)
- [Incident Response Runbook](./incident-response.md)
