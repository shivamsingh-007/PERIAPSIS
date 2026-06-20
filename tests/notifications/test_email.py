from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from packages.notifications.email_notifier import EmailMessage, EmailNotifier, email_notifier


@pytest.fixture
def notifier():
    return EmailNotifier(smtp_host="smtp.test.com", smtp_port=587)


@pytest.fixture
def sample_recipients():
    return ["user@example.com", "admin@example.com"]


class TestEmailMessage:
    def test_create_message(self):
        msg = EmailMessage(
            to=["a@b.com"],
            subject="Test",
            body="Hello",
        )
        assert msg.to == ["a@b.com"]
        assert msg.subject == "Test"
        assert msg.body == "Hello"
        assert msg.status == "pending"
        assert msg.priority == "normal"
        assert msg.html_body is None
        assert msg.sent_at is None

    def test_message_defaults(self):
        msg = EmailMessage(to=["a@b.com"], subject="s", body="b")
        assert msg.message_id is not None
        assert msg.created_at is not None

    def test_with_html_body(self):
        msg = EmailMessage(
            to=["a@b.com"],
            subject="s",
            body="text",
            html_body="<h1>HTML</h1>",
        )
        assert msg.html_body == "<h1>HTML</h1>"

    def test_with_priority(self):
        msg = EmailMessage(
            to=["a@b.com"],
            subject="s",
            body="b",
            priority="high",
        )
        assert msg.priority == "high"


class TestEmailNotifier:
    def test_init(self, notifier):
        assert notifier.smtp_host == "smtp.test.com"
        assert notifier.smtp_port == 587
        assert notifier._queue == []
        assert notifier._sent == []

    def test_init_defaults(self):
        n = EmailNotifier()
        assert n.smtp_host == ""
        assert n.smtp_port == 587

    def test_register_template(self, notifier):
        notifier.register_template(
            "welcome",
            subject="Welcome!",
            body="Hello {{name}}",
        )
        assert "welcome" in notifier._templates
        assert notifier._templates["welcome"]["subject"] == "Welcome!"

    def test_register_template_overwrite(self, notifier):
        notifier.register_template("t", subject="v1", body="b1")
        notifier.register_template("t", subject="v2", body="b2")
        assert notifier._templates["t"]["subject"] == "v2"

    @pytest.mark.asyncio
    async def test_send_escalation(self, notifier, sample_recipients):
        msg = await notifier.send_escalation(
            to=sample_recipients,
            run_id="run-123",
            reason="Budget exceeded",
            details="Cost was $500",
        )
        assert isinstance(msg, EmailMessage)
        assert msg.to == sample_recipients
        assert "run-123" in msg.body
        assert "Budget exceeded" in msg.body
        assert msg.status == "pending"
        assert len(notifier._queue) == 1

    @pytest.mark.asyncio
    async def test_send_escalation_with_template(self, notifier, sample_recipients):
        notifier.register_template(
            "escalation",
            subject="URGENT: Escalation Required",
            body="Escalation for run requires attention.",
        )
        msg = await notifier.send_escalation(
            to=sample_recipients,
            run_id="run-456",
            reason="Failed",
        )
        assert msg.subject == "URGENT: Escalation Required"
        assert msg.body == "Escalation for run requires attention."

    @pytest.mark.asyncio
    async def test_send_escalation_without_details(self, notifier):
        msg = await notifier.send_escalation(
            to=["a@b.com"],
            run_id="run-1",
            reason="test",
        )
        assert msg.status == "pending"

    @pytest.mark.asyncio
    async def test_send_notification(self, notifier):
        msg = await notifier.send_notification(
            to=["user@test.com"],
            subject="Hello",
            body="World",
        )
        assert msg.subject == "Hello"
        assert msg.body == "World"
        assert msg.priority == "normal"
        assert len(notifier._queue) == 1

    @pytest.mark.asyncio
    async def test_send_notification_with_priority(self, notifier):
        msg = await notifier.send_notification(
            to=["user@test.com"],
            subject="Urgent",
            body="Important",
            priority="high",
        )
        assert msg.priority == "high"

    @pytest.mark.asyncio
    async def test_process_queue_empty(self, notifier):
        count = await notifier.process_queue()
        assert count == 0
        assert notifier._sent == []

    @pytest.mark.asyncio
    async def test_process_queue(self, notifier):
        await notifier.send_notification(to=["a@b.com"], subject="s1", body="b1")
        await notifier.send_notification(to=["c@d.com"], subject="s2", body="b2")
        count = await notifier.process_queue()
        assert count == 2
        assert len(notifier._queue) == 0
        assert len(notifier._sent) == 2

    @pytest.mark.asyncio
    async def test_process_queue_sets_sent_status(self, notifier):
        msg = await notifier.send_notification(to=["a@b.com"], subject="s", body="b")
        assert msg.status == "pending"
        await notifier.process_queue()
        assert msg.status == "sent"
        assert msg.sent_at is not None

    def test_get_pending_empty(self, notifier):
        assert notifier.get_pending() == []

    def test_get_pending(self, notifier):
        notifier._queue.append(
            EmailMessage(to=["a@b.com"], subject="s", body="b")
        )
        pending = notifier.get_pending()
        assert len(pending) == 1

    def test_get_pending_returns_copy(self, notifier):
        notifier._queue.append(
            EmailMessage(to=["a@b.com"], subject="s", body="b")
        )
        pending = notifier.get_pending()
        pending.clear()
        assert len(notifier._queue) == 1

    def test_get_sent_empty(self, notifier):
        assert notifier.get_sent() == []

    def test_get_sent_with_limit(self, notifier):
        for i in range(5):
            msg = EmailMessage(to=["a@b.com"], subject=f"s{i}", body=f"b{i}")
            notifier._sent.append(msg)
        sent = notifier.get_sent(limit=3)
        assert len(sent) == 3

    def test_get_sent_all(self, notifier):
        for i in range(3):
            msg = EmailMessage(to=["a@b.com"], subject=f"s{i}", body=f"b{i}")
            notifier._sent.append(msg)
        assert len(notifier.get_sent()) == 3

    def test_get_stats_empty(self, notifier):
        stats = notifier.get_stats()
        assert stats["pending"] == 0
        assert stats["sent"] == 0
        assert stats["templates"] == []

    def test_get_stats(self, notifier):
        notifier._queue.append(EmailMessage(to=["a@b.com"], subject="s", body="b"))
        notifier._sent.append(EmailMessage(to=["a@b.com"], subject="s", body="b"))
        notifier.register_template("t1", subject="s", body="b")
        stats = notifier.get_stats()
        assert stats["pending"] == 1
        assert stats["sent"] == 1
        assert "t1" in stats["templates"]

    @pytest.mark.asyncio
    async def test_multiple_escalations_queue(self, notifier):
        for i in range(3):
            await notifier.send_escalation(
                to=["a@b.com"],
                run_id=f"run-{i}",
                reason=f"reason-{i}",
            )
        assert len(notifier._queue) == 3
