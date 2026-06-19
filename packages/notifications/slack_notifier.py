from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("slack_notifier")


class SlackMessage(BaseModel):
    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    channel: str
    text: str
    blocks: list[dict] | None = None
    thread_ts: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: datetime | None = None
    status: str = "pending"
    slack_timestamp: str | None = None


class SlackInteraction(BaseModel):
    interaction_id: str
    type: str
    user_id: str
    action_id: str
    action_value: str
    message_ts: str
    channel_id: str


class SlackNotifier:
    def __init__(self, webhook_url: str = "", signing_secret: str = ""):
        self.webhook_url = webhook_url
        self.signing_secret = signing_secret
        self._messages: list[SlackMessage] = []
        self._interactions: list[SlackInteraction] = []
        self._approval_requests: dict[str, dict] = {}

    async def send_approval_request(
        self,
        channel: str,
        run_id: str,
        goal: str,
        risk_tier: str,
        requester: str = "system",
    ) -> SlackMessage:
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Approval Required"},
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Run:*\n{run_id}"},
                    {"type": "mrkdwn", "text": f"*Risk:*\n{risk_tier}"},
                ],
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Goal:*\n{goal}"},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "action_id": f"approve_{run_id}",
                        "value": run_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "action_id": f"reject_{run_id}",
                        "value": run_id,
                    },
                ],
            },
        ]

        msg = SlackMessage(
            channel=channel,
            text=f"Approval required for run {run_id}: {goal}",
            blocks=blocks,
        )
        self._messages.append(msg)

        self._approval_requests[run_id] = {
            "channel": channel,
            "goal": goal,
            "risk_tier": risk_tier,
            "requester": requester,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending",
        }

        logger.info(f"Sent approval request for run {run_id} to {channel}")
        return msg

    async def handle_interaction(self, interaction: SlackInteraction) -> dict:
        self._interactions.append(interaction)

        if interaction.action_id.startswith("approve_"):
            run_id = interaction.action_value
            if run_id in self._approval_requests:
                self._approval_requests[run_id]["status"] = "approved"
                self._approval_requests[run_id]["approved_by"] = interaction.user_id
                return {"text": f"Run {run_id} approved by {interaction.user_id}"}

        elif interaction.action_id.startswith("reject_"):
            run_id = interaction.action_value
            if run_id in self._approval_requests:
                self._approval_requests[run_id]["status"] = "rejected"
                self._approval_requests[run_id]["rejected_by"] = interaction.user_id
                return {"text": f"Run {run_id} rejected by {interaction.user_id}"}

        return {"text": "Unknown action"}

    def verify_signature(self, body: str, timestamp: str, signature: str) -> bool:
        if not self.signing_secret:
            return True

        if abs(time.time() - float(timestamp)) > 300:
            return False

        base_string = f"v0:{timestamp}:{body}"
        expected = "v0=" + hmac.new(
            self.signing_secret.encode(),
            base_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def get_approval_status(self, run_id: str) -> dict | None:
        return self._approval_requests.get(run_id)

    def get_pending_approvals(self) -> list[dict]:
        return [
            {"run_id": k, **v}
            for k, v in self._approval_requests.items()
            if v["status"] == "pending"
        ]

    def get_stats(self) -> dict:
        return {
            "total_messages": len(self._messages),
            "total_interactions": len(self._interactions),
            "pending_approvals": sum(
                1 for v in self._approval_requests.values()
                if v["status"] == "pending"
            ),
        }


slack_notifier = SlackNotifier()
