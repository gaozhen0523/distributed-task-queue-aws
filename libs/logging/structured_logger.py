# libs/logging/structured_logger.py
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


def _get_env() -> str:
    # 优先 ENVIRONMENT，其次 APP_ENV，默认 dev
    return os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "dev"


def _get_service(default: str = "app") -> str:
    # SERVICE_NAME 可以在 ECS Task Definition 里单独配置
    return os.getenv("SERVICE_NAME", default)


class StructuredLogger:
    """
    简单统一的 JSON 结构化日志封装。

    输出格式示例：
    {
      "timestamp": "...",
      "level": "INFO",
      "service": "rag-api-gateway",
      "env": "dev",
      "trace_id": "...",
      "correlation_id": "...",
      "message": "INGEST_ACCEPTED",
      "task_id": "...",
      "extra": {...}
    }
    """

    def __init__(self, base_logger: logging.Logger, service: str, env: str) -> None:
        self._logger = base_logger
        self._service = service
        self._env = env

    def _log(
        self,
        level: str,
        message: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        extra: dict[str, Any] | None = None,
        exc_info: bool = False,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": level,
            "service": self._service,
            "env": self._env,
            "message": message,
            "trace_id": trace_id,
            "correlation_id": correlation_id,
        }
        if extra:
            # 避免覆盖顶层字段
            record.setdefault("extra", {})
            record["extra"].update(extra)

        text = json.dumps(record, ensure_ascii=False)

        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
        }
        level_no = level_map.get(level.upper(), logging.INFO)
        self._logger.log(level_no, text, exc_info=exc_info)

    # 对外简单方法
    def info(
        self,
        message: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._log(
            "INFO",
            message,
            trace_id=trace_id,
            correlation_id=correlation_id,
            extra=extra,
        )

    def debug(
        self,
        message: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._log(
            "DEBUG",
            message,
            trace_id=trace_id,
            correlation_id=correlation_id,
            extra=extra,
        )

    def warning(
        self,
        message: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._log(
            "WARNING",
            message,
            trace_id=trace_id,
            correlation_id=correlation_id,
            extra=extra,
        )

    def error(
        self,
        message: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._log(
            "ERROR",
            message,
            trace_id=trace_id,
            correlation_id=correlation_id,
            extra=extra,
        )

    def exception(
        self,
        message: str,
        *,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        # 带堆栈的错误日志
        self._log(
            "ERROR",
            message,
            trace_id=trace_id,
            correlation_id=correlation_id,
            extra=extra,
            exc_info=True,
        )


def get_logger(default_service: str = "app") -> StructuredLogger:
    base_logger = logging.getLogger(default_service)
    service = _get_service(default_service)
    env = _get_env()
    return StructuredLogger(base_logger=base_logger, service=service, env=env)


# 默认导出一个 logger，SERVICE_NAME 未配置则使用 default_service
logger = get_logger()
