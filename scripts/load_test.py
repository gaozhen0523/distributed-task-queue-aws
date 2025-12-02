# scripts/load_test.py
"""
Simple load test tool for distributed-task-queue-aws.

Usage examples:

  # 10 秒内尽可能打满 100 并发（按 CPU 分成多进程）
  python scripts/load_test.py --concurrency 100 --duration 10

  # 指定 API 地址和 biz_key
  python scripts/load_test.py --url http://localhost:8000/tasks --biz-key load_test
"""

import argparse
import asyncio
import time
import random
import statistics
from typing import Dict, Any, List, Tuple
import multiprocessing as mp
import uuid

import httpx

port = 8001

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load test for task queue API")
    parser.add_argument(
        "--url",
        type=str,
        default=f"http://localhost:{port}/tasks",
        help="Task submit API endpoint",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=50,
        help="Total concurrent clients across all processes",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=10,
        help="Duration of the test in seconds",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=mp.cpu_count(),
        help="Number of processes to spawn (default: cpu_count)",
    )
    parser.add_argument(
        "--biz-key",
        type=str,
        default="load_test",
        help="biz_key to use when submitting tasks",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# 单进程内：异步 worker 逻辑
# ---------------------------------------------------------------------------

async def _load_worker(
    worker_id: int,
    url: str,
    biz_key: str,
    duration: int,
    timeout: float,
) -> Dict[str, Any]:
    """
    一个协程 worker：在指定 duration 内不断向 /tasks 发送请求。
    """
    start_ts = time.time()
    latencies: List[float] = []
    success = 0
    fail = 0

    async with httpx.AsyncClient(timeout=timeout) as client:
        while time.time() - start_ts < duration:
            seq = random.randint(1, 10_000_000)
            payload = {"payload": {"seq": seq}}

            biz_key = f"{uuid.uuid4().hex[:8]}"
            t0 = time.perf_counter()
            try:
                resp = await client.post(
                    url,
                    params={"biz_key": biz_key},
                    json=payload,
                )
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000.0)  # ms

                if 200 <= resp.status_code < 300:
                    success += 1
                else:
                    fail += 1
            except Exception:
                # 超时 / 连接错误等都算失败
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000.0)
                fail += 1

    return {
        "latencies": latencies,
        "success": success,
        "fail": fail,
    }


async def _run_in_process(
    proc_id: int,
    url: str,
    biz_key: str,
    duration: int,
    timeout: float,
    concurrency: int,
) -> Dict[str, Any]:
    """
    单个进程入口：启动多个协程 worker，并汇总结果。
    """
    tasks = [
        asyncio.create_task(
            _load_worker(i, url, biz_key, duration, timeout)
        )
        for i in range(concurrency)
    ]
    results = await asyncio.gather(*tasks)

    all_latencies: List[float] = []
    success = 0
    fail = 0

    for r in results:
        all_latencies.extend(r["latencies"])
        success += r["success"]
        fail += r["fail"]

    return {
        "latencies": all_latencies,
        "success": success,
        "fail": fail,
    }


def _process_entry(args: Tuple[int, str, str, int, float, int]) -> Dict[str, Any]:
    """
    multiprocessing 用的包装函数。
    """
    proc_id, url, biz_key, duration, timeout, concurrency = args
    return asyncio.run(
        _run_in_process(
            proc_id=proc_id,
            url=url,
            biz_key=biz_key,
            duration=duration,
            timeout=timeout,
            concurrency=concurrency,
        )
    )


# ---------------------------------------------------------------------------
# 汇总 & 百分位工具
# ---------------------------------------------------------------------------

def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[int(k)]
    d0 = values_sorted[f] * (c - k)
    d1 = values_sorted[c] * (k - f)
    return d0 + d1


def main() -> None:
    args = parse_args()

    total_concurrency = max(1, args.concurrency)
    num_workers = max(1, args.workers)
    # 每个进程的协程数量，尽量平均
    base = total_concurrency // num_workers
    extra = total_concurrency % num_workers

    per_proc_concurrency = []
    for i in range(num_workers):
        c = base + (1 if i < extra else 0)
        if c > 0:
            per_proc_concurrency.append(c)

    if not per_proc_concurrency:
        per_proc_concurrency = [1]
        num_workers = 1

    print(
        f"Starting load test: url={args.url}, "
        f"biz_key={args.biz_key}, duration={args.duration}s, "
        f"total_concurrency={total_concurrency}, "
        f"processes={len(per_proc_concurrency)}"
    )

    mp.set_start_method("spawn", force=True)

    proc_args = [
        (
            i,
            args.url,
            args.biz_key,
            args.duration,
            args.timeout,
            per_proc_concurrency[i],
        )
        for i in range(len(per_proc_concurrency))
    ]

    t_start = time.time()
    with mp.Pool(processes=len(per_proc_concurrency)) as pool:
        results = pool.map(_process_entry, proc_args)
    t_end = time.time()

    all_latencies: List[float] = []
    total_success = 0
    total_fail = 0

    for r in results:
        all_latencies.extend(r["latencies"])
        total_success += r["success"]
        total_fail += r["fail"]

    total_requests = total_success + total_fail
    elapsed = t_end - t_start
    rps = total_requests / elapsed if elapsed > 0 else 0.0

    print("\n=== Load Test Summary ===")
    print(f"Total time: {elapsed:.2f}s")
    print(f"Total requests: {total_requests}")
    print(f"  Success: {total_success}")
    print(f"  Fail:    {total_fail}")
    print(f"  RPS:     {rps:.2f} req/s")

    if all_latencies:
        p50 = _percentile(all_latencies, 50)
        p95 = _percentile(all_latencies, 95)
        p99 = _percentile(all_latencies, 99)
        avg = statistics.mean(all_latencies)

        print("\nLatency (ms):")
        print(f"  avg = {avg:.2f}")
        print(f"  p50 = {p50:.2f}")
        print(f"  p95 = {p95:.2f}")
        print(f"  p99 = {p99:.2f}")
    else:
        print("\nNo latencies recorded (no requests?)")


if __name__ == "__main__":
    main()
