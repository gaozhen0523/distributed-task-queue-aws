#!/usr/bin/env python3
"""
Benchmark: Distributed task queue throughput vs worker replicas.

This script orchestrates multiple runs of scripts/load_test.py against
the public dist API:

  - DIST_API_URL (default: ALB /tasks endpoint)
  - For worker_counts in [1, 2, 4, 8] (configurable via QUEUE_WORKERS env)
    - (Optionally) update ECS service desired_count via AWS CLI
    - Run load_test.py with computed concurrency
    - Parse the summary (RPS, p50, p95, p99)

Outputs:
  benchmarks/dist/results/workers_{n}.json
  benchmarks/dist/plots/qps_vs_workers.png
"""

import os
import subprocess
import time
import json
from pathlib import Path
from typing import Dict, Any, List

import matplotlib.pyplot as plt

# ================================
# Config
# ================================

REPO_ROOT = Path(__file__).resolve().parents[2]

DIST_API_URL = os.getenv(
    "DIST_API_URL",
    "http://dist-api-alb-863248708.us-east-1.elb.amazonaws.com/tasks",
)

WORKERS_STR = os.getenv("QUEUE_WORKERS", "1,2,4,8")
WORKER_COUNTS = [int(x) for x in WORKERS_STR.split(",") if x.strip()]

CONCURRENCY_PER_WORKER = int(os.getenv("QUEUE_CONCURRENCY_PER_WORKER", "20"))
DURATION = int(os.getenv("QUEUE_DURATION", "15"))

# ECS optional config
ECS_CLUSTER = os.getenv("QUEUE_ECS_CLUSTER")  # e.g. dist-cluster
ECS_SERVICE = os.getenv("QUEUE_ECS_SERVICE")  # e.g. dist-worker-service
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

OUT_DIR = REPO_ROOT / "benchmarks" / "dist"
RESULT_DIR = OUT_DIR / "results"
PLOT_DIR = OUT_DIR / "plots"

RESULT_DIR.mkdir(parents=True, exist_ok=True)
PLOT_DIR.mkdir(parents=True, exist_ok=True)


# ================================
# Helpers
# ================================


def _run_cmd(cmd: List[str]) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=False, capture_output=True, text=True)


def _scale_ecs_desired_count(workers: int) -> None:
    """
    Optionally scale ECS service if ECS_CLUSTER & ECS_SERVICE are provided.
    Uses AWS CLI: aws ecs update-service + aws ecs wait services-stable
    """
    if not ECS_CLUSTER or not ECS_SERVICE:
        print(
            f"⚠️  ECS_CLUSTER / ECS_SERVICE not set, "
            f"please manually scale worker service to {workers} replicas."
        )
        input("    After scaling to the desired count, press Enter to continue...")
        return

    print(
        f"🔧 Scaling ECS service {ECS_SERVICE} in cluster {ECS_CLUSTER} "
        f"to desiredCount={workers} ..."
    )

    update_cmd = [
        "aws",
        "ecs",
        "update-service",
        "--cluster",
        ECS_CLUSTER,
        "--service",
        ECS_SERVICE,
        "--desired-count",
        str(workers),
        "--region",
        AWS_REGION,
    ]
    res = _run_cmd(update_cmd)
    if res.returncode != 0:
        print("❌ Failed to update ECS service desired count:")
        print(res.stderr)
        input("Please fix the issue / scale manually, then press Enter to continue...")
        return

    wait_cmd = [
        "aws",
        "ecs",
        "wait",
        "services-stable",
        "--cluster",
        ECS_CLUSTER,
        "--services",
        ECS_SERVICE,
        "--region",
        AWS_REGION,
    ]
    print("⏳ Waiting for ECS service to become stable ...")
    res_wait = _run_cmd(wait_cmd)
    if res_wait.returncode != 0:
        print("⚠️ aws ecs wait services-stable returned non-zero. Proceeding anyway.")
    else:
        print("✅ ECS service is stable.")


def _parse_load_test_output(stdout: str) -> Dict[str, Any]:
    """
    Parse the summary part from scripts/load_test.py stdout.

    Expected lines (examples):

    === Load Test Summary ===
    Total time: 10.02s
    Total requests: 1234
      Success: 1200
      Fail:    34
      RPS:     123.45 req/s

    Latency (ms):
      avg = 10.23
      p50 = 8.76
      p95 = 20.12
      p99 = 35.67
    """
    summary: Dict[str, Any] = {}

    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("Total time:"):
            # "Total time: 10.02s"
            try:
                val = line.split("Total time:", 1)[1].strip()
                summary["total_time_s"] = float(val.rstrip("s"))
            except Exception:
                pass
        elif line.startswith("Total requests:"):
            try:
                val = line.split("Total requests:", 1)[1].strip()
                summary["total_requests"] = int(val)
            except Exception:
                pass
        elif line.startswith("Success:"):
            try:
                val = line.split("Success:", 1)[1].strip()
                summary["success"] = int(val)
            except Exception:
                pass
        elif line.startswith("Fail:"):
            try:
                val = line.split("Fail:", 1)[1].strip()
                summary["fail"] = int(val)
            except Exception:
                pass
        elif line.startswith("RPS:"):
            # "RPS:     123.45 req/s"
            try:
                val = line.split("RPS:", 1)[1].strip().split()[0]
                summary["rps"] = float(val)
            except Exception:
                pass
        elif line.startswith("avg ="):
            try:
                val = line.split("avg =", 1)[1].strip()
                summary["latency_avg_ms"] = float(val)
            except Exception:
                pass
        elif line.startswith("p50 ="):
            try:
                val = line.split("p50 =", 1)[1].strip()
                summary["latency_p50_ms"] = float(val)
            except Exception:
                pass
        elif line.startswith("p95 ="):
            try:
                val = line.split("p95 =", 1)[1].strip()
                summary["latency_p95_ms"] = float(val)
            except Exception:
                pass
        elif line.startswith("p99 ="):
            try:
                val = line.split("p99 =", 1)[1].strip()
                summary["latency_p99_ms"] = float(val)
            except Exception:
                pass

    return summary


def _run_load_test(concurrency: int, duration: int) -> Dict[str, Any]:
    """
    Invoke scripts/load_test.py via subprocess and parse summary.
    """
    script_path = REPO_ROOT / "scripts" / "load_test.py"

    cmd = [
        "python",
        str(script_path),
        "--url",
        DIST_API_URL,
        "--concurrency",
        str(concurrency),
        "--duration",
        str(duration),
    ]

    print(
        f"🚀 Running load_test.py with concurrency={concurrency}, duration={duration}s"
    )
    res = _run_cmd(cmd)

    if res.returncode != 0:
        print("⚠️ load_test.py returned non-zero code")
        print(res.stderr)

    summary = _parse_load_test_output(res.stdout)
    summary["raw_stdout"] = res.stdout
    summary["return_code"] = res.returncode

    return summary


# ================================
# Main
# ================================


def main():
    all_results: List[Dict[str, Any]] = []

    print(
        f"Starting queue benchmark on {DIST_API_URL}\n"
        f"  Worker counts: {WORKER_COUNTS}\n"
        f"  Concurrency per worker: {CONCURRENCY_PER_WORKER}\n"
        f"  Duration per run: {DURATION}s\n"
    )

    for workers in WORKER_COUNTS:
        print(f"\n=== Benchmark for workers={workers} ===")

        _scale_ecs_desired_count(workers)

        # 给 ECS 一点时间让实例完全 ready（健康检查通过）
        print("⏳ Sleeping 10s to let workers warm up ...")
        time.sleep(10)

        concurrency = workers * CONCURRENCY_PER_WORKER
        summary = _run_load_test(concurrency, DURATION)

        summary["workers"] = workers
        summary["concurrency"] = concurrency

        out_file = RESULT_DIR / f"workers_{workers}.json"
        out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"✅ Saved result → {out_file}")

        all_results.append(summary)

    if not all_results:
        print("\n⚠️ No results collected. Please check configuration.")
        return

    # -------- Plot QPS vs workers --------
    xs = []
    ys = []

    for r in all_results:
        w = r.get("workers")
        qps = r.get("rps")
        if w is None or qps is None:
            continue
        xs.append(w)
        ys.append(qps)

    if xs and ys:
        plt.figure(figsize=(8, 5))
        plt.plot(xs, ys, marker="o")
        plt.xlabel("Worker replicas")
        plt.ylabel("Throughput (req/s)")
        plt.title("Distributed Queue Throughput vs Worker Replicas")
        plt.grid(True)

        out_path = PLOT_DIR / "qps_vs_workers.png"
        plt.savefig(out_path, dpi=160)
        print(f"📈 Saved QPS plot → {out_path}")
    else:
        print("\n⚠️ Not enough data points to plot QPS vs workers.")

    print("\n🎉 Queue benchmark finished.")


if __name__ == "__main__":
    main()
