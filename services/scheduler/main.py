# services/scheduler/main.py
import asyncio
import json
import logging
import os
import time

from dotenv import load_dotenv

from libs.metrics.prom_metrics import (
    observe_scheduler_latency,
    record_retry,
)
from libs.queue.priority_queue import PriorityQueue

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("scheduler")


load_dotenv(override=False)


class SchedulerService:
    """
    Day 7 + Day 11:
    - ZSET 延迟队列扫描
    - metrics: scheduler_scan_seconds
    """

    def __init__(
        self,
        host: str = os.getenv("REDIS_HOST", "127.0.0.1"),
        port: int = os.getenv("REDIS_PORT", 6379),
        db: int = os.getenv("REDIS_DB", 0),
        scan_interval: int = 2,
    ):
        kind = os.getenv("QUEUE_KIND", "medium")
        self.queue = PriorityQueue(host=host, port=port, db=db, kind=kind)
        self.scan_interval = scan_interval

    async def run(self):
        logger.info("🚀 Scheduler started (scan_interval=%ds)", self.scan_interval)
        while True:
            try:
                t0 = time.time()

                ready_task = self.queue.pop_due_retry()

                if ready_task:
                    logger.info("task ready for retry -> main queue")
                    record_retry()
                    self.queue.r.lpush(self.queue.queue_key, json.dumps(ready_task))

                # observe scan latency
                observe_scheduler_latency(time.time() - t0)

                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                logger.exception("Scheduler loop error: %s", e)
                await asyncio.sleep(self.scan_interval)


async def main():
    scheduler = SchedulerService()
    await scheduler.run()


if __name__ == "__main__":
    asyncio.run(main())

# test1
