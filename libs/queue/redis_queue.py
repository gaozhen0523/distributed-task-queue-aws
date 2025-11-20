# libs/queue/redis_queue.py
import json
import time
from typing import Optional, Dict, Any
from libs.queue.task_priority import Priority
import redis


class RedisQueue:
    """
    A simple reliable Redis-backed task queue.

    Keys:
      - main queue:    tasks:default
      - retry queue:   tasks:retry  (sorted set: score = available_at timestamp)
      - dead-letter:   tasks:dlq
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        queue_key: str = "tasks:default",
        retry_key: str = "tasks:retry",
        dlq_key: str = "tasks:dlq",
    ):
        self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.queue_key = queue_key
        self.retry_key = retry_key
        self.dlq_key = dlq_key

    # ----------------------------------------------------------------------
    # Push new task
    # ----------------------------------------------------------------------
    def enqueue(self, task: Dict[str, Any], priority: str = Priority.MEDIUM) -> None:
        """Push a task to the queue (LPUSH so BRPOP pops in FIFO)."""
        payload = json.dumps(task)
        key = f"{self.queue_key}:{priority}"
        self.r.lpush(key, payload)

    # ----------------------------------------------------------------------
    # Blocking pop
    # ----------------------------------------------------------------------
    def dequeue(self, block: bool = True, timeout: int = 5) -> Optional[Dict[str, Any]]:
        """
        BRPOP:
          - If block=True: wait up to timeout seconds
          - If block=False: just check once (RPOP)
        """
        if block:
            result = self.r.brpop([self.queue_key], timeout=timeout)
            if result is None:
                return None  # timeout, no task
            _, payload = result
        else:
            payload = self.r.rpop(self.queue_key)
            if payload is None:
                return None

        try:
            return json.loads(payload)
        except Exception:
            return None

    def dequeue_priority(self, timeout=5):
        queues = [f"{self.queue_key}:{Priority.HIGH}", f"{self.queue_key}:{Priority.MEDIUM}", f"{self.queue_key}:{Priority.LOW}"]
        result = self.r.brpop(queues, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        return json.loads(raw)

    # ----------------------------------------------------------------------
    # Retry queue (sorted set)
    # available_at = now + backoff_seconds
    # ----------------------------------------------------------------------
    def push_retry(self, task: Dict[str, Any], delay_seconds: int) -> None:
        payload = json.dumps(task)
        available_at = int(time.time()) + delay_seconds
        self.r.zadd(self.retry_key, {payload: available_at})

    def pop_due_retry(self) -> Optional[Dict[str, Any]]:
        """
        Return tasks whose available_at <= now.

        This uses ZRANGEBYSCORE with limit=1 to only pop one at a time.
        """
        now = int(time.time())
        items = self.r.zrangebyscore(self.retry_key, 0, now, start=0, num=1)
        if not items:
            return None

        payload = items[0]
        # Remove from sorted set
        self.r.zrem(self.retry_key, payload)
        return json.loads(payload)

    # ----------------------------------------------------------------------
    # Dead Letter Queue
    # ----------------------------------------------------------------------
    def push_dlq(self, task: Dict[str, Any]):
        self.r.lpush(self.dlq_key, json.dumps(task))

    def list_dlq(self, limit: int = 50):
        """For API /dlq: show first N items"""
        items = self.r.lrange(self.dlq_key, 0, limit - 1)
        return [json.loads(i) for i in items]