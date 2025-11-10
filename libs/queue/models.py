from enum import Enum
from datetime import datetime, timedelta
from typing import Optional
import uuid

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    RETRY = "RETRY"

class Task:
    def __init__(self, payload: dict, max_retries: int = 3):
        self.id = str(uuid.uuid4())
        self.payload = payload
        self.status = TaskStatus.PENDING
        self.retry_count = 0
        self.max_retries = max_retries
        self.retry_after: Optional[datetime] = None
        self.created_at = datetime.utcnow()
        self.updated_at = self.created_at

    def mark_running(self):
        self.status = TaskStatus.RUNNING
        self.updated_at = datetime.utcnow()

    def mark_done(self):
        self.status = TaskStatus.DONE
        self.updated_at = datetime.utcnow()

    def mark_failed(self):
        """失败一次 → 进入 RETRY 或 FAILED"""
        self.updated_at = datetime.utcnow()
        if self.retry_count < self.max_retries:
            self.status = TaskStatus.RETRY
            delay = 2 ** self.retry_count   # 指数退避
            self.retry_after = datetime.utcnow() + timedelta(seconds=delay)
            self.retry_count += 1
        else:
            self.status = TaskStatus.FAILED
