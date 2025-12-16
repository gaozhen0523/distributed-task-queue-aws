import json
import time
from typing import Any

import redis

queue_key: str = "tasks:default"
retry_key: str = "tasks:retry"
dlq_key: str = "tasks:dlq"


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
        "high": f"{queue_key}:high",
        "medium": f"{queue_key}:medium",
        "low": f"{queue_key}:low",
    }

    def __init__(self, host="127.0.0.1", port=6379, db=0, kind="medium"):
        if kind not in self.QUEUE_KEYS:
            raise ValueError("QUEUE_KIND must be high|medium|low")

        self.kind = kind
        self.r = redis.Redis(host=host, port=port, db=db)

        self.queue_key = self.QUEUE_KEYS[kind]
        self.retry_key = f"{retry_key}:{kind}"
        self.dlq_key = f"{dlq_key}:{kind}"
        self.processing_prefix = "processing:"
        self.idempotency_prefix = "idempotency:"

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

    # -------------------- Processing Lock API --------------------
    def start_processing(
        self, biz_key: str | None, task_id: str, ttl_seconds: int = 3600
    ) -> bool:
        """
        避免同一个 biz_key 的任务并发执行：
        - 如果 biz_key 为空，直接返回 True
        - 否则在 Redis 设置 key processing:{biz_key} = task_id
          使用 NX（不存在才创建）+ TTL 防止死锁
        """
        if not biz_key:
            return True

        key = f"{self.processing_prefix}{biz_key}"
        ok = self.r.set(key, task_id, nx=True, ex=ttl_seconds)
        return bool(ok)

    def end_processing(self, biz_key: str | None):
        """
        完成后删除 processing 锁
        """
        if not biz_key:
            return
        key = f"{self.processing_prefix}{biz_key}"
        self.r.delete(key)

    def get_processing(self, biz_key: str) -> str | None:
        """
        查询 processing 状态：
        任务 API 在 /tasks 时会使用它判断是否需要返回 reused=True
        """
        key = f"{self.processing_prefix}{biz_key}"
        val = self.r.get(key)
        return val if val else None
