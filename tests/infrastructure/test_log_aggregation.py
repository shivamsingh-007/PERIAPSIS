from __future__ import annotations
"""Tests for packages.infrastructure.log_aggregation - LogAggregator."""

from datetime import datetime, timedelta

import pytest

from packages.infrastructure.log_aggregation import AggregatedLog, LogAggregator


class TestLogAggregator:
    def setup_method(self):
        self.aggregator = LogAggregator()

    def test_ingest(self):
        log = self.aggregator.ingest("api", "info", "Request received")
        assert log.source == "api"
        assert log.level == "info"
        assert log.message == "Request received"

    def test_ingest_with_fields(self):
        log = self.aggregator.ingest("api", "info", "test", fields={"key": "value"})
        assert log.fields == {"key": "value"}

    def test_ingest_with_trace_id(self):
        log = self.aggregator.ingest("api", "info", "test", trace_id="abc123")
        assert log.trace_id == "abc123"

    def test_flush(self):
        self.aggregator.ingest("api", "info", "msg1")
        self.aggregator.ingest("api", "info", "msg2")
        count = self.aggregator.flush()
        assert count == 2
        assert len(self.aggregator._logs) == 2

    def test_query_all(self):
        self.aggregator.ingest("api", "info", "msg1")
        self.aggregator.ingest("worker", "error", "msg2")
        results = self.aggregator.query()
        assert len(results) == 2

    def test_query_by_source(self):
        self.aggregator.ingest("api", "info", "msg1")
        self.aggregator.ingest("worker", "info", "msg2")
        results = self.aggregator.query(source="api")
        assert len(results) == 1

    def test_query_by_level(self):
        self.aggregator.ingest("api", "info", "msg1")
        self.aggregator.ingest("api", "error", "msg2")
        results = self.aggregator.query(level="error")
        assert len(results) == 1

    def test_query_limit(self):
        for i in range(10):
            self.aggregator.ingest("api", "info", f"msg{i}")
        results = self.aggregator.query(limit=3)
        assert len(results) == 3

    def test_auto_flush(self):
        aggregator = LogAggregator()
        aggregator._flush_interval = 3
        for i in range(3):
            aggregator.ingest("api", "info", f"msg{i}")
        assert len(aggregator._logs) == 3

    def test_get_stats(self):
        self.aggregator.ingest("api", "info", "msg1")
        self.aggregator.ingest("worker", "info", "msg2")
        self.aggregator.flush()
        stats = self.aggregator.get_stats()
        assert stats["total_logs"] == 2
        assert "api" in stats["sources"]
        assert "worker" in stats["sources"]
