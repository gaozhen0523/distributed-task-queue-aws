# services/worker/main.py
import logging
import os
import random
import time

import redis
from dotenv import load_dotenv

from libs.metrics.prom_metrics import (
    observe_task_latency,
    record_abnormal_empty,
    record_fail,
    record_forced_fail,
    record_redis_error,
    record_retry,
)
from libs.queue.priority_queue import PriorityQueue

logger = logging.getLogger("worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
)

load_dotenv(override=False)

# ----------------------------------------------------------------------
# 失败注入开关：使用环境变量控制模拟失败比例（0.0 ~ 1.0）
# ----------------------------------------------------------------------
try:
    FAIL_RATE = float(os.getenv("FAIL_RATE", "0.2"))
    if FAIL_RATE < 0.0 or FAIL_RATE > 1.0:
        FAIL_RATE = 0.2
except ValueError:
    FAIL_RATE = 0.2


# ----------------------------------------------------------------------
# 模拟业务逻辑：80% 成功 / 20% 失败
# ----------------------------------------------------------------------
def execute_task(task: dict) -> bool:
    t = random.uniform(0.005, 0.02)  # 5ms ~ 20ms
    time.sleep(t)

    # 显式强制失败（用于测试）
    if task["payload"].get("force_fail"):
        record_forced_fail()
        return False

    # 按 FAIL_RATE 注入随机失败
    if random.random() < FAIL_RATE:
        record_forced_fail()
        return False

    return True


# ----------------------------------------------------------------------
# 获取下一条任务（retry 优先级更高）
# ----------------------------------------------------------------------
def fetch_next_task(queue: PriorityQueue):
    retry_task = queue.pop_due_retry()
    if retry_task:
        retry_task["_from"] = "retry"
        return retry_task

    normal_task = queue.dequeue(timeout=5)
    if normal_task:
        normal_task["_from"] = "normal"
        return normal_task

    return None


# ----------------------------------------------------------------------
# 统一的任务执行逻辑（幂等 + 重试 + dlq）
# ----------------------------------------------------------------------
def run_task(task: dict, queue: PriorityQueue):
    task_id = task.get("task_id")
    retry_count = task.get("retry_count", 0)
    max_retries = task.get("max_retries", 3)

    biz_key = task.get("biz_key")

    # Step 0: acquire processing lock
    acquired = queue.start_processing(biz_key, task_id)
    if not acquired:
        logger.warning(
            f"[processing-lock] biz_key={biz_key} already processing, retry in 1s"
        )
        queue.push_retry(task, delay_seconds=1)
        return
    # -------------------------------
    # Step 1: 执行任务 + metrics(耗时)
    # -------------------------------
    t0 = time.time()
    try:
        logger.info(
            f"[execute] task_id={task_id} retry_count={retry_count} "
            f"from={task.get('_from')}"
        )
        ok = execute_task(task)
    finally:
        queue.end_processing(biz_key)

    # Histogram 记录任务耗时
    observe_task_latency(time.time() - t0)

    # -------------------------------
    # Step 2: 成功
    # -------------------------------
    if ok:
        logger.info(f"[success] {task_id}")
        return

    # -------------------------------
    # Step 3: 失败 → 重试或 DLQ
    # -------------------------------
    record_fail()  # 记录失败数
    task["retry_count"] = retry_count + 1

    if task["retry_count"] > max_retries:
        logger.error(f"[dlq] {task_id} after {task['retry_count']} attempts")
        queue.push_dlq(task)
        return

    # retry
    delay = 2 ** task["retry_count"]
    logger.warning(f"[retry] {task_id} delay={delay}s")
    record_retry()  # 🔥 记录 retry 次数
    queue.push_retry(task, delay_seconds=delay)


# ----------------------------------------------------------------------
# Main worker loop
# ----------------------------------------------------------------------
def worker_loop():
    kind = os.getenv("QUEUE_KIND", "medium")
    # queue = RedisQueue()
    queue = PriorityQueue(kind=kind)
    logger.info(
        "Worker started. Waiting for tasks... (kind=%s, FAIL_RATE=%.2f)",
        kind,
        FAIL_RATE,
    )

    empty_polls = 0  # 连续空轮询次数

    while True:
        try:
            task = fetch_next_task(queue)
        except redis.exceptions.RedisError as e:
            logger.exception("[redis-error] Worker Redis operation failed: %s", e)
            record_redis_error()
            time.sleep(1.0)
            continue

        if not task:
            empty_polls += 1
            if empty_polls >= 10:
                logger.warning("[empty-queue] no task fetched for 10 consecutive polls")
                record_abnormal_empty()
                empty_polls = 0
            continue

        # 一旦有任务，重置空轮询计数
        empty_polls = 0
        run_task(task, queue)


if __name__ == "__main__":
    worker_loop()

# test1
