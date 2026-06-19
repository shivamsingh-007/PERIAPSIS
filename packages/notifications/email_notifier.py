from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("email_notifier")


class EmailMessage(BaseModel):
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    to: list[str]
    subject: str
    body: str
    html_body: str | None = None
    priority: str = "normal"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: datetime | None = None
    status: str = "pending"


class EmailNotifier:
    def __init__(self, smtp_host: str = "", smtp_port: int = 587):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self._queue: list[EmailMessage] = []
        self._sent: list[EmailMessage] = []
        self._templates: dict[str, dict] = {}

    def register_template(self, name: str, subject: str, body: str) -> None:
        self._templates[name] = {"subject": subject, "body": body}

    async def send_escalation(
        self,
        to: list[str],
        run_id: str,
        reason: str,
        details: str = "",
    ) -> EmailMessage:
        template = self._templates.get("escalation", {})
        subject = template.get("subject", f"Escalation Required: Run {run_id}")
        body = template.get("body", f"Run {run_id} requires human attention.\n\nReason: {reason}\n\n{details}")

        msg = EmailMessage(to=to, subject=subject, body=body)
        self._queue.append(msg)
        logger.info(f"Queued escalation email for run {run_id}")
        return msg

    async def send_notification(
        self,
        to: list[str],
        subject: str,
        body: str,
        priority: str = "normal",
    ) -> EmailMessage:
        msg = EmailMessage(to=to, subject=subject, body=body, priority=priority)
        self._queue.append(msg)
        return msg

    async def process_queue(self) -> int:
        sent_count = 0
        while self._queue:
            msg = self._queue.pop(0)
            msg.status = "sent"
            msg.sent_at = datetime.utcnow()
            self._sent.append(msg)
            sent_count += 1
            logger.info(f"Sent email to {msg.to}: {msg.subject}")

        return sent_count

    def get_pending(self) -> list[EmailMessage]:
        return list(self._queue)

    def get_sent(self, limit: int = 50) -> list[EmailMessage]:
        return self._sent[-limit:]

    def get_stats(self) -> dict:
        return {
            "pending": len(self._queue),
            "sent": len(self._sent),
            "templates": list(self._templates.keys()),
        }


email_notifier = EmailNotifier()
