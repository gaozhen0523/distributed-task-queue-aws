# libs/queue/redis_queue.py
import json
import os
import time
from typing import Any

import redis
from dotenv import load_dotenv

from libs.queue.task_priority import Priority

load_dotenv(override=False)


class RedisQueue:
    """
    A simple reliable Redis-backed task queue.

    Keys:
      - main queue:    tasks:default
      - retry queue:   tasks:retry  (sorted set: score = available_at timestamp)
      - dead-letter:   tasks:dlq

      - idempotency key: idempotency:{biz_key} -> task_id
      - processing key:  processing:{biz_key}  -> task_id (short TTL)
    """

    def __init__(
        self,
        host: str = os.getenv("REDIS_HOST", "127.0.0.1"),
        port: int = os.getenv("REDIS_PORT", 6379),
        db: int = os.getenv("REDIS_DB", 0),
        queue_key: str = "tasks:default",
        retry_key: str = "tasks:retry",
        dlq_key: str = "tasks:dlq",
    ):
        self.r = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.queue_key = queue_key
        self.retry_key = retry_key
        self.dlq_key = dlq_key

        # 幂等 & 执行锁 key 前缀
        self.idempotency_prefix = "idempotency:"
        self.processing_prefix = "processing:"

    def get_processing(self, biz_key: str) -> str | None:
        if not biz_key:
            return None
        key = f"{self.processing_prefix}{biz_key}"
        val = self.r.get(key)
        return val if val else None

    # ----------------------------------------------------------------------
    # Push new task
    # ----------------------------------------------------------------------
    def enqueue(self, task: dict[str, Any], priority: str = Priority.MEDIUM) -> None:
        """Push a task to the queue (LPUSH so BRPOP pops in FIFO)."""
        payload = json.dumps(task)
        key = f"{self.queue_key}:{priority}"
        self.r.lpush(key, payload)

    # ----------------------------------------------------------------------
    # Blocking pop
    # ----------------------------------------------------------------------
    def dequeue(self, block: bool = True, timeout: int = 5) -> dict[str, Any] | None:
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
        queues = [
            f"{self.queue_key}:{Priority.HIGH}",
            f"{self.queue_key}:{Priority.MEDIUM}",
            f"{self.queue_key}:{Priority.LOW}",
        ]
        result = self.r.brpop(queues, timeout=timeout)
        if result is None:
            return None
        _, raw = result
        return json.loads(raw)

    # ----------------------------------------------------------------------
    # Retry queue (sorted set)
    # available_at = now + backoff_seconds
    # ----------------------------------------------------------------------
    def push_retry(self, task: dict[str, Any], delay_seconds: int) -> None:
        available_at = int(time.time()) + delay_seconds

        # 复制一份，避免直接修改调用方传入的 dict
        task_with_meta = dict(task)
        task_with_meta["next_available_at"] = available_at

        payload = json.dumps(task_with_meta)
        self.r.zadd(self.retry_key, {payload: available_at})

    def pop_due_retry(self) -> dict[str, Any] | None:
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
    def push_dlq(self, task: dict[str, Any]):
        self.r.lpush(self.dlq_key, json.dumps(task))

    def list_dlq(self, limit: int = 50):
        """For API /dlq: show first N items"""
        items = self.r.lrange(self.dlq_key, 0, limit - 1)
        return [json.loads(i) for i in items]

    # ----------------------------------------------------------------------
    # Idempotency helpers
    # ----------------------------------------------------------------------

    def get_idempotency(self, biz_key: str) -> str | None:
        """
        返回已存在的幂等 task_id，如不存在则为 None。
        """
        key = f"{self.idempotency_prefix}{biz_key}"
        val = self.r.get(key)
        return val if val else None

    def set_idempotency(
        self, biz_key: str, task_id: str, ttl_seconds: int = 24 * 3600
    ) -> None:
        """
        设置幂等 key，默认 TTL 24h。
        """
        key = f"{self.idempotency_prefix}{biz_key}"
        # ex 指定 TTL（秒）
        self.r.set(key, task_id, ex=ttl_seconds)

    # ----------------------------------------------------------------------
    # Processing lock helpers
    # ----------------------------------------------------------------------
    def start_processing(
        self, biz_key: str | None, task_id: str, ttl_seconds: int = 3600
    ) -> bool:
        """
        为 biz_key 设置处理锁：
          - 若 biz_key 为空，直接返回 True
          - 若 processing:{biz_key} 已存在，返回 False（表示已有任务在处理）
          - 否则 SETNX 并返回 True

        TTL 默认 1 小时，避免 Worker 崩溃时留下永久死锁。
        """
        if not biz_key:
            return True

        key = f"{self.processing_prefix}{biz_key}"
        # NX: only set if not exists
        ok = self.r.set(key, task_id, nx=True, ex=ttl_seconds)
        return bool(ok)

    def end_processing(self, biz_key: str | None) -> None:
        """
        处理结束后删除 processing 锁。
        """
        if not biz_key:
            return
        key = f"{self.processing_prefix}{biz_key}"
        self.r.delete(key)
