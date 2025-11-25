# services/worker/main.py
import json
import random
import time
import logging
from datetime import datetime

from libs.queue.redis_queue import RedisQueue

logger = logging.getLogger("worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
)


# ----------------------------------------------------------------------
# 模拟业务逻辑：80% 成功 / 20% 失败
# ----------------------------------------------------------------------
def execute_task(task: dict) -> bool:
    time.sleep(3)
    if task["payload"]["force_fail"]:
        return False
    return random.random() >= 0.2


# ----------------------------------------------------------------------
# 获取下一条任务（retry 优先级更高）
# ----------------------------------------------------------------------
def fetch_next_task(queue: RedisQueue):
    retry_task = queue.pop_due_retry()
    if retry_task:
        retry_task["_from"] = "retry"
        return retry_task

    normal_task = queue.dequeue_priority(timeout=5)
    if normal_task:
        normal_task["_from"] = "normal"
        return normal_task

    return None


# ----------------------------------------------------------------------
# 统一的任务执行逻辑（幂等 + 重试 + dlq）
# ----------------------------------------------------------------------
def run_task(task: dict, queue: RedisQueue):
    task_id = task.get("task_id")
    biz_key = task.get("biz_key")
    retry_count = task.get("retry_count", 0)
    max_retries = task.get("max_retries", 3)

    # -------------------------------
    # Step 0: acquire processing lock
    # -------------------------------
    acquired = queue.start_processing(biz_key, task_id)

    if not acquired:
        # 说明同一 biz_key 在执行，不能直接丢任务
        # → 小延迟后重试（保护任务不丢）
        logger.warning(
            f"[processing-lock-fail] biz_key={biz_key} task_id={task_id} -> retry in 1s"
        )
        queue.push_retry(task, delay_seconds=1)
        return

    try:
        # -------------------------------
        # Step 1: 真正执行
        # -------------------------------
        logger.info(
            f"[execute] task_id={task_id} retry_count={retry_count} from={task.get('_from')}"
        )
        ok = execute_task(task)

    finally:
        # Always release processing lock
        queue.end_processing(biz_key)

    # -------------------------------
    # Step 2: 执行成功
    # -------------------------------
    if ok:
        logger.info(f"[success] {task_id}")
        return

    # -------------------------------
    # Step 3: 执行失败 → 进入重试
    # -------------------------------
    task["retry_count"] = retry_count + 1

    if task["retry_count"] > max_retries:
        # 超过最大重试次数 → DLQ
        logger.error(f"[dlq] {task_id} after {task['retry_count']} attempts")
        queue.push_dlq(task)
        return

    # retry with exponential backoff
    delay = 2 ** task["retry_count"]
    logger.warning(f"[retry] {task_id} delay={delay}s")
    queue.push_retry(task, delay_seconds=delay)


# ----------------------------------------------------------------------
# Main worker loop
# ----------------------------------------------------------------------
def worker_loop():
    queue = RedisQueue()
    logger.info("Worker started. Waiting for tasks...")

    while True:
        task = fetch_next_task(queue)
        if not task:
            continue

        run_task(task, queue)


if __name__ == "__main__":
    worker_loop()
