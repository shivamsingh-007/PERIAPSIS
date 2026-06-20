from __future__ import annotations

import hashlib
import hmac
import time
import uuid

import pytest

from packages.notifications.slack_notifier import (
    SlackInteraction,
    SlackMessage,
    SlackNotifier,
    slack_notifier,
)


@pytest.fixture
def notifier():
    return SlackNotifier(
        webhook_url="https://hooks.slack.com/test",
        signing_secret="test-secret-key",
    )


@pytest.fixture
def notifier_no_secret():
    return SlackNotifier()


class TestSlackMessage:
    def test_create_message(self):
        msg = SlackMessage(channel="#general", text="Hello")
        assert msg.channel == "#general"
        assert msg.text == "Hello"
        assert msg.status == "pending"
        assert msg.blocks is None
        assert msg.thread_ts is None
        assert msg.slack_timestamp is None

    def test_message_defaults(self):
        msg = SlackMessage(channel="#test", text="t")
        assert msg.message_id is not None
        assert msg.created_at is not None
        assert msg.sent_at is None

    def test_with_blocks(self):
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hi"}}]
        msg = SlackMessage(channel="#test", text="t", blocks=blocks)
        assert msg.blocks == blocks

    def test_with_thread(self):
        msg = SlackMessage(channel="#test", text="t", thread_ts="123.456")
        assert msg.thread_ts == "123.456"


class TestSlackInteraction:
    def test_create_interaction(self):
        interaction = SlackInteraction(
            interaction_id="int-1",
            type="block_actions",
            user_id="U123",
            action_id="approve_run-1",
            action_value="run-1",
            message_ts="123.456",
            channel_id="C123",
        )
        assert interaction.user_id == "U123"
        assert interaction.action_id == "approve_run-1"


class TestSlackNotifier:
    def test_init(self, notifier):
        assert notifier.webhook_url == "https://hooks.slack.com/test"
        assert notifier.signing_secret == "test-secret-key"
        assert notifier._messages == []
        assert notifier._interactions == []
        assert notifier._approval_requests == {}

    def test_init_defaults(self, notifier_no_secret):
        assert notifier_no_secret.webhook_url == ""
        assert notifier_no_secret.signing_secret == ""

    @pytest.mark.asyncio
    async def test_send_approval_request(self, notifier):
        msg = await notifier.send_approval_request(
            channel="#approvals",
            run_id="run-1",
            goal="Deploy to production",
            risk_tier="high",
        )
        assert isinstance(msg, SlackMessage)
        assert msg.channel == "#approvals"
        assert "Deploy to production" in msg.text
        assert msg.blocks is not None
        assert len(msg.blocks) == 4
        assert len(notifier._messages) == 1

    @pytest.mark.asyncio
    async def test_send_approval_request_stores_data(self, notifier):
        await notifier.send_approval_request(
            channel="#test",
            run_id="run-2",
            goal="Run backup",
            risk_tier="low",
            requester="alice",
        )
        status = notifier.get_approval_status("run-2")
        assert status is not None
        assert status["channel"] == "#test"
        assert status["goal"] == "Run backup"
        assert status["risk_tier"] == "low"
        assert status["requester"] == "alice"
        assert status["status"] == "pending"

    @pytest.mark.asyncio
    async def test_send_approval_request_blocks_structure(self, notifier):
        msg = await notifier.send_approval_request(
            channel="#test",
            run_id="run-3",
            goal="Test goal",
            risk_tier="medium",
        )
        assert msg.blocks[0]["type"] == "header"
        assert msg.blocks[1]["type"] == "section"
        assert msg.blocks[2]["type"] == "section"
        assert msg.blocks[3]["type"] == "actions"
        buttons = msg.blocks[3]["elements"]
        assert len(buttons) == 2
        assert buttons[0]["action_id"] == "approve_run-3"
        assert buttons[1]["action_id"] == "reject_run-3"

    @pytest.mark.asyncio
    async def test_handle_interaction_approve(self, notifier):
        await notifier.send_approval_request(
            channel="#test", run_id="run-4", goal="g", risk_tier="low"
        )
        interaction = SlackInteraction(
            interaction_id="i1",
            type="block_actions",
            user_id="U99",
            action_id="approve_run-4",
            action_value="run-4",
            message_ts="123.456",
            channel_id="C123",
        )
        result = await notifier.handle_interaction(interaction)
        assert "approved" in result["text"]
        assert "U99" in result["text"]
        status = notifier.get_approval_status("run-4")
        assert status["status"] == "approved"
        assert status["approved_by"] == "U99"

    @pytest.mark.asyncio
    async def test_handle_interaction_reject(self, notifier):
        await notifier.send_approval_request(
            channel="#test", run_id="run-5", goal="g", risk_tier="low"
        )
        interaction = SlackInteraction(
            interaction_id="i2",
            type="block_actions",
            user_id="U88",
            action_id="reject_run-5",
            action_value="run-5",
            message_ts="123.456",
            channel_id="C123",
        )
        result = await notifier.handle_interaction(interaction)
        assert "rejected" in result["text"]
        status = notifier.get_approval_status("run-5")
        assert status["status"] == "rejected"
        assert status["rejected_by"] == "U88"

    @pytest.mark.asyncio
    async def test_handle_interaction_unknown_action(self, notifier):
        interaction = SlackInteraction(
            interaction_id="i3",
            type="block_actions",
            user_id="U77",
            action_id="unknown_action",
            action_value="val",
            message_ts="123.456",
            channel_id="C123",
        )
        result = await notifier.handle_interaction(interaction)
        assert "Unknown" in result["text"]

    @pytest.mark.asyncio
    async def test_handle_interaction_nonexistent_run(self, notifier):
        interaction = SlackInteraction(
            interaction_id="i4",
            type="block_actions",
            user_id="U66",
            action_id="approve_nonexistent",
            action_value="nonexistent",
            message_ts="123.456",
            channel_id="C123",
        )
        result = await notifier.handle_interaction(interaction)
        assert "Unknown" in result["text"]

    def test_verify_signature_no_secret(self, notifier_no_secret):
        assert notifier_no_secret.verify_signature("body", "123456", "sig") is True

    def test_verify_signature_valid(self, notifier):
        timestamp = str(int(time.time()))
        body = "test-body"
        base_string = f"v0:{timestamp}:{body}"
        expected = "v0=" + hmac.new(
            b"test-secret-key",
            base_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert notifier.verify_signature(body, timestamp, expected) is True

    def test_verify_signature_invalid(self, notifier):
        timestamp = str(int(time.time()))
        assert notifier.verify_signature("body", timestamp, "v0=bad") is False

    def test_verify_signature_expired(self, notifier):
        old_timestamp = str(int(time.time()) - 600)
        body = "test-body"
        base_string = f"v0:{old_timestamp}:{body}"
        expected = "v0=" + hmac.new(
            b"test-secret-key",
            base_string.encode(),
            hashlib.sha256,
        ).hexdigest()
        assert notifier.verify_signature(body, old_timestamp, expected) is False

    def test_get_approval_status_found(self, notifier):
        notifier._approval_requests["r1"] = {"status": "pending", "goal": "g"}
        result = notifier.get_approval_status("r1")
        assert result["status"] == "pending"

    def test_get_approval_status_not_found(self, notifier):
        assert notifier.get_approval_status("nonexistent") is None

    def test_get_pending_approvals(self, notifier):
        notifier._approval_requests["r1"] = {"status": "pending", "goal": "g1"}
        notifier._approval_requests["r2"] = {"status": "approved", "goal": "g2"}
        notifier._approval_requests["r3"] = {"status": "pending", "goal": "g3"}
        pending = notifier.get_pending_approvals()
        assert len(pending) == 2
        run_ids = [p["run_id"] for p in pending]
        assert "r1" in run_ids
        assert "r3" in run_ids

    def test_get_pending_approvals_empty(self, notifier):
        assert notifier.get_pending_approvals() == []

    def test_get_stats_empty(self, notifier):
        stats = notifier.get_stats()
        assert stats["total_messages"] == 0
        assert stats["total_interactions"] == 0
        assert stats["pending_approvals"] == 0

    def test_get_stats(self, notifier):
        notifier._messages.append(SlackMessage(channel="#t", text="m1"))
        notifier._messages.append(SlackMessage(channel="#t", text="m2"))
        notifier._approval_requests["r1"] = {"status": "pending"}
        stats = notifier.get_stats()
        assert stats["total_messages"] == 2
        assert stats["pending_approvals"] == 1
