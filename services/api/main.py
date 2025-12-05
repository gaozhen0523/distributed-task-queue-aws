# services/api/main.py
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from libs.metrics.prom_metrics import (
    observe_api_latency,
    record_enqueue,
    record_fail,
    record_retry,
    registry,
    update_queue_depth,
)
from libs.queue.auto_scale import AutoScaler
from libs.queue.redis_queue import RedisQueue
from libs.queue.task_priority import Priority

app = FastAPI(title="Distributed Task Queue API", version="0.1.0")

queue = RedisQueue()

IDEMPOTENCY_TTL_SECONDS = 24 * 3600  # 24h


# ----------------------------------------------------------------------
# Schema
# ----------------------------------------------------------------------
class TaskCreate(BaseModel):
    payload: dict[str, Any]
    max_retries: int = 3
    priority: str = Priority.MEDIUM


class TaskAck(BaseModel):
    task_id: str
    accepted_at: float
    biz_key: str | None = None
    reused: bool = False  # True 表示命中幂等，未创建新任务


# ----------------------------------------------------------------------
# POST /tasks  -> enqueue
# ----------------------------------------------------------------------
@app.post("/tasks", response_model=TaskAck)
def create_task(req: TaskCreate, biz_key: str | None = None):
    t0 = time.time()

    try:
        reused = False
        task_id: str

        # 幂等性
        if biz_key:
            existing = queue.get_idempotency(biz_key)
            if existing:
                task_id = existing
                reused = True
            else:
                task_id = str(uuid.uuid4())
                task = {
                    "task_id": task_id,
                    "payload": req.payload,
                    "retry_count": 0,
                    "max_retries": req.max_retries,
                    "biz_key": biz_key,
                }
                queue.enqueue(task, priority=req.priority)
                queue.set_idempotency(
                    biz_key, task_id, ttl_seconds=IDEMPOTENCY_TTL_SECONDS
                )
                record_enqueue()
        else:
            task_id = str(uuid.uuid4())
            task = {
                "task_id": task_id,
                "payload": req.payload,
                "retry_count": 0,
                "max_retries": req.max_retries,
                "biz_key": None,
            }
            queue.enqueue(task, priority=req.priority)
            record_enqueue()

        return TaskAck(
            task_id=task_id,
            accepted_at=time.time(),
            biz_key=biz_key,
            reused=reused,
        )

    finally:
        observe_api_latency(time.time() - t0)


# ----------------------------------------------------------------------
# GET /dlq -> view dead letter queue
# ----------------------------------------------------------------------
@app.get("/dlq")
def get_dlq(limit: int = 50):
    t0 = time.time()
    try:
        items = queue.list_dlq(limit=limit)
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        observe_api_latency(time.time() - t0)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    """Prometheus-compatible metrics endpoint"""
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/metrics/test")
def metrics_test():
    record_enqueue()
    record_enqueue()
    record_fail()
    record_retry()
    update_queue_depth(3)
    return {"ok": True}


@app.get("/autoscale/suggest")
def autoscale_suggest():
    try:
        scaler = AutoScaler()
        return scaler.get_suggestion()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def debug_key():
    req = TaskCreate(payload={"task_id": str(uuid.uuid4())})
    create_task(req, biz_key="zhen4")
    return 0
