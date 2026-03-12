# Data Pipeline Spec

**Last updated:** 2025-10-28  
**Owner:** Data Engineering Team  
**Status:** Current

## Overview

The Acme Platform data pipeline handles ETL for analytics, ML feature generation, and compliance reporting. It processes approximately 12 million events per day across all tenants.

## Pipeline Architecture

```
core-api (writes) → PostgreSQL → Debezium CDC → Kafka → Flink → Data Warehouse (Redshift)
                                                      ↘ S3 (raw events, Parquet)
                                                      ↘ Feature Store (Redis)
```

### Components

| Component | Technology | Purpose |
| --------- | ---------- | ------- |
| CDC | Debezium | Captures row-level changes from PostgreSQL WAL |
| Streaming | Kafka (MSK) | Event bus, 7-day retention, 12 partitions per topic |
| Processing | Apache Flink | Stream processing, aggregations, joins |
| Warehouse | Redshift Serverless | Analytics queries, dashboards, ad-hoc SQL |
| Raw Storage | S3 + Parquet | Immutable event archive, 5-year retention |
| Feature Store | Redis | Low-latency ML feature serving |

## Event Schema

All events follow a common envelope:

```json
{
  "event_id": "uuid",
  "event_type": "workflow.completed",
  "tenant_id": "uuid",
  "user_id": "uuid",
  "timestamp": "2025-10-28T14:32:00Z",
  "version": 3,
  "payload": { ... }
}
```

### Key Event Types

| Event | Published By | Consumers |
| ----- | ------------ | --------- |
| `workflow.created` | core-api | analytics, ml-pipeline |
| `workflow.completed` | worker | analytics, ml-pipeline, billing |
| `document.uploaded` | core-api | ml-pipeline (classification) |
| `document.classified` | ml-pipeline | core-api (updates metadata) |
| `user.login` | core-api | analytics, security-audit |
| `export.requested` | core-api | worker (generates file) |
| `invoice.generated` | billing | analytics, notifications |

## Processing Stages

### Stage 1: CDC Ingestion

Debezium captures INSERT, UPDATE, DELETE operations from PostgreSQL and publishes to Kafka topics named `cdc.{schema}.{table}`. Each message includes the full row before/after state.

Latency: ~500ms from database write to Kafka.

### Stage 2: Stream Processing (Flink)

Flink jobs consume from Kafka and perform:

1. **Enrichment** — joins events with tenant metadata (plan tier, region, feature flags)
2. **Aggregation** — 1-minute and 5-minute tumbling windows for real-time dashboards
3. **Deduplication** — exactly-once semantics using event_id as the dedup key
4. **Routing** — writes to Redshift (via S3 staging), S3 archive, and Redis feature store

### Stage 3: Warehouse Loading

Flink writes Parquet files to S3 every 5 minutes, then triggers a Redshift `COPY` command. Data is available for analytics queries within ~10 minutes of the original event.

### Stage 4: Feature Store

ML features (e.g., "average workflow completion time for this tenant over 30 days") are computed by Flink and written to Redis with a TTL of 24 hours. The `ml-pipeline` service reads features from Redis at inference time.

## Data Retention

| Data Store | Retention | Reason |
| ---------- | --------- | ------ |
| PostgreSQL (operational) | Active data only | Source of truth for live application |
| Kafka | 7 days | Reprocessing window |
| S3 (raw Parquet) | 5 years | Compliance (SOC 2, GDPR audit trail) |
| Redshift | 13 months | Analytics queries (rolling window) |
| Redis (feature store) | 24-hour TTL | ML inference, auto-expires |

## Backfill Process

When a Flink job logic changes or a new aggregation is needed:

1. Deploy the updated Flink job with a `--backfill` flag
2. It reads from S3 Parquet archive instead of Kafka
3. Reprocesses historical data and writes to Redshift
4. Typical backfill for 1 month of data: ~45 minutes

## Monitoring

- **Kafka consumer lag** — alert if any consumer group falls behind by > 100,000 messages
- **Flink checkpoint failures** — alert on 3 consecutive failures
- **Redshift COPY failures** — alert immediately, triggers PagerDuty
- **S3 write latency** — alert if p99 > 5 seconds

## Known Issues

- **DATA-892:** The `document.classified` event sometimes arrives before `document.uploaded` due to a race condition in the ml-pipeline. The Flink job handles this with a 30-second buffered join, but events arriving more than 30 seconds apart are dropped. Affects ~0.3% of documents.
- **DATA-1045:** Redshift COPY occasionally fails with "S3ServiceException: SlowDown" during peak hours (2-4pm ET). Current mitigation: exponential backoff with 3 retries. Long-term fix: switch to Redshift streaming ingestion (planned Q2 2026).
