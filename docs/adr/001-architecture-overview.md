# ADR-001: Architecture Overview

**Date:** 2026-06-19
**Status:** Accepted
**Deciders:** Platform Team

## Context

The Agentic Loop Platform needs a clear architectural foundation to support closed-loop agent execution with governance, memory, and fleet orchestration.

## Decision

We adopt a layered architecture with the following core principles:

1. **Closed-Loop Design** — Every run must reach a terminal state (SUCCESS, PARTIAL_SUCCESS, ESCALATED_TO_HUMAN, STOP_BUDGET, STOP_POLICY, STOP_NO_PROGRESS, FAIL_TOOLING, FAIL_INVARIANT)
2. **Governance-First** — Policy checks happen before every action, not after
3. **Typed State Only** — RunState is a Pydantic model; no untyped `Any` blobs in graph state
4. **Immutable Audit Logs** — governance_events are append-only
5. **Graph-Aware Intelligence** — Graphify knowledge graph provides context for planning, memory, reflection, and fleet routing

## Consequences

- **Positive:** Clear separation of concerns, auditable by design, scalable fleet
- **Negative:** More boilerplate for adding new nodes, graph dependency adds operational complexity
- **Mitigations:** LangGraph handles state management; Graphify wraps CLI complexity
