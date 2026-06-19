from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from packages.logging.structured import get_logger

logger = get_logger("security_gateway")


class ThreatLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PIICategory(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    MEDICAL = "medical"
    FINANCIAL = "financial"
    PASSWORD = "password"
    API_KEY = "api_key"


PII_PATTERNS: dict[PIICategory, re.Pattern] = {
    PIICategory.EMAIL: re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
    PIICategory.PHONE: re.compile(r'(\+?1?[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'),
    PIICategory.SSN: re.compile(r'\b\d{3}[-]?\d{2}[-]?\d{4}\b'),
    PIICategory.CREDIT_CARD: re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
    PIICategory.IP_ADDRESS: re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    PIICategory.PASSWORD: re.compile(r'(?i)(password|passwd|pwd)\s*[:=]\s*\S+'),
    PIICategory.API_KEY: re.compile(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+'),
}


class InjectionPattern(BaseModel):
    name: str
    pattern: re.Pattern
    severity: ThreatLevel
    description: str


INJECTION_PATTERNS: list[InjectionPattern] = [
    InjectionPattern(
        name="system_prompt_override",
        pattern=re.compile(r'(?i)(ignore|disregard|override)\s+(all\s+)?(previous|prior|system)\s+(instructions|prompts?)'),
        severity=ThreatLevel.HIGH,
        description="Attempt to override system prompt",
    ),
    InjectionPattern(
        name="role_hijack",
        pattern=re.compile(r'(?i)you\s+are\s+now\s+(a|an|the)\s+\w+'),
        severity=ThreatLevel.MEDIUM,
        description="Attempt to hijack agent role",
    ),
    InjectionPattern(
        name="data_exfiltration",
        pattern=re.compile(r'(?i)(send|transmit|upload|exfiltrate)\s+(all\s+)?(data|files|secrets?|keys?|tokens?)'),
        severity=ThreatLevel.CRITICAL,
        description="Attempt to exfiltrate data",
    ),
    InjectionPattern(
        name="code_execution",
        pattern=re.compile(r'(?i)(exec|eval|system|subprocess|os\.system)\s*\('),
        severity=ThreatLevel.HIGH,
        description="Attempt to execute arbitrary code",
    ),
    InjectionPattern(
        name="privilege_escalation",
        pattern=re.compile(r'(?i)(sudo|admin|root|elevate)\s+(access|privileges?|permissions?)'),
        severity=ThreatLevel.CRITICAL,
        description="Attempt to escalate privileges",
    ),
]


class PIIDetection(BaseModel):
    category: PIICategory
    start: int
    end: int
    original: str
    redacted: str


class SecurityCheckResult(BaseModel):
    passed: bool
    threat_level: ThreatLevel = ThreatLevel.NONE
    pii_detections: list[PIIDetection] = Field(default_factory=list)
    injection_detections: list[dict] = Field(default_factory=list)
    redacted_content: str | None = None
    blocked_reason: str | None = None
    checks_performed: list[str] = Field(default_factory=list)


class RateLimitConfig(BaseModel):
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    tokens_per_minute: int = 100000
    cost_per_hour: float = 10.0


class SecurityGateway:
    def __init__(self):
        self._rate_limits: dict[str, RateLimitConfig] = {}
        self._request_counts: dict[str, list[float]] = defaultdict(list)
        self._token_counts: dict[str, list[float]] = defaultdict(list)
        self._cost_counts: dict[str, list[float]] = defaultdict(list)
        self._blocked_agents: set[str] = set()

    def configure_rate_limit(self, agent_id: str, config: RateLimitConfig) -> None:
        self._rate_limits[agent_id] = config

    def check_request(
        self,
        agent_id: str,
        content: str,
        tool_name: str | None = None,
        estimated_tokens: int = 0,
        estimated_cost: float = 0.0,
    ) -> SecurityCheckResult:
        checks_performed = []

        if agent_id in self._blocked_agents:
            return SecurityCheckResult(
                passed=False,
                threat_level=ThreatLevel.CRITICAL,
                blocked_reason=f"Agent {agent_id} is blocked",
            )

        rate_check = self._check_rate_limits(agent_id, estimated_tokens, estimated_cost)
        checks_performed.append("rate_limits")
        if not rate_check.passed:
            return rate_check

        pii_check = self._check_pii(content)
        checks_performed.append("pii_detection")

        injection_check = self._check_injection(content)
        checks_performed.append("injection_detection")

        all_injections = injection_check.get("detections", [])
        if all_injections:
            max_severity = max(
                (ThreatLevel(p["severity"]) for p in all_injections),
                key=lambda x: list(ThreatLevel).index(x),
            )
            if max_severity in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
                return SecurityCheckResult(
                    passed=False,
                    threat_level=max_severity,
                    injection_detections=all_injections,
                    blocked_reason="Injection attack detected",
                    checks_performed=checks_performed,
                )

        redacted = self._redact_content(content, pii_check)

        return SecurityCheckResult(
            passed=True,
            threat_level=ThreatLevel.NONE if not all_injections else ThreatLevel.LOW,
            pii_detections=pii_check,
            injection_detections=all_injections,
            redacted_content=redacted,
            checks_performed=checks_performed,
        )

    def _check_rate_limits(
        self,
        agent_id: str,
        estimated_tokens: int,
        estimated_cost: float,
    ) -> SecurityCheckResult:
        config = self._rate_limits.get(agent_id)
        if not config:
            config = RateLimitConfig()

        now = time.time()
        minute_ago = now - 60
        hour_ago = now - 3600

        self._request_counts[agent_id] = [
            t for t in self._request_counts[agent_id] if t > minute_ago
        ]
        self._token_counts[agent_id] = [
            t for t in self._token_counts[agent_id] if t > minute_ago
        ]
        self._cost_counts[agent_id] = [
            t for t in self._cost_counts[agent_id] if t > hour_ago
        ]

        if len(self._request_counts[agent_id]) >= config.requests_per_minute:
            return SecurityCheckResult(
                passed=False,
                blocked_reason=f"Rate limit exceeded: {config.requests_per_minute} req/min",
            )

        if len(self._token_counts[agent_id]) + estimated_tokens > config.tokens_per_minute:
            return SecurityCheckResult(
                passed=False,
                blocked_reason=f"Token limit exceeded: {config.tokens_per_minute} tokens/min",
            )

        total_cost = sum(self._cost_counts[agent_id]) + estimated_cost
        if total_cost > config.cost_per_hour:
            return SecurityCheckResult(
                passed=False,
                blocked_reason=f"Cost limit exceeded: ${config.cost_per_hour}/hour",
            )

        self._request_counts[agent_id].append(now)
        self._token_counts[agent_id].append(now)
        self._cost_counts[agent_id].append(now)

        return SecurityCheckResult(passed=True)

    def _check_pii(self, content: str) -> list[PIIDetection]:
        detections = []
        for category, pattern in PII_PATTERNS.items():
            for match in pattern.finditer(content):
                redacted = f"[REDACTED_{category.value.upper()}]"
                detections.append(PIIDetection(
                    category=category,
                    start=match.start(),
                    end=match.end(),
                    original=match.group(),
                    redacted=redacted,
                ))
        return detections

    def _check_injection(self, content: str) -> dict:
        detections = []
        for pattern in INJECTION_PATTERNS:
            if pattern.pattern.search(content):
                detections.append({
                    "name": pattern.name,
                    "severity": pattern.severity.value,
                    "description": pattern.description,
                })
        return {"detections": detections}

    def _redact_content(self, content: str, pii_detections: list[PIIDetection]) -> str:
        if not pii_detections:
            return content

        sorted_detections = sorted(pii_detections, key=lambda d: d.start, reverse=True)
        redacted = content
        for detection in sorted_detections:
            redacted = redacted[:detection.start] + detection.redacted + redacted[detection.end:]
        return redacted

    def block_agent(self, agent_id: str) -> None:
        self._blocked_agents.add(agent_id)
        logger.warning(f"Blocked agent: {agent_id}")

    def unblock_agent(self, agent_id: str) -> None:
        self._blocked_agents.discard(agent_id)
        logger.info(f"Unblocked agent: {agent_id}")

    def get_rate_status(self, agent_id: str) -> dict:
        config = self._rate_limits.get(agent_id, RateLimitConfig())
        now = time.time()
        minute_ago = now - 60

        recent_requests = len([
            t for t in self._request_counts.get(agent_id, []) if t > minute_ago
        ])

        return {
            "agent_id": agent_id,
            "requests_this_minute": recent_requests,
            "requests_limit": config.requests_per_minute,
            "is_blocked": agent_id in self._blocked_agents,
        }


security_gateway = SecurityGateway()
