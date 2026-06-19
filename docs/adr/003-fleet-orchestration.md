# ADR-003: Fleet Orchestration with Ruflo

**Date:** 2026-06-19
**Status:** Accepted
**Deciders:** Platform Team

## Context

Complex tasks require parallel execution across multiple specialized agents. We need a fleet orchestration system that supports swarm-based coordination with compliance gating.

## Decision

We integrate Ruflo MCP as the fleet orchestration backend:

1. **MCP Bridge** — Subprocess-based communication with `npx ruflo@latest mcp start`
2. **Swarm Manager** — 4 pre-configured swarm types (code, research, security, governance)
3. **Worker Pool** — Parallel agent execution with workspace isolation via git worktrees
4. **Compliance Registry** — Asset registry, policy gates, audit trails, and data lineage

### Graph-Based Routing

The Graphify knowledge graph routes tasks to specialized agents:
- Security concepts → security-swarm
- Governance concepts → governance-swarm
- Research concepts → research-swarm
- Default → code-swarm

## Consequences

- **Positive:** Parallel execution, specialized agents, auditable fleet operations
- **Negative:** Ruflo dependency adds external service risk
- **Mitigations:** Fallback to keyword-based routing if graph unavailable; local-only mode for development
