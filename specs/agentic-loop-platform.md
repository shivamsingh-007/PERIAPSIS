# Agentic Loop Platform

## Objective

Build a production-grade, governance-first, closed-loop agent platform that executes bounded tasks through a stateful runtime with validation, checkpoints, memory, reflection, self-learning, and fleet orchestration. The system targets AI/ML platform teams who need a reusable runtime for multiple internal products. Reliability, observability, and governance are the priorities—not maximum autonomy.

---

## Step 1: Architecture Review

### Staff-Level Review Summary

1. **Closed-loop design is correct** — the explicit terminal states (SUCCESS, PARTIAL_SUCCESS, ESCALATED_TO_HUMAN, STOP_BUDGET, STOP_POLICY, STOP_NO_PROGRESS, FAIL_TOOLING, FAIL_INVARIANT) provide clear stop conditions that most agent frameworks lack.
2. **Separation of reasoning and control is critical** — keeping business rules deterministic while LLM reasoning stays probabilistic makes the system debuggable and auditable.
3. **Observability-first is the right call** — Langfuse integration before autonomy depth prevents the "invisible failure" pattern common in production agents.
4. **Memory as a managed subsystem is necessary** — treating memory as a policy-governed store with write filters, source attribution, and TTL prevents hallucination propagation.
5. **Fleet orchestration is over-scoped for v1** — parallel workers with git worktree isolation adds significant complexity; defer to v1.1+ after single-agent runtime is proven.
6. **Self-learning loop needs stricter promotion gates** — the pipeline from reflection to skill/rule promotion must require human approval for v1; autonomous promotion is a v2 feature.
7. **Hook system is well-designed** — deterministic extension points around every major event enable custom policy checks, metering, and notifications without modifying core loops.
8. **Schema is solid but needs idempotency keys** — the run_steps table needs a unique constraint on (run_id, node_name, step_number) to prevent duplicate writes on replay.

### Issues & Improvements

| Area | Issue | Risk | Recommendation | Priority |
|------|-------|------|----------------|----------|
| State Machine | No explicit state machine definition — transitions are implied by pseudocode | Runtime bugs from undefined transitions | Define an enum of states and a transition table in code | P0 |
| Checkpointing | Checkpoint after every node may be too frequent for v1 | Performance overhead on high-frequency nodes | Checkpoint only on state mutation nodes; add a `checkpoint: bool` flag to node config | P1 |
| Memory | No deduplication strategy for memory_items | Vector store bloat, retrieval latency | Add content hashing and merge-on-write for duplicate memories | P1 |
| Governance | Risk tier approval matrix is YAML-only — no runtime enforcement hook | Policies exist but aren't enforced | Build a `PolicyEngine` class that evaluates risk tier before each tool call | P0 |
| Fleet | Fleet orchestration adds merge conflict resolution, budget slicing, and cross-agent logging | v1 scope creep, 3-6 months added timeline | Defer fleet to v1.1; keep single-agent runtime solid first | P1 |
| Self-Learning | Promotion pipeline lacks rollback mechanism | Bad lessons permanently affect system | Add versioning to skills/rules and a rollback API | P1 |
| Observability | No cost attribution per run_step | Can't identify expensive operations | Add `cost_usd` column to run_steps, compute from token counts | P1 |
| Schema | No row-level security setup for multi-tenant isolation | Data leakage between tenants | Add RLS policies on all tables with tenant_id foreign key | P0 |
| Hooks | Hook failure handling is undefined | A failing hook could crash the entire run | Hooks must be async, with timeout and fallback-to-continue semantics | P0 |
| Terminal States | No metrics aggregation for terminal states | Can't compute success rates across runs | Add a materialized view or summary table for run outcomes | P2 |

---

## Step 2: Concrete Build Plan

### Milestone Roadmap

#### Milestone 0: Foundation (Week 1-2)
**Objective:** Project skeleton, local dev environment, core data models.

**Key Deliverables:**
- Repository structure with all packages
- FastAPI app with health check endpoint
- Postgres + pgvector running in Docker
- SQLAlchemy ORM models for all core tables
- Alembic migration setup
- LangGraph basic graph with placeholder nodes
- Langfuse tracing wired into FastAPI middleware

**Exit Criteria:**
- `docker-compose up` starts all services
- `/health` returns 200
- All tables created via migrations
- Langfuse dashboard shows traces from health check

#### Milestone 1: Core Runtime (Week 3-4)
**Objective:** Closed-loop execution with checkpointing, budgets, and stop conditions.

**Key Deliverables:**
- Main loop graph with plan → execute → validate → checkpoint nodes
- Budget enforcement (iteration, cost, time limits)
- Terminal state machine with all 8 states
- Run and RunStep ORM models with full CRUD
- Checkpoint persistence after every state-mutating node
- No-progress detection

**Exit Criteria:**
- Submit a goal via API → run completes with terminal state
- Budget limits enforced (run stops at max iterations)
- Every step checkpointed and recoverable after crash
- Langfuse traces show full execution path

#### Milestone 2: Governance & Validation (Week 5-6)
**Objective:** Policy engine, validation gates, human-in-the-loop.

**Key Deliverables:**
- PolicyEngine class with risk tier evaluation
- Validation gate node in graph (checks tool eligibility)
- Human approval workflow for medium/high risk actions
- Governance event logging
- Approval API endpoints

**Exit Criteria:**
- High-risk tool calls require human approval
- Policy violations logged as governance_events
- Approval workflow functional via API

#### Milestone 3: Memory & Reflection (Week 7-8)
**Objective:** Memory retrieval/write with policies, reflection loop.

**Key Deliverables:**
- Memory write pipeline with source attribution, confidence scoring, TTL
- Memory retrieval by task context
- Reflection nodes (step, error, strategy, final)
- Memory deduplication via content hashing
- Lesson promotion workflow (requires approval)

**Exit Criteria:**
- Memory written and retrieved correctly
- Reflections generated after each step
- Deduplication prevents duplicate memories
- Lessons only promoted with human approval

#### Milestone 4: Harness & Observability (Week 9-10)
**Objective:** Evaluation harness, metrics, admin dashboard.

**Key Deliverables:**
- Eval scenario runner (5-10 scenario types)
- Harness scoring and gate blocking
- Metrics dashboard (success rate, cost per run, tool error rate)
- Run explorer in Next.js admin UI
- Trace viewer with Langfuse integration

**Exit Criteria:**
- Eval suite runs against graph and produces scores
- Dashboard shows real-time metrics
- Can drill down from dashboard → run → step → trace

#### Milestone 5: Polish & Hardening (Week 11-12)
**Objective:** Production readiness, documentation, performance.

**Key Deliverables:**
- Row-level security for multi-tenant isolation
- Idempotency keys on critical write paths
- Hook system with timeout/fallback semantics
- Performance testing (P95 < 300ms orchestration overhead)
- API documentation
- Deployment scripts

**Exit Criteria:**
- All P0 issues from architecture review resolved
- Performance benchmarks pass
- Deployed to staging environment
- Documentation complete

### Module Breakdown

| Module | Responsibilities | Key APIs/Objects | Dependencies |
|--------|-----------------|------------------|--------------|
| `runtime/graph` | LangGraph state definition, node implementations, graph construction | `AgentState`, `build_main_graph()`, `build_memory_graph()` | langgraph, runtime/state |
| `runtime/state` | Typed state objects, terminal state enum, state transitions | `RunState`, `TerminalState`, `StateTransition` | pydantic |
| `runtime/checkpoint` | Postgres checkpoint persistence, recovery, checkpoint diffing | `CheckpointStore.save()`, `CheckpointStore.load()`, `CheckpointStore.diff()` | sqlalchemy, runtime/state |
| `governance/policy` | Risk tier evaluation, approval workflows, policy versioning | `PolicyEngine.evaluate()`, `RiskTier`, `ApprovalRequest` | runtime/state, db |
| `governance/events` | Governance event logging, audit trail | `GovernanceEvent.create()`, `EventQuery` | sqlalchemy |
| `memory/store` | Memory CRUD, vector search, deduplication, TTL management | `MemoryStore.write()`, `MemoryStore.retrieve()`, `MemoryStore.deduplicate()` | sqlalchemy, pgvector, runtime/state |
| `memory/write_filter` | Memory write policies, source attribution, confidence scoring | `WriteFilter.evaluate()`, `MemoryCandidate` | governance/policy |
| `reflection/critic` | Step, error, strategy, and final reflection nodes | `CriticNode.run()`, `ReflectionResult` | runtime/state, memory/store |
| `harness/eval` | Scenario execution, metric computation, gate blocking | `EvalRunner.run()`, `HarnessScore`, `GateCheck` | runtime/graph |
| `harness/metrics` | Metric aggregation, dashboards, alerts | `MetricsCollector.record()`, `MetricQuery` | sqlalchemy, langfuse |
| `observability/tracing` | Langfuse integration, trace wrapping, cost tracking | `TracingMiddleware`, `TraceContext` | langfuse |
| `connectors/base` | Connector interface, tool execution, permission checks | `BaseConnector`, `ToolCall`, `ToolResult` | governance/policy |
| `api/routes` | FastAPI endpoints for runs, approvals, memory, governance | `runs.py`, `approvals.py`, `memory.py` | all modules |
| `api/middleware` | Auth, rate limiting, request tracing | `AuthMiddleware`, `RateLimitMiddleware` | fastapi |

### Initial LangGraph Design

#### Main Loop Graph

```
[intake] → [policy_check] → [plan] → [execute] → [validate] → [checkpoint] → [reflect] → [decide]
                                                                                    ↓
                                                                              [escalate] or [stop]
```

**Nodes:**
- `intake`: Parses goal, classifies risk, initializes run state. **Interruptible: No.**
- `policy_check`: Evaluates governance policies, checks budget. **Interruptible: No.**
- `plan`: LLM generates action plan. **Interruptible: No.**
- `execute`: Runs tool or subagent. **Interruptible: Yes (for HITL on high-risk actions).**
- `validate`: Checks output against invariants. **Interruptible: No.**
- `checkpoint`: Persists state to Postgres. **Interruptible: No.**
- `reflect`: Generates step reflection. **Interruptible: No.**
- `decide`: Determines next state (continue/escalate/stop). **Interruptible: No.**
- `escalate`: Sends to human approval. **Interruptible: Yes (waiting for response).**

**Inputs:** `RunState` (goal, budget, policies, memory context)
**Outputs:** `RunState` with `terminal_state` set

#### Memory Loop Graph

```
[capture] → [classify] → [score] → [filter] → [store] → [index]
```

**Nodes:**
- `capture`: Extracts candidate memory from run step. **Interruptible: No.**
- `classify`: Determines memory type (fact/lesson/preference). **Interruptible: No.**
- `score`: Assigns confidence, relevance, sensitivity scores. **Interruptible: No.**
- `filter`: Applies write policies. **Interruptible: No.**
- `store`: Persists to Postgres + pgvector. **Interruptible: No.**
- `index`: Updates vector embeddings. **Interruptible: No.**

#### Reflection Loop Graph

```
[step_reflect] → [error_reflect] → [strategy_reflect] → [final_reflect] → [promote]
```

**Nodes:**
- `step_reflect`: Did the last action move forward? **Interruptible: No.**
- `error_reflect`: Why did failure happen? **Interruptible: No.**
- `strategy_reflect`: Should plan change? **Interruptible: No.**
- `final_reflect`: What lesson to retain? **Interruptible: No.**
- `promote`: Submit lesson for approval. **Interruptible: Yes (approval gate).**

#### Harness Loop Graph

```
[select_scenario] → [execute] → [score] → [aggregate] → [gate_check]
```

**Nodes:**
- `select_scenario`: Picks next eval scenario. **Interruptible: No.**
- `execute`: Runs scenario against graph. **Interruptible: No.**
- `score`: Computes metrics. **Interruptible: No.**
- `aggregate`: Sums scores across scenarios. **Interruptible: No.**
- `gate_check`: Pass/fail against thresholds. **Interruptible: No.**

### Data Schema Refinement

#### Write-Critical Tables (Transactional, Idempotent)

```sql
-- Core run tracking
CREATE TABLE runs (
    run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    goal TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    terminal_state VARCHAR(50),
    risk_tier VARCHAR(20) NOT NULL DEFAULT 'low',
    budget_policy_id UUID,
    governance_policy_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    UNIQUE(tenant_id, run_id)
);

-- Step tracking with idempotency
CREATE TABLE run_steps (
    step_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(run_id),
    tenant_id UUID NOT NULL,
    step_number INTEGER NOT NULL,
    node_name VARCHAR(100) NOT NULL,
    input_state_jsonb JSONB,
    output_state_jsonb JSONB,
    action_type VARCHAR(50),
    validation_result JSONB,
    cost_tokens_in INTEGER DEFAULT 0,
    cost_tokens_out INTEGER DEFAULT 0,
    cost_usd DECIMAL(10,6) DEFAULT 0,
    latency_ms INTEGER,
    checkpoint_ref VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, run_id, step_number),
    UNIQUE(tenant_id, run_id, node_name, step_number)
);

-- Memory with deduplication
CREATE TABLE memory_items (
    memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    scope VARCHAR(50) NOT NULL,
    scope_ref UUID,
    memory_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding VECTOR(1536),
    source_ref JSONB,
    confidence DECIMAL(3,2) DEFAULT 0.5,
    ttl_days INTEGER DEFAULT 365,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, content_hash)
);

-- Governance events (immutable audit log)
CREATE TABLE governance_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(run_id),
    tenant_id UUID NOT NULL,
    control_domain VARCHAR(100) NOT NULL,
    policy_rule VARCHAR(255) NOT NULL,
    decision VARCHAR(50) NOT NULL,
    reviewer UUID,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Reflections
CREATE TABLE reflections (
    reflection_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(run_id),
    step_id UUID REFERENCES run_steps(step_id),
    tenant_id UUID NOT NULL,
    critic_type VARCHAR(50) NOT NULL,
    finding TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL,
    confidence DECIMAL(3,2),
    recommended_action TEXT,
    promoted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

#### Analytic/Derived Tables

```sql
-- Harness scores (append-only, no transactions needed)
CREATE TABLE harness_scores (
    score_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(run_id),
    scenario_id VARCHAR(100) NOT NULL,
    tenant_id UUID NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4) NOT NULL,
    threshold DECIMAL(10,4),
    pass_fail BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fleet jobs (deferred to v1.1)
CREATE TABLE fleet_jobs (
    job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_run_id UUID NOT NULL REFERENCES runs(run_id),
    tenant_id UUID NOT NULL,
    worker_agent VARCHAR(100),
    workspace_ref VARCHAR(255),
    job_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    budget_slice DECIMAL(10,6),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Skills (versioned, approval-gated)
CREATE TABLE skills (
    skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    content_md TEXT NOT NULL,
    scope VARCHAR(50) NOT NULL,
    owner UUID NOT NULL,
    approval_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, name, version)
);
```

### Observability & Evaluation Integration

#### Langfuse Wiring

**FastAPI Middleware:**
- Wrap every request with `langfuse.trace()` in a FastAPI middleware
- Set `trace.user_id` from auth context
- Set `trace.tags` with tenant_id, run_id

**LangGraph Nodes:**
- Each node call wrapped with `langfuse.generation()` for LLM calls
- Each tool call wrapped with `langfuse.span()` with input/output
- Log `cost_usd` and `latency_ms` as trace metadata

**Events to Log:**
| Hook | What to Log | Langfuse Method |
|------|-------------|-----------------|
| `before_run_start` | Goal, risk tier, budget | trace metadata |
| `before_tool_call` | Tool name, input params | span start |
| `after_tool_call` | Output, latency, tokens | span end |
| `before_checkpoint` | State snapshot | span |
| `after_memory_write` | Memory type, confidence | span |
| `after_reflection` | Finding, severity | span |
| `after_incident` | Incident details | trace event |

**Metrics to Define First:**
1. `run_success_rate` — % of runs reaching SUCCESS terminal state
2. `cost_per_run` — average USD per completed run
3. `tool_error_rate` — % of tool calls failing
4. `no_progress_stop_rate` — % of runs stopped for no progress
5. `human_escalation_rate` — % of runs requiring human approval
6. `p95_orchestration_overhead` — excluding LLM/tool latency

#### Eval Harness

**Scenario Types:**

| # | Scenario | What It Tests | Execution |
|---|----------|---------------|-----------|
| 1 | Simple Q&A | Basic goal completion | Submit goal, verify SUCCESS |
| 2 | Budget enforcement | Stop at iteration/cost limit | Submit expensive goal, verify STOP_BUDGET |
| 3 | Policy violation | Governance blocking | Submit restricted goal, verify STOP_POLICY |
| 4 | Tool failure recovery | Retry and fallback | Mock tool failure, verify recovery |
| 5 | Memory retrieval | Relevant context loaded | Submit goal with prior memory, verify memory used |
| 6 | Human escalation | HITL workflow | Submit high-risk goal, verify ESCALATED_TO_HUMAN |
| 7 | No-progress detection | Stuck loop detection | Submit goal that loops, verify STOP_NO_PROGRESS |
| 8 | Concurrent runs | Multi-tenant isolation | Submit parallel runs, verify no cross-tenant data |
| 9 | Crash recovery | Checkpoint restoration | Kill process mid-run, verify resume from checkpoint |
| 10 | Cost tracking | Accurate attribution | Submit run, verify cost_usd matches token usage |

**Execution:**
- Each scenario runs against the full graph in a test environment
- Scores recorded in `harness_scores` table
- Gate check blocks deploy if any critical scenario fails

---

## Step 3: First Implementation Tasks

### Repository Skeleton

```
agentic-loop-platform/
├── apps/
│   ├── api/
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── runs.py
│   │   │   ├── approvals.py
│   │   │   ├── memory.py
│   │   │   └── governance.py
│   │   └── middleware/
│   │       ├── auth.py
│   │       └── tracing.py
│   ├── worker/
│   │   └── celery_app.py
│   └── web/
│       ├── package.json
│       └── src/
├── packages/
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── graph.py
│   │   ├── state.py
│   │   └── checkpoint.py
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── policy.py
│   │   └── events.py
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── store.py
│   │   └── write_filter.py
│   ├── reflection/
│   │   ├── __init__.py
│   │   └── critic.py
│   ├── harness/
│   │   ├── __init__.py
│   │   ├── eval.py
│   │   └── metrics.py
│   ├── observability/
│   │   ├── __init__.py
│   │   └── tracing.py
│   ├── connectors/
│   │   ├── __init__.py
│   │   └── base.py
│   └── schemas/
│       ├── __init__.py
│       └── models.py
├── docs/
├── governance/
├── evals/
├── infra/
│   ├── docker/
│   │   ├── docker-compose.yml
│   │   └── Dockerfile
│   └── terraform/
├── scripts/
├── .env.example
├── pyproject.toml
├── alembic.ini
└── README.md
```

### Task List (Weeks 1-2)

| # | Task | Acceptance Criteria |
|---|------|---------------------|
| 1 | Initialize pyproject.toml with dependencies (fastapi, langgraph, sqlalchemy, langfuse, pgvector, pydantic) | `pip install -e .` succeeds, all imports work |
| 2 | Create docker-compose.yml with Postgres+pgvector, Redis | `docker-compose up` starts both services |
| 3 | Create .env.example with all required env vars | Documented, all vars have example values |
| 4 | Implement SQLAlchemy Base and engine setup | Connection to Postgres works, session factory created |
| 5 | Implement Run and RunStep ORM models | Models defined, `create_tables()` creates them |
| 6 | Implement MemoryItem, GovernanceEvent, Reflection, HarnessScore ORM models | All tables created via migration |
| 7 | Set up Alembic with initial migration | `alembic upgrade head` creates all tables |
| 8 | Create FastAPI app with health check endpoint | `GET /health` returns 200 with status info |
| 9 | Add Langfuse tracing middleware to FastAPI | Traces appear in Langfuse dashboard for every request |
| 10 | Implement typed RunState Pydantic model with terminal states | Model validates correctly, terminal states enum defined |
| 11 | Build LangGraph main loop skeleton with placeholder nodes | Graph compiles, can invoke with empty state |
| 12 | Implement checkpoint store (save/load/diff) | Checkpoints persist to Postgres, can recover state |
| 13 | Implement budget enforcement node | Run stops at max iterations/cost/time |
| 14 | Implement no-progress detection | Run stops after N rounds with no state change |
| 15 | Add run CRUD API endpoints | Create/read/update runs via REST |
| 16 | Write unit tests for state model, budget enforcement, checkpoint store | Tests pass, coverage > 80% for core modules |

---

## Step 4: Guardrails for Implementation

### Decisions We Will Not Revisit Lightly

1. **Closed-loop design is non-negotiable.** Every run must have a terminal state. No open-ended loops.
2. **Checkpoint after every state-mutating node.** Recovery is not optional.
3. **Separation of reasoning and control.** LLM calls never bypass policy checks.
4. **Typed state only.** No untyped `dict` or `Any` state blobs in the graph.
5. **Immutable audit logs.** governance_events are append-only, never updated or deleted.

### Anti-Patterns to Avoid

1. **Never embed governance logic in prompts.** Policy enforcement belongs in code, not in LLM instructions.
2. **Never let the agent bypass validation gates.** Even if it "knows" the answer is correct.
3. **Never use raw conversation history as memory.** Memory must go through the write pipeline.
4. **Never skip checkpointing for "performance."** The overhead is negligible vs. recovery cost.
5. **Never allow self-promotion of lessons without approval.** The self-learning loop requires human gates in v1.

### PR Review Criteria

1. **Must not reduce observability.** Every new node/tool call must have Langfuse tracing.
2. **Must preserve invariants.** No step without checkpoint, no write without policy check.
3. **Must include idempotency keys** on all write-critical database operations.
4. **Must not bypass the PolicyEngine.** All tool calls go through `policy_check` node.
5. **Must include tests** for any state machine transition or budget enforcement logic.
6. **Must not introduce typed state leaks.** No `Any` types in graph state definitions.

---

## Definition of Done

- [ ] All 5 milestones completed
- [ ] All P0 architecture issues resolved
- [ ] 10 eval scenarios passing
- [ ] P95 orchestration overhead < 300ms
- [ ] Langfuse traces for 100% of production runs
- [ ] Row-level security enabled on all tables
- [ ] API documentation complete
- [ ] Deployed to staging environment
- [ ] Admin UI functional (run explorer, trace viewer, metrics dashboard)
