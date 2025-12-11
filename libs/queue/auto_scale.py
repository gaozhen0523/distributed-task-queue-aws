# libs/queue/auto_scale.py

from libs.queue.redis_queue import RedisQueue
from libs.queue.task_priority import Priority


class AutoScaler:
    """
    Day13: 仅协议层，不做真实扩容。
    Day23: 综合队列 backlog + CPU 百分比，给出副本数建议。

    注意：这里不直接调用 AWS API，仅返回建议值，实际扩缩容交给
    ECS Application Auto Scaling / 运维手动执行。
    """

    def __init__(self):
        self.queue = RedisQueue()

    def get_queue_depths(self) -> dict:
        """统计三个优先级队列的长度。"""
        r = self.queue.r
        base = self.queue.queue_key
        return {
            Priority.HIGH: r.llen(f"{base}:{Priority.HIGH}"),
            Priority.MEDIUM: r.llen(f"{base}:{Priority.MEDIUM}"),
            Priority.LOW: r.llen(f"{base}:{Priority.LOW}"),
        }

    def calc_backlog_replicas(self, total: int) -> int:
        """
        简单伸缩规则（仅根据 backlog）：
            total <= 20     -> 1
            total <= 100    -> 2
            total <= 500    -> 3
            total <= 2000   -> 4
            total >  2000   -> 6
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

    def calc_cpu_replicas(self, cpu_percent: float | None) -> int:
        """
        仅根据 CPU 的建议副本数。

        规则（可以写进文档方便面试讲解）：
            cpu < 40%      -> 1
            40% <= cpu <60 -> 2
            60% <= cpu <75 -> 3
            cpu >= 75%     -> 4
        """
        if cpu_percent is None:
            return 0  # 不参与决策

        if cpu_percent < 40:
            return 1
        if cpu_percent < 60:
            return 2
        if cpu_percent < 75:
            return 3
        return 4

    def get_suggestion(self, cpu_percent: float | None = None) -> dict:
        """
        返回 autoscaling 建议 JSON。

        - backlog_based_replicas：仅根据 backlog 的建议
        - cpu_based_replicas：仅根据 CPU 的建议（未提供则为 0）
        - desired_replicas：max(backlog_based, cpu_based)
        """
        depths = self.get_queue_depths()
        total = int(sum(depths.values()))

        backlog_replicas = self.calc_backlog_replicas(total)
        cpu_replicas = self.calc_cpu_replicas(cpu_percent)

        if cpu_percent is None:
            desired = backlog_replicas
            reason = f"cpu not provided, use backlog_only={backlog_replicas} replicas"
        else:
            desired = max(backlog_replicas, cpu_replicas)
            reason = (
                "combined backlog & cpu: "
                f"backlog_based={backlog_replicas}, "
                f"cpu_based={cpu_replicas}, "
                f"chosen={desired}"
            )

        return {
            "queues": depths,
            "total_backlog": total,
            "cpu_percent": cpu_percent,
            "backlog_based_replicas": backlog_replicas,
            "cpu_based_replicas": cpu_replicas,
            "desired_replicas": desired,
            "reason": reason,
            "rules": {
                "backlog": "total<=20→1, <=100→2, <=500→3, <=2000→4, else→6",
                "cpu": "cpu<40→1, 40-60→2, 60-75→3, >=75→4",
            },
            "recommended_aws_metric": {
                "QueueBacklog": total,
                "CpuPercent": cpu_percent,
            },
        }
