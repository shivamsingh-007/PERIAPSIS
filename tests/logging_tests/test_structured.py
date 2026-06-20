from __future__ import annotations
"""Tests for packages.logging.structured - StructuredLogger, JSONFormatter."""

import json
import logging

import pytest

from packages.logging.structured import (
    JSONFormatter,
    StructuredLogger,
    get_logger,
    setup_structured_logging,
)


class TestJSONFormatter:
    def test_format_basic(self):
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Hello world", args=(), exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Hello world"

    def test_format_with_exception(self):
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test", level=logging.ERROR, pathname="test.py",
            lineno=1, msg="Error occurred", args=(), exc_info=exc_info,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"


class TestStructuredLogger:
    def setup_method(self):
        self.logger = StructuredLogger("test_logger")

    def test_info(self):
        # Should not raise
        self.logger.info("test message")

    def test_warning(self):
        self.logger.warning("warning message")

    def test_error(self):
        self.logger.error("error message")

    def test_debug(self):
        self.logger.debug("debug message")

    def test_critical(self):
        self.logger.critical("critical message")

    def test_log_run_start(self):
        self.logger.log_run_start("run1", "tenant1", "test goal")

    def test_log_run_complete(self):
        self.logger.log_run_complete("run1", "tenant1", "SUCCESS", 0.5)

    def test_log_step(self):
        self.logger.log_step("run1", "tenant1", 1, "research", True)

    def test_log_policy_check(self):
        self.logger.log_policy_check("run1", "tenant1", "allow", "low")

    def test_log_memory_write(self):
        self.logger.log_memory_write("tenant1", "fact", 0.8)

    def test_log_error(self):
        self.logger.log_error("something failed")

    def test_get_logger(self):
        logger = get_logger("my_module")
        assert isinstance(logger, StructuredLogger)
