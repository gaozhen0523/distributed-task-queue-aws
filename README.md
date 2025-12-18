# Distributed Task Queue (AWS Ready)

High-concurrency distributed task queue system built from scratch, inspired by Celery / Sidekiq, with explicit focus on **reliability, observability, and cloud deployment**.

- 🧱 **Core**: Task submission API · Worker pool · Retry & exponential backoff · DLQ
- 🚦 **Control**: Priority queues (high / medium / low) · Idempotency · Autoscaling suggestions
- 📊 **Observability**: Prometheus metrics · queue depth · failure / retry counts
- ☁️ **Cloud-ready**: Docker · AWS ECS Fargate · Terraform · CloudWatch Logs

---

## 1. What this project does

This repo implements a **simple but realistic** distributed task processing system:

- **API service**
  - `POST /tasks` to enqueue tasks with priority & business key
  - `GET /tasks/{id}` to query status
  - `GET /dlq` to inspect dead-letter queue
  - `GET /autoscale/suggest` to get recommended worker replicas based on backlog
- **Worker service**
  - BRPOP from **high → medium → low** priority queues
  - Execute task handler with structured logging
  - On failure: increment `retry_count`, put into Retry ZSET
  - Once `max_retries` exceeded → move to DLQ
- **Scheduler service**
  - Scans Retry ZSET periodically
  - Moves due tasks back to the right priority queue
  - Updates retry & queue depth metrics
- **Redis usage**
  - **LIST** queues for normal tasks
  - **ZSET** for retry with score = next available time
  - **HASH** (optional) for business key → task id (idempotency)
- **Metrics**
  - Enqueue / retry / failure counters
  - Task processing duration histograms
  - Queue depth gauges (high / medium / low)

---

## 2. Architecture

### 2.1 High-level diagram

```mermaid
graph TD
    A[Client /tasks API] --> B[(Redis - High Priority)]
    A --> C[(Redis - Medium Priority)]
    A --> D[(Redis - Low Priority)]

    subgraph Worker Pool
        W1[Worker 1]
        W2[Worker 2]
        W3[Worker 3]
    end

    B --> W1
    C --> W1
    D --> W1
    B --> W2
    C --> W2
    D --> W2

    W1 -->|fail| E[(Retry ZSET)]
    W2 -->|fail| E
    E -->|due→ready| B

    W1 -->|max retries| F[(Dead Letter Queue)]
````

---

## 3. Components

### API Service

* Accepts JSON payloads and enqueues tasks:

  * `priority`: `high` / `medium` / `low`
  * `max_retries`
  * optional `business_key` for idempotency
* Exposes:

  * `POST /tasks`
  * `GET /tasks/{id}`
  * `GET /dlq`
  * `GET /autoscale/suggest`
  * `GET /health`

### Worker Service

* Infinite loop over:

  1. Try BRPOP from `queue:high`
  2. Fallback to `queue:medium`
  3. Fallback to `queue:low`
* Execute handler and record:

  * `task_id`
  * `priority`
  * `attempt`
  * `latency_ms`
  * `status` (success / fail / retry / dead)
* On failure:

  ```text
  next_delay = base_delay * 2^retry_count
  ```

  * If `retry_count < max_retries` → push into Retry ZSET with score = now + next_delay
  * Else → push into DLQ

### Scheduler Service

* Runs every 500ms–1s (configurable)
* Pops due tasks from Retry ZSET
* Re-enqueues them into the corresponding priority queue
* Emits metrics about retry volume & delay

### Redis Layout

```text
tasks:queue:high
tasks:queue:medium
tasks:queue:low

tasks:retry:zset
tasks:dlq:list

tasks:id:{task_id}     # optional metadata / status
tasks:biz:{biz_key}    # idempotency mapping
```

---

## 4. Directory Structure

```text
services/
  api/          # FastAPI: /tasks, /dlq, /autoscale/suggest, /health
  worker/       # Worker process consuming from Redis
  scheduler/    # Retry scheduler

libs/
  queue/        # Redis client, priority queue helpers, idempotency
  backoff/      # Exponential backoff logic
  metrics/      # Prometheus instrumentation
  logging/      # Structured logger helpers

infra/
  terraform/
    modules/    # vpc, ecs_service_internal, ecr, redis, observability
    envs/
      dev/
        main.tf
        variables.tf
        outputs.tf

docker/
  api.Dockerfile
  worker.Dockerfile
  scheduler.Dockerfile

scripts/
  load_test.py  # Load testing / benchmarking

tests/
  ...
```

---

## 5. Getting Started (Local)

### 5.1 Requirements

* Python 3.10+
* Redis (Docker or local)
* Docker (optional, for containerized run)

### 5.2 Run Redis

Simple way (Docker):

```bash
docker run -d --name redis \
  -p 6379:6379 redis:7-alpine
```

### 5.3 Python env

```bash
python3.10 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### 5.4 Run services locally

In separate terminals:

```bash
# 1) API
uvicorn services.api.main:app --reload --port 9000

# 2) Worker
python -m services.worker.main

# 3) Scheduler
python -m services.scheduler.main
```

Health check:

```bash
curl http://localhost:9000/health
```

---

## 6. API Examples

### 6.1 Submit a task

```bash
curl -X POST "http://localhost:9000/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {"user_id": 123, "action": "send_email"},
    "priority": "high",
    "max_retries": 5,
    "business_key": "send_email:user:123"
  }'
```

Response:

```json
{
  "task_id": "8b5f2a9c-...",
  "status": "PENDING",
  "priority": "high",
  "max_retries": 5,
  "created_at": 1730xxxx.xxx
}
```

### 6.2 Query task status

```bash
curl "http://localhost:9000/tasks/8b5f2a9c-..."
```

### 6.3 Inspect DLQ

```bash
curl "http://localhost:9000/dlq"
```

### 6.4 Get autoscaling suggestion

```bash
curl "http://localhost:9000/autoscale/suggest"
```

Example:

```json
{
  "backlog": 750,
  "suggested_replicas": 4,
  "buckets": {
    "<100": 2,
    "100-500": 3,
    "500-2000": 4,
    ">2000": 6
  }
}
```

---

## 7. Benchmarking

Use `scripts/load_test.py` to generate concurrent load:

* config: total tasks, concurrency, fail rate, payload size
* output: throughput, failures, retries, latency stats

Example:

```bash
python scripts/load_test.py \
  --api-url "http://localhost:9000/tasks" \
  --tasks 1000 \
  --concurrency 50 \
  --fail-rate 0.1
```

Metrics exposed at:

```text
GET /metrics
```

Key metrics:

* `enqueue_total`
* `retry_total`
* `fail_total`
* `task_processing_seconds_bucket`
* `queue_depth{priority="high|medium|low"}`
* `worker_active_gauge`

---

## 8. Deploying to AWS

High-level flow:

1. Build Docker images for `api`, `worker`, `scheduler`, push to ECR.
2. Use Terraform in `infra/terraform/envs/dev` to:

   * create VPC + subnets + security groups
   * create ECS cluster and three services (api / worker / scheduler)
   * provision Redis (container or ElastiCache, depending on env)
   * wire up ALB for API service
3. Point a domain (optional) to the ALB via Route 53.

Logs are aggregated into CloudWatch; alarms can be added based on:

* DLQ size
* queue depth
* failure rate

---

## 9. Known limitations

* Single Redis instance (no clustering / sentinel).
* Simple fixed priority policy (no per-tenant weights).
* Autoscaling output is **advisory** only; it does not yet call AWS APIs to scale workers automatically.

---

## 10. Future work

* Switch Redis → Kafka + Consumer Groups.
* Real autoscaling via AWS Application Auto Scaling.
* SLA-aware scheduling and task deadlines.
* Per-tenant rate limiting and quotas.
* Full tracing via OpenTelemetry.


