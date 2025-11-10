# services/api/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
import uuid
import time

from libs.queue.redis_queue import RedisQueue


app = FastAPI(title="Distributed Task Queue API", version="0.1.0")

queue = RedisQueue()


# ----------------------------------------------------------------------
# Schema
# ----------------------------------------------------------------------
class TaskCreate(BaseModel):
    payload: Dict[str, Any]
    max_retries: int = 3


class TaskAck(BaseModel):
    task_id: str
    accepted_at: float


# ----------------------------------------------------------------------
# POST /tasks  -> enqueue
# ----------------------------------------------------------------------
@app.post("/tasks", response_model=TaskAck)
def create_task(req: TaskCreate):
    task_id = str(uuid.uuid4())

    task = {
        "task_id": task_id,
        "payload": req.payload,
        "retry_count": 0,
        "max_retries": req.max_retries,
    }

    try:
        queue.enqueue(task)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return TaskAck(
        task_id=task_id,
        accepted_at=time.time(),
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
