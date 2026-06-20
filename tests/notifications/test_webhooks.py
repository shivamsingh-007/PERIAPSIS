from __future__ import annotations
"""Tests for packages.notifications.webhooks - WebhookManager._sign_payload."""

import hashlib
import hmac
import json

import pytest

from packages.notifications.webhooks import WebhookEvent, WebhookManager


class TestWebhookManagerLogic:
    def setup_method(self):
        self.manager = WebhookManager()

    def test_sign_payload(self):
        payload = {"event": "test", "data": {"key": "value"}}
        signature = self.manager._sign_payload("my-secret", payload)
        assert signature
        assert len(signature) == 64  # SHA-256 hex

    def test_sign_payload_deterministic(self):
        payload = {"event": "test"}
        sig1 = self.manager._sign_payload("secret", payload)
        sig2 = self.manager._sign_payload("secret", payload)
        assert sig1 == sig2

    def test_sign_payload_different_secrets(self):
        payload = {"event": "test"}
        sig1 = self.manager._sign_payload("secret1", payload)
        sig2 = self.manager._sign_payload("secret2", payload)
        assert sig1 != sig2

    def test_webhook_event_enum(self):
        assert WebhookEvent.RUN_CREATED.value == "run.created"
        assert WebhookEvent.RUN_COMPLETED.value == "run.completed"
        assert WebhookEvent.APPROVAL_NEEDED.value == "approval.needed"
        assert len(list(WebhookEvent)) == 10
