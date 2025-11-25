# services/api/main.py
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
import time
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from libs.metrics.prom_metrics import registry, record_enqueue, record_fail, record_retry, update_queue_depth
from libs.queue.redis_queue import RedisQueue
from libs.queue.task_priority import Priority


app = FastAPI(title="Distributed Task Queue API", version="0.1.0")

queue = RedisQueue()

IDEMPOTENCY_TTL_SECONDS = 24 * 3600  # 24h


# ----------------------------------------------------------------------
# Schema
# ----------------------------------------------------------------------
class TaskCreate(BaseModel):
    payload: Dict[str, Any]
    max_retries: int = 3
    priority: str = Priority.MEDIUM

class TaskAck(BaseModel):
    task_id: str
    accepted_at: float
    biz_key: Optional[str] = None
    reused: bool = False  # True 表示命中幂等，未创建新任务


# ----------------------------------------------------------------------
# POST /tasks  -> enqueue
# ----------------------------------------------------------------------
@app.post("/tasks", response_model=TaskAck)
def create_task(req: TaskCreate, biz_key: Optional[str] = None):
    """
    创建任务并入队：
      - 如 biz_key 提供，则基于 biz_key 做幂等：
          - 若 idempotency:{biz_key} 已存在：复用原 task_id，不再入队
          - 若不存在：生成新 task_id，入队并设置幂等 key
      - 如 biz_key 未提供：每次调用都创建新任务
    """
    reused = False
    task_id: str

    # ----------------------------
    # 1) 先处理幂等性：基于 biz_key
    # ----------------------------
    if biz_key:
        existing = queue.get_idempotency(biz_key)
        if existing:
            # 幂等命中：直接返回旧的 task_id，不再重新入队
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
            try:
                queue.enqueue(task, priority=req.priority)
                queue.set_idempotency(biz_key, task_id, ttl_seconds=IDEMPOTENCY_TTL_SECONDS)
                record_enqueue()
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    else:
        # 无 biz_key：普通非幂等任务
        task_id = str(uuid.uuid4())
        task = {
            "task_id": task_id,
            "payload": req.payload,
            "retry_count": 0,
            "max_retries": req.max_retries,
            "biz_key": None,
        }
        try:
            queue.enqueue(task, priority=req.priority)
            record_enqueue()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return TaskAck(
        task_id=task_id,
        accepted_at=time.time(),
        biz_key=biz_key,
        reused=reused,
    )


# ----------------------------------------------------------------------
# GET /dlq -> view dead letter queue
# ----------------------------------------------------------------------
@app.get("/dlq")
def get_dlq(limit: int = 50):
    try:
        items = queue.list_dlq(limit=limit)
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
