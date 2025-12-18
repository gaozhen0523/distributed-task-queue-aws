# Distributed Task Queue (AWS Ready) — Interview Notes

---

## Page 1 — Architecture & Why I Built It

**Motivation**

- I wanted to demonstrate I can design and implement:
  - a distributed, fault-tolerant task processing system,
  - with clear separation between API, worker, scheduler,
  - similar to Celery / Sidekiq, but small enough to read in an interview.

**Architecture**

- **API Service**
  - `POST /tasks` to enqueue tasks with priority & max_retries.
  - `GET /tasks/{id}`, `/dlq`, `/autoscale/suggest`, `/health`.
- **Worker Service**
  - BRPOP from high → medium → low Redis lists.
  - Execute handler, handle retries, push to DLQ on max_retries.
- **Scheduler Service**
  - Periodically scans the Retry ZSET.
  - Moves due tasks back to the appropriate priority queue.
- **Redis**
  - LIST for main queues,
  - ZSET for retry with delay,
  - HASH for business key → task id (idempotency).
- **Metrics**
  - Prometheus metrics for queue depth, processing latency, retries, failures.

---

## Page 2 — Performance, Backoff & Priority

**Throughput and worker model**

- Worker processes are independent and stateless:
  - safe to scale horizontally on ECS.
- Each worker uses blocking pops (BRPOP) with priority order:
  - high → medium → low,
  - avoiding busy-waiting and keeping latency low for high-priority tasks.

**Retry & backoff design**

- On failure, a task is not immediately retried:
  - instead it’s inserted into a Retry ZSET with a `next_available_at` timestamp.
- Backoff formula:

  ```text
  delay = base_delay * 2^retry_count
    ````

* This avoids:

  * hot-looping on failing tasks,
  * and distributes retries over time.

**Autoscaling story**

* API exposes `/autoscale/suggest`:

  * looks at backlog (queue depth),
  * maps ranges to recommended replicas, e.g.:

    * `<100` → 1–2,
    * `100–500` → 3,
    * `500–2000` → 4,
    * `>2000` → 6.
* In a real environment you could:

  * wire this into AWS Application Auto Scaling,
  * or use it as a manual SRE playbook.

---

## Page 3 — Reliability, DLQ & Cloud Deployment Story

**Reliability & failure handling**

* Tasks that exceed `max_retries` go into a **Dead Letter Queue**.
* DLQ is queryable via `/dlq`:

  * makes it easy to inspect bad payloads or misconfigured jobs.
* Redis connectivity issues are handled gracefully:

  * workers degrade instead of crashing,
  * errors are counted and visible in metrics.

**Observability**

* Metrics include:

  * `enqueue_total`, `retry_total`, `fail_total`,
  * queue depth per priority,
  * task processing duration histograms.
* These are exported in Prometheus format and can be combined with CloudWatch logs.
* Tracing hooks are planned so we can trace:

  * API → Worker → Retry → DLQ.

**What I would extend in a real team**

* Use **Kafka + Consumer Groups** instead of Redis lists for better scalability.
* Implement **SLA-aware scheduling**:

  * deadlines / priorities based on tenant / business impact.
* Implement **automatic autoscaling**:

  * scale worker services based on queue length and processing latency.
* Add multi-region failover and disaster recovery.
