# ADR-004: Governance Model

**Date:** 2026-06-19
**Status:** Accepted
**Deciders:** Platform Team

## Context

Agent actions must be governed to prevent unauthorized operations, budget overruns, and policy violations. Governance must be enforceable without blocking legitimate work.

## Decision

We implement a layered governance model:

1. **Policy Engine** — Rule-based evaluation of actions before execution (allow/deny/escalate)
2. **Rules Engine** — Factual claims require evidence; traces require sources; terminal states require justification
3. **Feature Flags** — Boolean/percentage/segment-based feature gating
4. **Circuit Breaker** — Prevents cascade failures (CLOSED → OPEN → HALF_OPEN)
5. **Approval API** — Human-in-the-loop for high-risk actions

### Risk Tiers

- **Low** — Auto-approved (read-only operations)
- **Medium** — Logged and monitored (write operations)
- **High** — Requires approval (destructive/deploy operations)

## Consequences

- **Positive:** Prevents unauthorized actions, auditable by design, human oversight for high-risk
- **Negative:** Approval latency for high-risk actions
- **Mitigations:** Auto-approve for trusted patterns; async approval workflows
