# Distributed Task Queue (AWS Ready) — Roadmap

This project demonstrates the fundamentals of a distributed task system. Here is the path to turn it into a production-grade platform.

---

## 1. Queue Backend & Scalability

- Add Kafka backend (with Consumer Groups) as an alternative to Redis.
- Support pluggable queue backends via an interface layer in `libs/queue`.
- Introduce sharding / partitioning strategies:
  - per-tenant shards,
  - per-job-type shards.

---

## 2. Scheduling & SLA

- SLA-aware scheduling:
  - tasks with deadlines,
  - priority escalation when deadlines are near.
- Rate limiting:
  - per tenant,
  - per endpoint,
  - per job type.
- Support cron-like recurring jobs.

---

## 3. Autoscaling & Operations

- Turn `/autoscale/suggest` into a real control loop:
  - integrate with AWS Application Auto Scaling.
- Use metrics:
  - queue depth,
  - processing latency,
  - DLQ growth rate,
  - to drive scaling decisions.
- Provide operator dashboards:
  - top N failing jobs,
  - DLQ trends,
  - worker saturation.

---

## 4. Reliability & Multi-Region

- Redis:
  - introduce Redis Cluster / ElastiCache with replication.
- Multi-region:
  - active–passive or active–active replication patterns.
- Disaster recovery drills:
  - simulate Redis outage,
  - simulate regional failure,
  - verify that DLQ and retries behave as expected.

---

## 5. Developer Experience

- Job SDK:
  - decorator-based APIs to define tasks, similar to Celery.
- Local dev tooling:
  - CLI to inspect queues and DLQ,
  - replay tasks from DLQ.
- Better documentation:
  - more examples,
  - troubleshooting guide,
  - "how we debugged X" stories.
