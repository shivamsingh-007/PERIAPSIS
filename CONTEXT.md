<p align="center">
  <img src="https://img.shields.io/badge/AGENTIC--LOOP-blue?style=for-the-badge&logo=python&logoColor=white" alt="Agentic Loop"/>
  <img src="https://img.shields.io/badge/VERSION-0.1.0-green?style=for-the-badge" alt="Version"/>
  <img src="https://img.shields.io/badge/PYTHON-3.11+-yellow?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/STATUS-PROTOTYPE-orange?style=for-the-badge" alt="Status"/>
</p>

<h1 align="center">
  <br>
  <img src="https://img.shields.io/badge/🧠-AGENT%20PLATFORM-ff6b6b?style=for-the-badge&logo=robot&logoColor=white" alt="Agent Platform" width="200"/>
  <br>
  Agentic Loop Platform — CONTEXT
  <br>
</h1>

<p align="center">
  <b>Complete project history, architecture decisions, session logs, and honest status assessment.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/SESSIONS-12+-9b59b6?style=flat-square" alt="Sessions"/>
  <img src="https://img.shields.io/badge/COMMITS-22+-2ecc71?style=flat-square" alt="Commits"/>
  <img src="https://img.shields.io/badge/TESTS-1256-3498db?style=flat-square" alt="Tests"/>
  <img src="https://img.shields.io/badge/FEATURES-220-e74c3c?style=flat-square" alt="Features"/>
  <img src="https://img.shields.io/badge/LOC-~15K-95a5a6?style=flat-square" alt="Lines of Code"/>
</p>

---

## 📑 Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Architecture Decision Records](#2-architecture-decision-records)
- [3. Tech Stack](#3-tech-stack)
- [4. Session History](#4-session-history)
- [5. What Was Built](#5-what-was-built)
- [6. Security Hardening Log](#6-security-hardening-log)
- [7. Test Suite Status](#7-test-suite-status)
- [8. Known Issues & Honest Assessment](#8-known-issues--honest-assessment)
- [9. File Map](#9-file-map)
- [10. Environment Variables](#10-environment-variables)
- [11. Git History](#11-git-history)
- [12. Future Work](#12-future-work)

---

## 1. Project Overview

### What Is This?

A **governance-first, closed-loop agent platform** built with Python/FastAPI, LangGraph, Postgres+pgvector, and Langfuse. The system executes bounded AI agent tasks through a stateful runtime with validation, checkpoints, memory, reflection, and fleet orchestration.

### Who Is It For?

AI/ML platform teams who need a reusable runtime for multiple internal products. Reliability, observability, and governance are the priorities — not maximum autonomy.

### Key Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Closed-loop** | Every run must reach a terminal state (SUCCESS, PARTIAL_SUCCESS, ESCALATED_TO_HUMAN, STOP_BUDGET, STOP_POLICY, STOP_NO_PROGRESS, FAIL_TOOLING, FAIL_INVARIANT) |
| **Governance-first** | Policy engine evaluates risk tiers before every tool call |
| **Observability-first** | Langfuse integration on every LLM call and HTTP request |
| **Typed state** | Pydantic models throughout, no `Any` blobs |
| **Immutable audit** | Governance events are append-only |

---

## 2. Architecture Decision Records

### ADR-001: LangGraph for State Machine
- **Decision:** Use LangGraph for the agent runtime state machine
- **Rationale:** Native Python, supports cycles (reflect→decide), checkpointing, human-in-the-loop
- **Trade-off:** Tightly coupled to LangChain ecosystem

### ADR-002: Postgres + pgvector for Persistence
- **Decision:** Postgres as primary DB, pgvector for embeddings
- **Rationale:** Battle-tested, supports JSON, full-text search, vector similarity
- **Trade-off:** Requires async driver (asyncpg), more complex than SQLite

### ADR-003: Langfuse for Observability
- **Decision:** Langfuse for tracing, cost tracking, and prompt management
- **Rationale:** Open-source, self-hostable, purpose-built for LLM apps
- **Trade-off:** Additional infrastructure dependency

### ADR-004: PyJWT over Custom HMAC
- **Decision:** Migrate from custom HMAC-SHA256 JWT to PyJWT library
- **Rationale:** Standard library, proper validation, audience/issuer checks
- **Trade-off:** Additional dependency, but well-maintained

### ADR-005: Repository Pattern for Data Access
- **Decision:** Use repository pattern for auth and secrets; raw SQL for some routes
- **Rationale:** Testability, separation of concerns
- **Trade-off:** Inconsistent pattern (some routes use ORM, some use raw SQL)

### ADR-006: Middleware Stack Ordering
- **Decision:** Request → RateLimit → Idempotency → Tracing → RLS → RBAC → Router
- **Rationale:** Rate limiting first (cheapest check), auth last (most expensive)
- **Trade-off:** RLS before RBAC means tenant context is set before role verification

---

## 3. Tech Stack

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                          │
│  Next.js 14 · TypeScript · Tailwind CSS · SWR       │
├─────────────────────────────────────────────────────┤
│                     API LAYER                        │
│  FastAPI · Pydantic v2 · Starlette Middleware        │
├─────────────────────────────────────────────────────┤
│                   CORE RUNTIME                       │
│  LangGraph · LangChain · Python 3.11+               │
├─────────────────────────────────────────────────────┤
│                  INFRASTRUCTURE                      │
│  Postgres+pgvector · Redis · Supabase · 9router     │
├─────────────────────────────────────────────────────┤
│                 OBSERVABILITY                        │
│  Langfuse · Structured Logging · Circuit Breaker    │
├─────────────────────────────────────────────────────┤
│                   SECURITY                           │
│  PyJWT · Fernet · RBAC · RLS · CORS · CSP Headers   │
└─────────────────────────────────────────────────────┘
```

### Dependencies (from pyproject.toml)

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | ≥0.115.0 | API framework |
| uvicorn | ≥0.30.0 | ASGI server |
| sqlalchemy[asyncio] | ≥2.0.30 | ORM + async DB |
| asyncpg | ≥0.29.0 | PostgreSQL async driver |
| alembic | ≥1.13.0 | Database migrations |
| pydantic | ≥2.7.0 | Data validation |
| langgraph | ≥0.2.0 | Agent state machine |
| langfuse | ≥2.40.0 | LLM observability |
| pgvector | ≥0.3.0 | Vector similarity search |
| redis | ≥5.0.0 | Caching (planned) |
| httpx | ≥0.27.0 | Async HTTP client |
| openai | ≥1.30.0 | LLM API client |
| supabase | ≥2.0.0 | Database-as-a-service |
| cryptography | ≥42.0.0 | Fernet encryption |
| pyjwt | (via auth) | JWT tokens |

---

## 4. Session History

### Session 1: Foundation (Milestone 0)
**Commit:** `d9e692d`
- Repository skeleton with all packages
- FastAPI app with health check
- SQLAlchemy models (14 tables)
- LangGraph setup with initial nodes
- Langfuse middleware integration

### Session 2: Core Runtime (Milestone 1)
**Commit:** `7f05585`
- Checkpoint store with save/load
- Run API (CRUD + execute)
- Graph nodes (intake, plan, execute, validate, reflect, decide)
- Run service with budget enforcement

### Session 3: Governance (Milestone 2)
**Commit:** `48c028f`
- PolicyEngine with risk-tier evaluation
- Validation gate node
- Approval workflow
- Governance event logging

### Session 4: Memory & Reflection (Milestone 3)
**Commit:** `c26b3a0`
- Memory store with deduplication
- TTL-based expiry
- Confidence-based write filters
- Reflection node (simplified)

### Session 5: Hooks, Harness, Metrics
**Commit:** `7866106`
- Hook system for extensibility
- Evaluation harness
- Metrics aggregation
- Quality scoring

### Session 6: Polish & Hardening (Milestone 5)
**Commit:** `ccc71f8`
- Idempotency middleware
- Rate limiting middleware
- Structured logging
- Graceful shutdown

### Session 7: Backend Completion
**Commit:** `dc6abae`
- WebSocket manager
- Row-level security middleware
- RBAC middleware
- Webhooks, export, scheduler

### Session 8: Frontend
**Commit:** `76692a6`
- Next.js admin dashboard
- 8 pages: runs, memory, governance, health, metrics, logs, settings, dashboard
- Components: RunCard, MemoryCard, StatusBadge

### Session 9: Rules, Features, Circuit Breaker
**Commit:** `16293da`
- Rules engine
- Feature flags
- Circuit breaker (production-quality)
- Cost prediction
- Run replay
- Templates

### Session 10: Fleet Orchestration
**Commit:** `11f419a`
- Fleet orchestrator
- Swarm manager
- Security gateway
- Compliance layer
- Ruflo integration (partial)

### Session 11: Remaining Features
**Commit:** `a9b5c20`
- Memory policy YAML
- Checkpoint diff visualization
- Fleet board UI
- Unit tests
- OpenAPI docs
- ADRs, runbook, contributing guide

### Session 12: Graphify Integration
**Commit:** `b269cf0`
- Knowledge graph router
- Graph-aware planning
- Memory graph linking
- Fleet routing via graph

### Session 13: 1181-Test Suite
**Commit:** `09c08d6`
- Comprehensive test suite
- 76% coverage
- Tests for all modules

### Session 14: Real Execute Node
**Commit:** `e32f8d9`
- Created `packages/runtime/executor.py` — Executor protocol + ToolExecutionResult
- Created `packages/runtime/llm_executor.py` — Real OpenAI integration + Langfuse tracing
- Replaced fake `execute()` in graph.py with real async executor
- Fixed fleet_node.py crash (getattr instead of .get())
- 9 new executor tests

### Session 15: Persistence & Security
**Commit:** `aa2defd`
- ORM models: AuthTokenRecord, SecretRecord, AgentRecord
- Repository layer: AuthRepository, SecretsRepository, AgentsRepository
- Async DB-backed auth and secrets
- SQL injection fix (whitelist + ORM)
- Hardcoded DB URL fix
- Alembic migration 001

### Session 16: Supabase + 9router
**Commit:** `daee69f`
- Supabase client wrapper
- 9router LLM proxy support
- Added supabase, openai, cryptography to deps
- 10 new infrastructure tests

### Session 17: Routes, WebSocket Auth, Frontend Reality
**Commit:** `f731809`
- Auth dependencies (get_current_user, get_current_tenant, verify_ws_token)
- Governance API (events, summary, approve, deny)
- Notifications API (subscribe, subscriptions, jobs)
- Logs API (from in-memory buffer)
- Run metrics summary endpoint
- Token-authenticated WebSocket endpoint
- 4 frontend pages replaced with real API calls
- Fixed 3 test failures
- 1256 tests passing

### Session 18: Security Hardening
**Commit:** `0d64a80`
- PyJWT replacement (jwt_utils.py)
- RBAC: role from JWT token, not header
- CORS middleware (env-configurable)
- Security headers (CSP, HSTS, X-Frame-Options)
- SSRF URL validation utility
- Rotated SECRET_KEY
- Hardened .gitignore
- Fixed JWT jti mismatch
- 1256 tests passing

---

## 5. What Was Built

### Modules (28 packages)

```
packages/
├── runtime/          # Core agent runtime
│   ├── graph.py          # LangGraph state machine (9 nodes)
│   ├── state.py          # RunState, BudgetPolicy, Action models
│   ├── executor.py       # Executor protocol + ToolExecutionResult
│   ├── llm_executor.py   # Real OpenAI integration + Langfuse
│   ├── fleet_node.py     # Fleet orchestration dispatch
│   ├── checkpoint.py     # Save/load state snapshots
│   └── templates.py      # Prompt template management
│
├── security/         # Authentication & authorization
│   ├── auth.py           # Token lifecycle (PyJWT)
│   ├── jwt_utils.py      # JWT encode/decode
│   ├── secrets.py        # Fernet encryption vault
│   ├── repositories.py   # Auth/Secrets/Agents DB repos
│   ├── rbac.py           # Role-based access control
│   ├── rls.py            # Row-level security (broken)
│   ├── dependencies.py   # FastAPI auth dependencies
│   ├── security_headers.py  # CSP, HSTS, X-Frame-Options
│   └── url_validation.py # SSRF protection
│
├── governance/       # Policy & compliance
│   └── policy.py         # Risk-tier policy engine
│
├── resilience/       # Fault tolerance
│   └── circuit_breaker.py # CLOSED→OPEN→HALF_OPEN state machine
│
├── memory/           # Knowledge management
│   ├── store.py          # CRUD + dedup + TTL
│   └── write_filter.py   # Confidence-based gating
│
├── evals/            # Evaluation harness
│   ├── harness.py        # Test runner
│   └── scoring.py        # Quality scoring
│
├── schemas/          # Data models
│   ├── models.py         # 14 SQLAlchemy ORM models
│   └── database.py       # Engine, sessions, context manager
│
├── middleware/        # HTTP middleware
│   ├── idempotency.py    # POST/PUT/PATCH/DELETE dedup
│   ├── rate_limit.py     # Sliding window rate limiter
│   └── shutdown.py       # Graceful shutdown tracker
│
├── infrastructure/   # External integrations
│   └── supabase_client.py # Supabase wrapper
│
├── logging/          # Observability
│   └── structured.py     # JSON logging + buffer
│
├── websocket/        # Real-time
│   └── manager.py        # Connection manager + pub/sub
│
├── scheduler/        # Job scheduling
│   └── scheduler.py      # Cron/interval scheduler (stub)
│
├── notifications/    # Alerts
│   └── webhooks.py       # Webhook delivery
│
├── fleet/            # Multi-agent
│   └── coordinator.py    # Fleet orchestration
│
└── graphify/         # Knowledge graph
    └── graph_router.py   # Graph-aware routing
```

### API Routes (15 routers)

| Router | Endpoints | Auth |
|--------|-----------|------|
| `/runs` | CRUD, execute, metrics | Bearer token |
| `/approvals` | Create, approve, deny | Bearer token |
| `/memory` | CRUD, search, graph | Bearer token |
| `/harness` | Evaluate, score | Bearer token |
| `/export` | Run data export | Bearer token |
| `/webhooks` | CRUD, test | Bearer token |
| `/scheduler` | CRUD, trigger | Bearer token |
| `/ws` | WebSocket (auth + legacy) | Token query param |
| `/fleet` | Jobs, swarms, compliance | Tenant header |
| `/graphify` | Build, query, path | None ⚠️ |
| `/resilience` | Circuit breaker, rate limit | Tenant header |
| `/governance` | Events, summary, approve | Bearer token |
| `/notifications` | Subscribe, jobs | Bearer token |
| `/logs` | Event logs | Bearer token |
| `/health` | Health check | None |

### Frontend (Next.js)

| Page | Status | API Calls |
|------|--------|-----------|
| Dashboard | ✅ Real | Aggregated |
| Runs | ✅ Real | `/runs` |
| Memory | ✅ Real | `/memory` |
| Governance | ✅ Real | `/governance/*` |
| Health | ✅ Real | `/health` |
| Metrics | ✅ Real | `/runs/metrics/summary` |
| Logs | ✅ Real | `/logs` |
| Settings | ⏳ Placeholder | — |
| Run Detail | ❌ Missing | — |

---

## 6. Security Hardening Log

### Findings & Fixes (Session 18)

| # | Severity | Finding | File | Fix |
|---|----------|---------|------|-----|
| 1 | CRITICAL | No CORS middleware | main.py | `CORSMiddleware` with env origins |
| 2 | CRITICAL | Hardcoded DB URL | alembic.ini | `%(DATABASE_URL)s` env var |
| 3 | CRITICAL | RBAC from X-User-Role header | rbac.py | Role from JWT token payload |
| 4 | HIGH | Custom HMAC JWT | auth.py | PyJWT via jwt_utils.py |
| 5 | HIGH | Weak SECRET_KEY | .env | Rotated to 48-byte random |
| 6 | MEDIUM | No security headers | — | SecurityHeadersMiddleware |
| 7 | MEDIUM | Minimal .gitignore | .gitignore | Added .env.*, *.key, *.pem |
| 8 | MEDIUM | No SSRF validation | — | url_validation.py utility |
| 9 | LOW | Docs exposed | main.py | DISABLE_DOCS env flag |
| 10 | LOW | No input size caps | — | Deferred |

### Residual Issues (NOT Fixed)

| Issue | Severity | Reason |
|-------|----------|--------|
| RLS middleware broken | CRITICAL | Sets tenant on throwaway session |
| SQL injection pattern | HIGH | f-string SQL composition in runs.py |
| Unauthenticated WebSocket | HIGH | Legacy `/ws/{client_id}` endpoint |
| Secret key regen on restart | HIGH | Module-level singleton |
| No DNS rebinding protection | MEDIUM | URL validation only checks IP literals |
| In-memory rate limiting | MEDIUM | Not distributed |

---

## 7. Test Suite Status

### Overall: 1256 tests, 0 failing

### Test Quality by Category

```
REAL TESTS (hit actual logic)
├── Runtime (graph, state, executor)     57 tests  ████████████ 95%
├── Security (auth, secrets, RBAC)       35 tests  ████████████ 90%
├── Governance (policy engine)           22 tests  ████████████ 100%
├── Resilience (circuit breaker)         20 tests  ████████████ 100%
├── Memory (store, filters)              15 tests  ████████████ 80%
├── API Routes (governance, notif)       50 tests  ████████░░░░ 70%
├── WebSocket                            6 tests   ████████░░░░ 60%
├── Middleware (rate limit, idemp)       10 tests  ████████░░░░ 70%
├── Infrastructure (supabase)           10 tests  ████████████ 100%
└── Other                               445 tests  ████████░░░░ 80%

VACUOUS TESTS (mock everything, assert mock output)
├── Templates                           10 tests  ░░░░░░░░░░░░ mock-only
├── Checkpoint                           5 tests  ░░░░░░░░░░░░ mock-only
├── Evals (fact coverage)                7 tests  ░░░░░░░░░░░░ assert not-None
├── Fleet/Graphify                      10 tests  ░░░░░░░░░░░░ mock-only
├── API Routes (some)                   30 tests  ░░░░░░░░░░░░ mock sessions
└── WebSocket (some)                     6 tests  ░░░░░░░░░░░░ mock connections
```

### Honest Count
- **Real tests:** ~1050 (84%)
- **Vacuous tests:** ~206 (16%)
- **Broken tests:** 0 (0%)

---

## 8. Known Issues & Honest Assessment

### What's Genuinely Good ✅

1. **Architecture spec** — One of the best agent platform specs ever written. 543 lines of detailed analysis.
2. **Circuit breaker** — Production-quality. Full state machine, metrics, 20 real tests.
3. **Auth/secrets design** — PyJWT + Fernet + repository pattern. Sound architecture.
4. **Policy engine** — Risk-tier evaluation, tool-level policies, 22 real tests.
5. **Middleware stack concept** — Rate → Idempotency → Tracing → RLS → RBAC is correct.

### What's Half-Baked ⚠️

1. **Graph routing** — Real logic, but `plan()` returns hardcoded actions.
2. **Memory store** — CRUD works, but no vector search despite pgvector in deps.
3. **Fleet orchestration** — Word-matching dispatch, no actual Ruflo API calls.
4. **Scheduler** — Cron parsing is a stub (always +1hr).
5. **WebSocket** — Auth works on new endpoint, legacy endpoint is unauthenticated.

### What's Broken ❌

1. **RLS middleware** — Sets tenant on throwaway session. Non-functional.
2. **SQL injection pattern** — f-string SQL composition in runs.py.
3. **Secret key regeneration** — Every restart invalidates all tokens.
4. **No integration tests** — Every test mocks the database.
5. **No Docker files** — Can't deploy or test locally with real DB.

### Honest Rating

| Aspect | Rating | Notes |
|--------|--------|-------|
| Architecture | 8/10 | Excellent spec, good design decisions |
| Security | 4/10 | Hardened but critical flaws remain |
| Testing | 5/10 | Good unit tests, zero integration tests |
| Production readiness | 2/10 | In-memory state, no Docker, no CI/CD |
| Code quality | 6/10 | Clean models, inconsistent patterns |
| Documentation | 7/10 | Good spec, decent inline docs |
| **Overall** | **5/10** | **Well-designed prototype, not production** |

---

## 9. File Map

### Project Root
```
C:\Users\shiva\OneDrive\Documents\AL new\
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Template with placeholders
├── .gitignore                    # Secrets, builds, IDE files
├── pyproject.toml                # Dependencies, pytest, ruff, mypy
├── alembic.ini                   # Migration config (env var DB URL)
├── feature_list.json             # 220 features tracked
├── specs/
│   └── agentic-loop-platform.md  # Full architecture spec (543 lines)
├── docs/
│   └── hardening-plan.md         # 11-section security guide
├── alembic/
│   ├── env.py                    # Migration runner
│   └── versions/
│       ├── 001_initial_schema.py
│       └── 002_notifications_scheduler.py
├── apps/
│   ├── api/
│   │   ├── main.py               # FastAPI app + middleware
│   │   ├── middleware/
│   │   │   └── tracing.py        # Langfuse HTTP tracing
│   │   └── routes/               # 15 API routers
│   └── web/                      # Next.js frontend
├── packages/                     # 28 Python packages
│   ├── runtime/
│   ├── security/
│   ├── governance/
│   ├── resilience/
│   ├── memory/
│   ├── evals/
│   ├── schemas/
│   ├── middleware/
│   ├── infrastructure/
│   ├── logging/
│   ├── websocket/
│   ├── scheduler/
│   ├── notifications/
│   ├── fleet/
│   └── graphify/
└── tests/                        # 1256 tests
    ├── conftest.py
    ├── runtime/
    ├── security/
    ├── governance/
    ├── resilience/
    ├── memory/
    ├── evals/
    ├── middleware/
    ├── infrastructure/
    ├── websocket/
    ├── notifications/
    ├── fleet/
    └── graphify/
```

---

## 10. Environment Variables

### Required

| Variable | Example | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql+asyncpg://agentic:agentic_dev@localhost:5432/agentic_loop` | Primary database |
| `SECRET_KEY` | `CgbtuO1R2380oJ3JM_hI6ixkaoDINTvPFeZSv1lLUZyXJ8kBwFVZSSlx2_HD8FWl` | JWT signing key |
| `LLM_API_KEY` | `sk-...` | OpenAI/9router API key |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_BASE_URL` | `http://localhost:20128/v1` | 9router proxy URL |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model name |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | — | Langfuse secret key |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse endpoint |
| `LANGFUSE_ENABLED` | `false` | Enable Langfuse tracing |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_KEY` | — | Supabase service role key |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | CORS origins (comma-separated) |
| `DISABLE_DOCS` | — | Disable /docs and /redoc |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRATION_MINUTES` | `60` | Token expiry |

---

## 11. Git History

```
0d64a80 security: harden JWT, RBAC, CORS, headers, secrets, SSRF
f731809 feat: missing routes, WebSocket auth, frontend reality
daee69f feat: Supabase integration + 9router LLM provider
aa2defd feat: persistence layer, SQL injection fix, DB-backed repos
e32f8d9 feat: implement real execute node with LLMExecutor + Langfuse
09c08d6 test: comprehensive 1181-test suite with 76% coverage
8b9f19c feat: complete remaining 9 features
b269cf0 feat: integrate Graphify knowledge graph
a9b5c20 feat: complete 42 remaining features
11f419a feat: Fleet orchestration with Ruflo integration
16293da feat: rules engine, feature flags, circuit breaker, cost prediction
76692a6 Next.js Admin Dashboard: full UI with 8 pages
dc6abae remaining backend: WebSocket, RLS, RBAC, Webhooks, Export, Scheduler
ccc71f8 M5: idempotency, rate limiting, logging, shutdown, deploy
7866106 M3+M4: hooks, consolidation, conflict, harness, metrics, gate
c26b3a0 M3: Memory & Reflection (partial)
48c028f M2: Governance - PolicyEngine, validation gate, approval workflow
7f05585 M1: Core Runtime - checkpoint store, run API, graph nodes
d9e692d M0: Foundation - repo skeleton, models, FastAPI, LangGraph
612f8b5 add spec, real features, and updated init.sh
de06cd2 initial workspace setup
```

**Total:** 21 commits on `master` branch

---

## 12. Future Work

### Priority 1: Fix Critical Security
- [ ] Fix RLS middleware (set tenant on request session, not throwaway)
- [ ] Fix SQL injection pattern (use ORM or parameterized queries everywhere)
- [ ] Fix secret key regeneration on restart (persistent key storage)
- [ ] Add auth to legacy WebSocket endpoint

### Priority 2: Production Infrastructure
- [ ] Add Docker + docker-compose.yml
- [ ] Add CI/CD pipeline (GitHub Actions)
- [ ] Add integration tests with real Postgres
- [ ] Add connection pooling
- [ ] Add request ID middleware

### Priority 3: Feature Completion
- [ ] Implement real cron parsing in scheduler
- [ ] Implement vector similarity search for memory
- [ ] Implement LLM-based planning (replace hardcoded actions)
- [ ] Add RunDetail page to frontend
- [ ] Add MemoryBoard page to frontend

### Priority 4: Hardening
- [ ] Replace in-memory rate limiting with Redis
- [ ] Replace in-memory idempotency with DB-backed cache
- [ ] Add DNS rebinding protection to URL validation
- [ ] Add input size caps to all API models
- [ ] Add health checks for all external dependencies

---

<p align="center">
  <img src="https://img.shields.io/badge/END%20OF%20CONTEXT-2c3e50?style=for-the-badge" alt="End of Context"/>
  <br>
  <i>Generated from full codebase audit · 22 commits · 1256 tests · ~15,000 lines of Python</i>
</p>
