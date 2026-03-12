# Incident Response Runbook

**Last updated:** 2026-01-10  
**Owner:** SRE Team  
**Status:** Current

## Severity Levels

| Level | Definition | Response Time | Examples |
| ----- | ---------- | ------------- | -------- |
| SEV-1 | Full outage or data loss affecting all customers | 5 min (PagerDuty) | Database down, auth service down, data corruption |
| SEV-2 | Partial outage or degraded performance for >10% of customers | 15 min (PagerDuty) | Elevated error rates, one region down, slow queries |
| SEV-3 | Minor issue affecting a small subset of customers | 1 hour (Slack) | Single tenant issue, non-critical feature broken |
| SEV-4 | Cosmetic or low-impact issue | Next business day | UI glitch, incorrect tooltip, minor logging gap |

## On-Call Rotation

- **Primary on-call:** Rotates weekly across the SRE team (currently 6 engineers)
- **Secondary on-call:** The previous week's primary
- **Escalation:** If primary doesn't acknowledge within 5 minutes, PagerDuty escalates to secondary, then to the SRE manager
- **Schedule:** Managed in PagerDuty, synced to Google Calendar
- **Compensation:** $500/week on-call stipend + $200 per SEV-1/SEV-2 incident outside business hours

## Incident Workflow

### 1. Detection

Incidents are detected via:
- **Automated alerts** — Datadog monitors (see thresholds below)
- **Customer reports** — via Zendesk, escalated by Support team
- **Internal reports** — engineers notice something in Slack #alerts

### 2. Triage

The on-call engineer:
1. Acknowledges the PagerDuty alert
2. Opens an incident channel: `#inc-YYYY-MM-DD-short-description`
3. Assesses severity level
4. Posts initial status to #incidents: "Investigating elevated 5xx rates on core-api"

### 3. Mitigation

Priority is **restore service first**, investigate root cause later.

Common mitigations:
- **Bad deploy:** Roll back via ArgoCD (takes ~2 minutes)
- **Database overload:** Kill long-running queries, failover to read replica
- **Memory leak:** Restart affected pods (`kubectl rollout restart`)
- **Upstream dependency down:** Enable circuit breaker / fallback mode
- **DDoS / traffic spike:** Scale up via Karpenter, enable aggressive rate limiting

### 4. Communication

| Audience | Channel | Frequency |
| -------- | ------- | --------- |
| Engineering | Slack #inc-* channel | Real-time |
| Leadership | Slack #incidents | Every 30 min for SEV-1, every hour for SEV-2 |
| Customers | status.acmecorp.com | Updated within 15 min of detection for SEV-1/2 |
| Support team | Slack #support-escalations | As needed |

### 5. Resolution

1. Confirm the issue is resolved (metrics back to normal)
2. Post final update to all channels
3. Update status page
4. Create a JIRA ticket for the post-mortem (due within 5 business days for SEV-1/2)

### 6. Post-Mortem

Template: [Post-Mortem Template](https://docs.google.com/templates/postmortem) (internal)

Required sections:
- Timeline of events
- Root cause analysis (use 5 Whys)
- Impact assessment (customers affected, duration, data impact)
- Action items with owners and due dates
- What went well / what could be improved

Post-mortems are **blameless**. Focus on systems and processes, not individuals.

## Alert Thresholds (Datadog)

| Alert | Condition | Severity | Notify |
| ----- | --------- | -------- | ------ |
| API error rate | 5xx rate > 5% for 2 min | SEV-2 | PagerDuty |
| API error rate | 5xx rate > 25% for 1 min | SEV-1 | PagerDuty |
| API latency | p99 > 500ms for 5 min | SEV-3 | Slack #alerts |
| API latency | p99 > 2s for 2 min | SEV-2 | PagerDuty |
| Database connections | Active connections > 80% pool | SEV-3 | Slack #alerts |
| Database connections | Active connections > 95% pool | SEV-1 | PagerDuty |
| Database replication lag | Lag > 30s for 5 min | SEV-2 | PagerDuty |
| Redis memory | Usage > 80% | SEV-3 | Slack #alerts |
| Redis memory | Usage > 95% | SEV-1 | PagerDuty |
| Kafka consumer lag | Lag > 100k messages for 10 min | SEV-3 | Slack #alerts |
| Kafka consumer lag | Lag > 1M messages for 5 min | SEV-2 | PagerDuty |
| Certificate expiry | < 14 days to expiry | SEV-3 | Slack #alerts |
| Disk usage | > 85% on any node | SEV-3 | Slack #alerts |
| Pod restarts | > 5 restarts in 10 min | SEV-3 | Slack #alerts |

## Runbook: Common Scenarios

### Database Failover

If the primary PostgreSQL instance is unresponsive:

1. Check RDS console for the instance status
2. If the instance is in `storage-full` state: increase storage via AWS console (takes ~10 min)
3. If the instance is crashed: initiate RDS failover to the standby (`aws rds failover-db-cluster`)
4. Verify application reconnects (connection pool should retry automatically)
5. Check for data consistency — compare row counts on key tables

### Redis Cluster Recovery

If Redis is OOM or unresponsive:

1. Check which keys are consuming the most memory: `redis-cli --bigkeys`
2. If it's session data: flush sessions (`FLUSHDB 2`) — users will need to re-login
3. If it's rate limit counters: flush rate limits (`FLUSHDB 3`) — temporary rate limit bypass
4. If it's the feature store: flush features (`FLUSHDB 4`) — ML predictions will use fallback values for 24h
5. Scale up the ElastiCache node type if the issue is capacity

### Stuck Celery Workers

If the worker queue is backing up:

1. Check RabbitMQ management UI for queue depth
2. Check for stuck tasks: `celery inspect active`
3. If tasks are stuck on external API calls: check the external service status
4. Revoke stuck tasks: `celery control revoke <task_id> --terminate`
5. Scale up worker replicas: `kubectl scale deployment worker --replicas=10`
6. If the queue is poisoned (bad message format): purge the queue and investigate the publisher

## Recent Incidents

| Date | Severity | Duration | Summary |
| ---- | -------- | -------- | ------- |
| 2026-01-08 | SEV-2 | 23 min | Redshift COPY failures caused analytics dashboard to show stale data. Root cause: S3 throttling during peak. Mitigation: increased retry backoff. |
| 2025-12-19 | SEV-1 | 8 min | core-api OOM due to a query returning 2M rows without pagination. Root cause: missing LIMIT clause in the export endpoint. Fix: added mandatory pagination. |
| 2025-12-03 | SEV-2 | 45 min | Authentication failures in eu-west-1 due to Redis replication lag. Root cause: network partition between AZs. Mitigation: failed over to local Redis replica. |
| 2025-11-15 | SEV-3 | 2 hours | Webhook deliveries delayed by 30+ minutes. Root cause: Celery worker stuck on a single tenant's webhook endpoint that was returning 504s with 30s timeout. Fix: reduced webhook timeout to 5s, added per-tenant circuit breaker. |
