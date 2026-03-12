# API Rate Limiting Spec

**Last updated:** 2025-09-20  
**Owner:** Platform Team  
**Status:** Current

## Overview

Rate limiting is enforced at the `gateway` service using a sliding window algorithm backed by Redis. Limits are applied per-tenant and per-endpoint to prevent abuse and ensure fair resource allocation.

## Rate Limit Tiers

Limits vary by the tenant's subscription plan:

| Plan | Requests/min (global) | Requests/min (per endpoint) | Burst allowance |
| ---- | --------------------- | --------------------------- | --------------- |
| Free | 60 | 20 | 10 |
| Starter | 300 | 100 | 50 |
| Professional | 1,200 | 400 | 200 |
| Enterprise | 6,000 | 2,000 | 1,000 |

**Global limit** applies to all API calls combined for a tenant.  
**Per-endpoint limit** applies to each unique `METHOD + path pattern` (e.g., `GET /workflows` and `POST /workflows` are separate).  
**Burst allowance** permits short spikes above the per-minute rate, consumed from a token bucket that refills at the per-minute rate.

## Implementation

### Algorithm: Sliding Window Log

We use a Redis sorted set per tenant per window:

- Key: `ratelimit:{tenant_id}:{endpoint_hash}:{window_minute}`
- Members: request timestamps (scored by timestamp)
- TTL: 2 minutes (auto-cleanup)

On each request:
1. Remove entries older than 60 seconds from the sorted set
2. Count remaining entries
3. If count >= limit, reject with `429 Too Many Requests`
4. Otherwise, add the current timestamp and allow the request

### Burst Handling: Token Bucket

A separate token bucket allows short bursts:

- Key: `ratelimit:burst:{tenant_id}:{endpoint_hash}`
- Stored as a Redis hash: `{tokens: N, last_refill: timestamp}`
- Tokens refill at `rate_per_minute / 60` per second
- Maximum tokens = burst allowance for the plan

A request is allowed if **either** the sliding window has capacity **or** a burst token is available.

## Response Headers

All API responses include rate limit headers:

```
X-RateLimit-Limit: 1200
X-RateLimit-Remaining: 847
X-RateLimit-Reset: 1698765432
X-RateLimit-Burst-Remaining: 150
```

When rate limited, the response is:

```json
HTTP/1.1 429 Too Many Requests
Retry-After: 12

{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Retry after 12 seconds.",
  "limit": 1200,
  "reset_at": "2025-09-20T14:32:12Z"
}
```

## Exemptions

The following are exempt from rate limiting:

- `GET /health` — health checks from load balancers
- `POST /auth/login` — has its own separate rate limit (see [Authentication Spec](./authentication.md))
- `POST /webhooks/incoming` — webhook receivers from third-party integrations (rate limited per source IP instead)
- Internal service-to-service calls (identified by `X-Internal-Service` header with HMAC signature)

## Rate Limiting for API Keys

API keys have separate rate limits from user sessions:

| Plan | API Key Requests/min |
| ---- | -------------------- |
| Free | Not available |
| Starter | 120 |
| Professional | 600 |
| Enterprise | 3,000 |

A tenant's user-session rate limit and API-key rate limit are tracked independently. Using both simultaneously effectively doubles the available throughput.

## Monitoring

- **Dashboard:** Datadog dashboard "Rate Limiting" shows real-time rejection rates per tenant and endpoint
- **Alert:** If global 429 rate exceeds 10% of total traffic for 5 minutes → SEV-3 alert
- **Alert:** If a single tenant is rate-limited for > 30 minutes continuously → notify Customer Success team

## Cost Considerations

Each rate limit check requires 2-3 Redis operations (ZREMRANGEBYSCORE, ZCARD, ZADD). At current traffic (~8,000 req/s peak), this adds approximately 24,000 Redis operations/second dedicated to rate limiting.

Current Redis capacity can handle ~200,000 ops/s, so rate limiting consumes about 12% of Redis capacity. If we add more granular rate limiting (e.g., per-user within a tenant), we may need to scale Redis or move to a dedicated rate-limiting Redis cluster.

## Known Issues

- **RATE-201:** Rate limit headers are not returned on WebSocket upgrade requests. The WebSocket connection itself is rate-limited (max 5 connections per tenant), but the client has no visibility into the limit. Fix planned for v2.9.
- **RATE-215:** The burst token bucket can go slightly negative under high concurrency due to a TOCTOU race in the Redis script. Impact is minimal (allows ~2-3 extra requests per burst). A Lua script fix is in code review.
- **ACME-5102:** API key rate limits are not enforced in eu-west-1 (see [Authentication Spec](./authentication.md) for details).
