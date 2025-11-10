from libs.queue.models import Task, TaskStatus
import time

def test_task_retry_logic():
    t = Task({"job": 1}, max_retries=2)

    # 第一次失败 → RETRY
    t.mark_failed()
    assert t.status == TaskStatus.RETRY
    assert t.retry_count == 1

    # 第二次失败 → RETRY
    t.mark_failed()
    assert t.status == TaskStatus.RETRY
    assert t.retry_count == 2

    # 第三次失败 → FAILED
    t.mark_failed()
    assert t.status == TaskStatus.FAILED
    assert t.retry_count == 2  # 不再增加