# libs/queue/auto_scale.py


from libs.queue.redis_queue import RedisQueue
from libs.queue.task_priority import Priority


class AutoScaler:
    """
    Day 13: 仅协议，不做真实扩容。
    给 API 返回一个 autoscaling 的建议值。
    """

    def __init__(self):
        self.queue = RedisQueue()

    def get_queue_depths(self) -> dict[str, int]:
        """统计三个优先级队列的长度。"""
        r = self.queue.r
        base = self.queue.queue_key
        return {
            Priority.HIGH: r.llen(f"{base}:{Priority.HIGH}"),
            Priority.MEDIUM: r.llen(f"{base}:{Priority.MEDIUM}"),
            Priority.LOW: r.llen(f"{base}:{Priority.LOW}"),
        }

    def calc_desired_replicas(self, total: int) -> int:
        """
        简单伸缩规则（仅协议层，不做真实 ECS 操作）：
            <=20     -> 1
            <=100    -> 2
            <=500    -> 3
            <=2000   -> 4
            >2000    -> 6
        """
        if total <= 20:
            return 1
        if total <= 100:
            return 2
        if total <= 500:
            return 3
        if total <= 2000:
            return 4
        return 6

    def get_suggestion(self) -> dict:
        """返回 autoscaling 建议 JSON。"""
        depths = self.get_queue_depths()
        total = sum(depths.values())
        replicas = self.calc_desired_replicas(total)

        return {
            "queues": depths,
            "total_backlog": total,
            "desired_replicas": replicas,
            "rules": {
                "1": "total<=20",
                "2": "total<=100",
                "3": "total<=500",
                "4": "total<=2000",
                "6": "else",
            },
        }
