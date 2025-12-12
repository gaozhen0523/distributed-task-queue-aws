import json
import time
from typing import Any

import redis


class PriorityQueue:
    """
    三队列隔离设计：
      queue:high
      queue:medium
      queue:low
    以及对应的 retry / dlq：
      retry:high, retry:medium, retry:low
      dlq:high,   dlq:medium,   dlq:low
    """

    QUEUE_KEYS = {
        "high": "queue:high",
        "medium": "queue:medium",
        "low": "queue:low",
    }

    def __init__(self, host="127.0.0.1", port=6379, db=0, kind="medium"):
        if kind not in self.QUEUE_KEYS:
            raise ValueError("QUEUE_KIND must be high|medium|low")

        self.kind = kind
        self.r = redis.Redis(host=host, port=port, db=db)

        self.queue_key = self.QUEUE_KEYS[kind]
        self.retry_key = f"retry:{kind}"
        self.dlq_key = f"dlq:{kind}"

    # -------------------- 生产者 API --------------------
    def enqueue(self, task: dict[str, Any]):
        self.r.lpush(self.queue_key, json.dumps(task))

    # -------------------- 消费 API --------------------
    def dequeue(self, timeout=5):
        item = self.r.brpop(self.queue_key, timeout=timeout)
        if not item:
            return None
        _, raw = item
        return json.loads(raw)

    # -------------------- Retry API --------------------
    def push_retry(self, task: dict[str, Any], delay_seconds: int):
        score = int(time.time()) + delay_seconds
        self.r.zadd(self.retry_key, {json.dumps(task): score})

    def pop_due_retry(self):
        now = int(time.time())
        items = self.r.zrangebyscore(self.retry_key, 0, now, start=0, num=1)
        if not items:
            return None
        raw = items[0]
        self.r.zrem(self.retry_key, raw)
        return json.loads(raw)

    # -------------------- DLQ API --------------------
    def push_dlq(self, task: dict[str, Any]):
        self.r.lpush(self.dlq_key, json.dumps(task))
