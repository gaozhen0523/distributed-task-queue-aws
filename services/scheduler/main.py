# services/scheduler/main.py
import asyncio
import logging
import time

from libs.queue.redis_queue import RedisQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("scheduler")


class SchedulerService:
    """
    Day 7: 延迟队列 / 周期任务雏形
    -------------------------------------------------
    Redis 结构:
      - main queue: tasks:default  (LIST)
      - retry queue: tasks:retry   (ZSET: score = available_at timestamp)
    -------------------------------------------------
    定期扫描 ZSET, 将到期任务移回主队列.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 6379, scan_interval: int = 2):
        self.queue = RedisQueue(host=host, port=port)
        self.scan_interval = scan_interval

    async def run(self):
        logger.info("🚀 Scheduler started (scan_interval=%ds)", self.scan_interval)
        while True:
            try:
                now = int(time.time())
                # 获取到期任务（最多 10 条，防止批量阻塞）
                ready_items = self.queue.r.zrangebyscore(self.queue.retry_key, 0, now, start=0, num=10)
                if ready_items:
                    logger.info("⏰ %d tasks ready for retry, moving to main queue...", len(ready_items))
                    for item in ready_items:
                        self.queue.r.zrem(self.queue.retry_key, item)
                        self.queue.r.lpush(self.queue.queue_key, item)
                await asyncio.sleep(self.scan_interval)
            except Exception as e:
                logger.exception("Scheduler loop error: %s", e)
                await asyncio.sleep(self.scan_interval)


async def main():
    scheduler = SchedulerService()
    await scheduler.run()


if __name__ == "__main__":
    asyncio.run(main())
