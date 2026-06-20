from __future__ import annotations

import pytest

from packages.fleet.ruflo_client import (
    RufloClient,
    RufloMCPMessage,
    RufloToolCall,
    RufloToolResult,
)


class TestRufloToolCall:
    def test_create_tool_call(self):
        call = RufloToolCall(
            name="read_file",
            arguments={"path": "/tmp/test.py"},
            id="call-1",
        )
        assert call.name == "read_file"
        assert call.arguments == {"path": "/tmp/test.py"}


class TestRufloToolResult:
    def test_create_result(self):
        result = RufloToolResult(
            tool_call_id="call-1",
            content="file contents",
            is_error=False,
        )
        assert result.content == "file contents"
        assert result.is_error is False

    def test_error_result(self):
        result = RufloToolResult(
            tool_call_id="call-1",
            content="permission denied",
            is_error=True,
        )
        assert result.is_error is True


class TestRufloMCPMessage:
    def test_create_message(self):
        msg = RufloMCPMessage(
            jsonrpc="2.0",
            id=1,
            method="tools/list",
        )
        assert msg.jsonrpc == "2.0"
        assert msg.method == "tools/list"

    def test_message_defaults(self):
        msg = RufloMCPMessage(jsonrpc="2.0", id=1, method="test")
        assert msg.params is None
        assert msg.result is None
        assert msg.error is None


class TestRufloClient:
    def test_client_init(self):
        client = RufloClient()
        assert client is not None

    def test_client_not_started(self):
        client = RufloClient()
        assert client._process is None
