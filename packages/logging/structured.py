from __future__ import annotations

import json
import logging
import sys
import time
import traceback
from datetime import datetime
from typing import Any


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = record.tenant_id
        if hasattr(record, "run_id"):
            log_entry["run_id"] = record.run_id
        if hasattr(record, "trace_id"):
            log_entry["trace_id"] = record.trace_id

        return json.dumps(log_entry, default=str)


class StructuredLogger:
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JSONFormatter())
            self.logger.addHandler(handler)

    def _log(self, level: int, message: str, **kwargs):
        extra = {}
        for key in ["tenant_id", "run_id", "trace_id", "extra_data"]:
            if key in kwargs:
                extra[key] = kwargs.pop(key)
        extra["extra_data"] = kwargs if kwargs else extra.get("extra_data", {})

        self.logger.log(level, message, extra=extra)

    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)

    def log_run_start(self, run_id: str, tenant_id: str, goal: str):
        self.info("Run started", run_id=run_id, tenant_id=tenant_id, goal=goal)

    def log_run_complete(self, run_id: str, tenant_id: str, state: str, cost: float):
        self.info("Run completed", run_id=run_id, tenant_id=tenant_id, state=state, cost=cost)

    def log_step(self, run_id: str, tenant_id: str, step: int, action: str, success: bool):
        self.info("Step executed", run_id=run_id, tenant_id=tenant_id, step=step, action=action, success=success)

    def log_policy_check(self, run_id: str, tenant_id: str, decision: str, risk_tier: str):
        self.info("Policy checked", run_id=run_id, tenant_id=tenant_id, decision=decision, risk_tier=risk_tier)

    def log_memory_write(self, tenant_id: str, memory_type: str, confidence: float):
        self.info("Memory written", tenant_id=tenant_id, memory_type=memory_type, confidence=confidence)

    def log_error(self, error: str, **kwargs):
        self.error(f"Error: {error}", **kwargs)


def setup_structured_logging(level: int = logging.INFO):
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.root.handlers[0].setFormatter(JSONFormatter())


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)
