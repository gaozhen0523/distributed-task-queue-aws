# services/worker/main.py
import json
import random
import time
from datetime import datetime
import logging

from libs.queue.redis_queue import RedisQueue


logger = logging.getLogger("worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
)


# ----------------------------------------------------------------------
# 模拟任务执行：80% 成功，20% 失败
# ----------------------------------------------------------------------
def execute_task(task: dict) -> bool:
    """
    Return True if success, False if failed.
    """
    # 模拟随机失败
    if random.random() < 0.2:
        return False
    return True


# ----------------------------------------------------------------------
# Worker Loop
# ----------------------------------------------------------------------
def worker_loop():
    queue = RedisQueue()

    logger.info("Worker started. Waiting for tasks...")

    while True:

        # ---------------------------------------------------------------
        # Step 1: process retry tasks (due)
        # ---------------------------------------------------------------
        retry_task = queue.pop_due_retry()
        if retry_task:
            logger.info(f"[retry] task_id={retry_task.get('task_id')} retry_count={retry_task['retry_count']}")

            ok = execute_task(retry_task)
            if ok:
                logger.info(f"[success-after-retry] {retry_task['task_id']}")
            else:
                # still failed → check max retries
                retry_task["retry_count"] += 1
                if retry_task["retry_count"] > retry_task.get("max_retries", 3):
                    logger.error(f"[dlq] {retry_task['task_id']} after retries")
                    queue.push_dlq(retry_task)
                else:
                    delay = 2 ** retry_task["retry_count"]
                    logger.warning(f"[retry-again] {retry_task['task_id']} delay={delay}s")
                    queue.push_retry(retry_task, delay)
            continue  # go back to loop

        # ---------------------------------------------------------------
        # Step 2: normal queue blocking pop
        # ---------------------------------------------------------------
        task = queue.dequeue_priority(timeout=5)
        if task is None:
            # no new task
            continue

        logger.info(f"[processing] task_id={task.get('task_id')} retry_count={task['retry_count']}")

        ok = execute_task(task)
        if ok:
            logger.info(f"[success] {task['task_id']}")
            continue

        # fail
        task["retry_count"] += 1
        if task["retry_count"] > task.get("max_retries", 3):
            logger.error(f"[dlq] {task['task_id']}")
            queue.push_dlq(task)
        else:
            delay = 2 ** task["retry_count"]
            logger.warning(f"[retry] {task['task_id']} delay={delay}s")
            queue.push_retry(task, delay)


if __name__ == "__main__":
    worker_loop()