from fastapi import FastAPI
from libs.queue.models import Task, TaskStatus

app = FastAPI(title="Distributed Task Queue API")

# 临时内存存储, Day6 会改成 Redis
tasks = {}

@app.post("/tasks")
def create_task(payload: dict):
    task = Task(payload)
    tasks[task.id] = task
    return {"task_id": task.id, "status": task.status}

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    t = tasks.get(task_id)
    if not t:
        return {"error": "not found"}
    return {
        "id": t.id,
        "status": t.status,
        "retry_count": t.retry_count,
        "max_retries": t.max_retries,
    }