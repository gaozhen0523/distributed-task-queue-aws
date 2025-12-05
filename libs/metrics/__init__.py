# libs/metrics/prom_metrics.py
from prometheus_client import CollectorRegistry, Counter, Gauge

# 独立 registry，避免默认全局污染
registry = CollectorRegistry(auto_describe=True)

# ---- Counters ----
task_enqueued_total = Counter(
    "task_enqueued_total",
    "Total number of tasks enqueued",
    registry=registry,
)
task_failed_total = Counter(
    "task_failed_total",
    "Total number of failed tasks",
    registry=registry,
)
task_retry_total = Counter(
    "task_retry_total",
    "Total number of retried tasks",
    registry=registry,
)

# ---- Gauges ----
queue_depth = Gauge(
    "queue_depth",
    "Current number of tasks in main queue",
    registry=registry,
)


# ---- Helper API ----
def record_enqueue():
    task_enqueued_total.inc()


def record_fail():
    task_failed_total.inc()


def record_retry():
    task_retry_total.inc()


def update_queue_depth(size: int):
    queue_depth.set(size)
