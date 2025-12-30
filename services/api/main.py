# services/api/main.py
import time
import uuid
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel

from libs.logging.structured_logger import logger
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

load_dotenv(override=False)
app = FastAPI(title="Distributed Task Queue API", version="0.1.0")


@app.middleware("http")
async def inject_trace_and_correlation(request: Request, call_next):
    """
    分布式任务系统 API 统一注入 trace_id / correlation_id：
      - 优先使用上游 X-Trace-Id / X-Correlation-Id
      - 否则生成新的 trace_id
    """
    header_trace_id = request.headers.get("X-Trace-Id") or request.headers.get(
        "X-Trace-ID"
    )
    correlation_id = request.headers.get("X-Correlation-Id")

    trace_id = header_trace_id or uuid.uuid4().hex

    request.state.trace_id = trace_id
    request.state.correlation_id = correlation_id

    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    if correlation_id:
        response.headers["X-Correlation-Id"] = correlation_id
    return response


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
def create_task(req: TaskCreate, request: Request, biz_key: str | None = None):
    trace_id = getattr(request.state, "trace_id", None)
    correlation_id = getattr(request.state, "correlation_id", None)

    t0 = time.time()

    try:
        reused = False
        task_id: str

        # 幂等性
        if biz_key:
            existing = queue.get_idempotency(biz_key)

            # 2) 是否已有 processing lock（任务正在被 worker 执行）
            processing = queue.get_processing(biz_key)

            if existing or processing:
                # 返回已有 task_id（processing 优先）
                task_id = processing or existing
                reused = True
            else:
                task_id = str(uuid.uuid4())
                task = {
                    "task_id": task_id,
                    "payload": req.payload,
                    "retry_count": 0,
                    "max_retries": req.max_retries,
                    "biz_key": biz_key,
                    "trace_id": trace_id,
                    "correlation_id": correlation_id,
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
                "trace_id": trace_id,
                "correlation_id": correlation_id,
            }
            queue.enqueue(task, priority=req.priority)
            record_enqueue()

        logger.info(
            "TASK_ENQUEUED",
            trace_id=trace_id,
            correlation_id=correlation_id,
            extra={
                "task_id": task_id,
                "biz_key": biz_key,
                "priority": req.priority,
                "reused": reused,
            },
        )
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
def autoscale_suggest(cpu: float | None = None):
    """
    返回队列 backlog + 可选 CPU 百分比下的副本数建议。

    用法示例：
      GET /autoscale/suggest
      GET /autoscale/suggest?cpu=72.5
    """
    try:
        scaler = AutoScaler()
        return scaler.get_suggestion(cpu_percent=cpu)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def debug_key():
    req = TaskCreate(payload={"task_id": str(uuid.uuid4())})
    create_task(req, biz_key="zhen4")
    return 0


# test2


@app.get("/test/error")
def test_error(request: Request):
    trace_id = getattr(request.state, "trace_id", None)
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.error(
        "TEST_ERROR_TRIGGERED",
        trace_id=trace_id,
        correlation_id=correlation_id,
    )
    raise RuntimeError("Intentional test error for CloudWatch logging")
