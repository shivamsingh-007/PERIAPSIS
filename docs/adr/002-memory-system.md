# ADR-002: Memory System Design

**Date:** 2026-06-19
**Status:** Accepted
**Deciders:** Platform Team

## Context

The platform needs persistent memory to learn from past runs and improve over time. Memory must be tenant-isolated, deduplicated, and support graph-anchored retrieval.

## Decision

We implement a three-tier memory system:

1. **Episodic Memory** — Run-scoped memories tied to specific executions (stored in Postgres with pgvector embeddings)
2. **Semantic Memory** — Consolidated lessons promoted from episodic memories (requires human approval for v1)
3. **Graph-Anchored Memory** — Memories linked to knowledge graph nodes via `graph_node_id` and `graph_concepts` fields

### Key Design Choices

- **Deduplication** via content hash (SHA-256) — duplicate writes increment confidence instead of creating new records
- **TTL-based expiry** — memories expire after configurable `ttl_days`
- **Write filtering** — source attribution and confidence scoring before storage
- **Conflict resolution** — 5 strategies (latest_wins, confidence_wins, merge, archive, human_decides)

## Consequences

- **Positive:** Reduces noise, prevents duplicate lessons, enables graph-aware retrieval
- **Negative:** Hash-based dedup may miss semantically similar content
- **Mitigations:** Clustering-based dedup (K-means on embeddings) as secondary layer
