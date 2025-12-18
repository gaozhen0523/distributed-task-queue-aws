# libs/metrics/prom_metrics.py
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# ---------------------------------------------------------
# 独立 registry，避免默认全局污染
# ---------------------------------------------------------
registry = CollectorRegistry(auto_describe=True)

# ---------------------------------------------------------
# Counters
# ---------------------------------------------------------
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

redis_connection_errors_total = Counter(
    "redis_connection_errors_total",
    "Total number of Redis connection "
    " command errors observed by workers or scheduler",
    registry=registry,
)

redis_abnormal_empty_total = Counter(
    "redis_abnormal_empty_total",
    "Total number of abnormal empty " "queue events (too many consecutive empty polls)",
    registry=registry,
)

worker_forced_fail_total = Counter(
    "worker_forced_fail_total",
    "Total number of intentionally simulated "
    "task failures (via FAIL_RATE or force_fail)",
    registry=registry,
)

# ---------------------------------------------------------
# Gauges
# ---------------------------------------------------------
queue_depth = Gauge(
    "queue_depth",
    "Current number of tasks in main queue",
    registry=registry,
)

# ---------------------------------------------------------
# Histograms
# ---------------------------------------------------------

# 任务执行耗时（worker）
task_processing_seconds = Histogram(
    "task_processing_seconds",
    "Time spent processing a task",
    buckets=[0.1, 0.2, 0.5, 1, 2, 5, 10],
    registry=registry,
)

# scheduler 扫描延迟
scheduler_scan_seconds = Histogram(
    "scheduler_scan_seconds",
    "Time spent scanning retry queue",
    buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1],
    registry=registry,
)

# API 处理耗时：POST /tasks, GET /dlq
api_latency_seconds = Histogram(
    "api_latency_seconds",
    "Latency for API requests",
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1],
    registry=registry,
)

retry_lag_seconds = Histogram(
    "retry_lag_seconds",
    "Lag between scheduled retry time and the "
    "actual time the task is moved back to main queue",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
    registry=registry,
)


# ---------------------------------------------------------
# Helper APIs
# ---------------------------------------------------------
def record_enqueue():
    task_enqueued_total.inc()


def record_fail():
    task_failed_total.inc()


def record_retry():
    task_retry_total.inc()


def update_queue_depth(size: int):
    queue_depth.set(size)


def observe_task_latency(seconds: float):
    task_processing_seconds.observe(seconds)


def observe_scheduler_latency(seconds: float):
    scheduler_scan_seconds.observe(seconds)


def observe_api_latency(seconds: float):
    api_latency_seconds.observe(seconds)


def record_redis_error():
    redis_connection_errors_total.inc()


def record_abnormal_empty():
    redis_abnormal_empty_total.inc()


def record_forced_fail():
    worker_forced_fail_total.inc()


def observe_retry_lag(seconds: float):
    retry_lag_seconds.observe(seconds)
