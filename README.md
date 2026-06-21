<p align="center">
  <br>
  <img src="https://img.shields.io/badge/🧠-AGENTIC--LOOP-6C5CE7?style=for-the-badge&logo=python&logoColor=white&labelColor=2D3436" alt="Agentic Loop" width="400"/>
  <br>
  <br>
</p>

<h1 align="center">
  <img src="https://img.shields.io/badge/GOVERNANCE-FIRST-ff6b6b?style=for-the-badge" alt="Governance First"/>
  <img src="https://img.shields.io/badge/CLOSED--LOOP-00b894?style=for-the-badge" alt="Closed Loop"/>
  <img src="https://img.shields.io/badge/AGENT-PLATFORM-0984e3?style=for-the-badge" alt="Agent Platform"/>
</h1>

<p align="center">
  <img src="https://img.shields.io/badge/VERSION-0.1.0-blue?style=flat-square&logo=github" alt="Version"/>
  <img src="https://img.shields.io/badge/PYTHON-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FASTAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/LANGGRAPH-0.2+-FF6B6B?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/POSTGRES-15+-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/LANGFUSE-2.40+-FFD93D?style=flat-square&logo=langfuse&logoColor=black" alt="Langfuse"/>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/TESTS-1256-00b894?style=flat-square" alt="Tests"/>
  <img src="https://img.shields.io/badge/FEATURES-220-e17055?style=flat-square" alt="Features"/>
  <img src="https://img.shields.io/badge/COVERAGE-73%25-00b894?style=flat-square" alt="Coverage"/>
  <img src="https://img.shields.io/badge/LOC-~15K-636e72?style=flat-square" alt="Lines of Code"/>
</p>

<p align="center">
  <i>A production-grade, governance-first, closed-loop agent platform that executes<br>
  bounded AI tasks through a stateful runtime with validation, checkpoints, memory,<br>
  reflection, and fleet orchestration.</i>
</p>

<p align="center">
  <a href="#-quickstart">Quickstart</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-testing">Tests</a> •
  <a href="#-deployment">Deploy</a> •
  <a href="#-contributing">Contributing</a>
</p>

---

<br>

<p align="center">
  <img src="https://img.shields.io/badge/⚡-LIGHTNING%20MODE-FDCB6E?style=for-the-badge&logo=zap&logoColor=black" alt="Lightning Mode"/>
</p>

<table align="center">
<tr>
<td align="center" width="180">

### 🔒 Governance
Risk-tier evaluation<br>before every tool call<br><br>
<img src="https://img.shields.io/badge/POLICY-ENGINE-00b894?style=flat-square" alt="Policy"/>

</td>
<td align="center" width="180">

### 🔄 Closed-Loop
Every run reaches a<br>terminal state<br><br>
<img src="https://img.shields.io/badge/8%20STATES-6C5CE7?style=flat-square" alt="States"/>

</td>
<td align="center" width="180">

### 📊 Observability
Langfuse tracing on<br>every LLM call<br><br>
<img src="https://img.shields.io/badge/TRACING-FFD93D?style=flat-square&logoColor=black" alt="Tracing"/>

</td>
<td align="center" width="180">

### 🧠 Memory
Policy-governed store<br>with write filters<br><br>
<img src="https://img.shields.io/badge/PGVECTOR-0984e3?style=flat-square" alt="Memory"/>

</td>
</tr>
</table>

---

<br>

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │ Next.js  │  │   CLI    │  │   SDK    │  │  Webhooks    │   │
│  │Dashboard │  │          │  │          │  │              │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
├───────┼──────────────┼──────────────┼───────────────┼───────────┤
│       └──────────────┴──────────────┴───────────────┘           │
│                          ↓ HTTPS                                │
│                   ┌──────────────┐                               │
│                   │   FastAPI    │  ← CORS · Security Headers   │
│                   │   Gateway    │  ← Rate Limiting             │
│                   │              │  ← Idempotency               │
│                   └──────┬───────┘  ← Request Tracing           │
│                          │                                       │
├──────────────────────────┼───────────────────────────────────────┤
│                    MIDDLEWARE STACK                               │
│  ┌────────┐ ┌──────────┐ ┌──────────┐ ┌─────┐ ┌─────────────┐ │
│  │Rate    │→│Idempoten-│→│ Tracing  │→│ RLS │→│    RBAC     │ │
│  │Limit   │ │   city   │ │(Langfuse)│ │     │ │  (JWT)      │ │
│  └────────┘ └──────────┘ └──────────┘ └─────┘ └─────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│                      API ROUTES (15)                             │
│  /runs  /approvals  /memory  /harness  /export  /webhooks      │
│  /fleet /graphify   /ws      /governance /notifications /logs  │
├──────────────────────────────────────────────────────────────────┤
│                     CORE RUNTIME                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                  LangGraph State Machine                    │ │
│  │                                                            │ │
│  │  ┌─────────┐   ┌──────────┐   ┌─────────┐               │ │
│  │  │ Intake  │──▶│  Policy  │──▶│  Plan   │               │ │
│  │  │         │   │  Check   │   │         │               │ │
│  │  └─────────┘   └──────────┘   └────┬────┘               │ │
│  │                                     │                     │ │
│  │  ┌──────────┐   ┌─────────┐   ┌────▼────┐               │ │
│  │  │ Validate │◀──│Execute  │◀──│Validn   │               │ │
│  │  │          │   │ (LLM)   │   │ Gate    │               │ │
│  │  └────┬─────┘   └─────────┘   └─────────┘               │ │
│  │       │                                                   │ │
│  │  ┌────▼─────┐   ┌─────────┐   ┌─────────┐               │ │
│  │  │CheckPoint│──▶│Reflect  │──▶│ Decide  │──▶ END        │ │
│  │  │          │   │         │   │         │               │ │
│  │  └──────────┘   └─────────┘   └─────────┘               │ │
│  └────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│                    DOMAIN MODULES                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │Governance│ │Resilience│ │  Memory  │ │  Fleet/Graphify  │  │
│  │  Policy  │ │ Circuit  │ │  Store   │ │  Orchestration   │  │
│  │  Engine  │ │ Breaker  │ │  + TTL   │ │                  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│                    INFRASTRUCTURE                                │
│  ┌────────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐  │
│  │PostgreSQL  │  │  Redis  │  │ Supabase │  │   Langfuse   │  │
│  │+ pgvector  │  │(planned)│  │  (SBaaS) │  │ (tracing)    │  │
│  └────────────┘  └─────────┘  └──────────┘  └──────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

---

<br>

## 🚀 Quickstart

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ with pgvector extension
- Node.js 18+ (for frontend)
- Langfuse account (optional, for tracing)

### 1. Clone & Install

```bash
git clone https://github.com/your-org/agentic-loop-platform.git
cd agentic-loop-platform

# Python dependencies
pip install -e ".[dev]"

# Frontend
cd apps/web && npm install && cd ../..
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values:
#   DATABASE_URL, SECRET_KEY, LLM_API_KEY
```

### 3. Setup Database

```bash
# Start Postgres (Docker)
docker run -d --name agentic-pg \
  -e POSTGRES_USER=agentic \
  -e POSTGRES_PASSWORD=agentic_dev \
  -e POSTGRES_DB=agentic_loop \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Run migrations
alembic upgrade head
```

### 4. Start Services

```bash
# Backend API
uvicorn apps.api.main:app --reload --port 8000

# Frontend (new terminal)
cd apps/web && npm run dev
```

### 5. Verify

```bash
# Health check
curl http://localhost:8000/health

# OpenAPI docs
open http://localhost:8000/docs
```

---

<br>

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=packages --cov=apps --cov-report=html

# Specific module
pytest tests/security/ -v
pytest tests/governance/ -v
pytest tests/runtime/ -v
```

### Test Breakdown

<table align="center">
<tr>
<th>Module</th><th>Tests</th><th>Real</th><th>Vacuous</th><th>Coverage</th>
</tr>
<tr><td>Runtime</td><td>60</td><td>55</td><td>5</td><td>73%</td></tr>
<tr><td>Security</td><td>35</td><td>32</td><td>3</td><td>68%</td></tr>
<tr><td>Governance</td><td>22</td><td>22</td><td>0</td><td>85%</td></tr>
<tr><td>Resilience</td><td>20</td><td>20</td><td>0</td><td>92%</td></tr>
<tr><td>Memory</td><td>15</td><td>8</td><td>7</td><td>45%</td></tr>
<tr><td>API Routes</td><td>80</td><td>50</td><td>30</td><td>55%</td></tr>
<tr><td>Infrastructure</td><td>10</td><td>10</td><td>0</td><td>78%</td></tr>
<tr><td>Other</td><td>1014</td><td>853</td><td>161</td><td>70%</td></tr>
<tr><td><b>Total</b></td><td><b>1256</b></td><td><b>~1050</b></td><td><b>~206</b></td><td><b>73%</b></td></tr>
</table>

---

<br>

## 🔐 Security

### Middleware Stack

```
Request → Rate Limit → Idempotency → Tracing → RLS → RBAC → Route Handler
```

### Implemented Controls

| Layer | Implementation |
|-------|---------------|
| **Authentication** | PyJWT tokens with per-manager secret keys |
| **Authorization** | RBAC middleware with role-based permission mapping |
| **CORS** | Configurable origins via `ALLOWED_ORIGINS` env var |
| **Headers** | CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| **Rate Limiting** | Sliding window per tenant |
| **Idempotency** | POST/PUT/PATCH/DELETE deduplication |
| **SSRF Protection** | URL validation blocking private IPs |
| **Encryption** | Fernet encryption vault for secrets |
| **Audit** | Governance events are append-only |
| **Tracing** | Langfuse traces on every LLM call |

### Security Status

<img src="https://img.shields.io/badge/JWT-PyJWT-00b894?style=flat-square" alt="JWT"/>
<img src="https://img.shields.io/badge/ENCRYPTION-Fernet-00b894?style=flat-square" alt="Encryption"/>
<img src="https://img.shields.io/badge/CORS-ENABLED-00b894?style=flat-square" alt="CORS"/>
<img src="https://img.shields.io/badge/HEADERS-ENABLED-00b894?style=flat-square" alt="Headers"/>
<img src="https://img.shields.io/badge/SSRF-PROTECTED-00b894?style=flat-square" alt="SSRF"/>
<img src="https://img.shields.io/badge/RLS-NEEDS%20FIX-FDCB6E?style=flat-square" alt="RLS"/>
<img src="https://img.shields.io/badge/SQL%20INJECTION-NEEDS%20FIX-FDCB6E?style=flat-square" alt="SQL"/>

---

<br>

## 📡 API Reference

### Runs

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/runs` | Create a new run |
| `GET` | `/runs` | List all runs |
| `GET` | `/runs/{run_id}` | Get run details |
| `PATCH` | `/runs/{run_id}` | Update a run |
| `POST` | `/runs/{run_id}/execute` | Execute a run |
| `GET` | `/runs/metrics/summary` | Aggregated metrics |

### Governance

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/governance/events` | List governance events |
| `GET` | `/governance/summary` | Governance summary |
| `POST` | `/governance/approve/{id}` | Approve an action |
| `POST` | `/governance/deny/{id}` | Deny an action |

### Memory

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/memory` | Write memory |
| `GET` | `/memory` | List memories |
| `GET` | `/memory/search` | Search by keywords |

### WebSocket

| Protocol | Endpoint | Description |
|----------|----------|-------------|
| `WS` | `/ws/runs?token=<jwt>` | Authenticated run updates |
| `WS` | `/ws/{client_id}` | Legacy (unauthenticated) |

---

<br>

## 🗂️ Project Structure

```
agentic-loop-platform/
│
├── 📄 CONTEXT.md              # Full project history & status
├── 📄 README.md               # This file
├── 📄 pyproject.toml          # Dependencies & config
├── 📄 alembic.ini             # DB migration config
├── 📄 feature_list.json       # 220 tracked features
│
├── 📁 specs/
│   └── 📄 agentic-loop-platform.md   # Architecture spec (543 lines)
│
├── 📁 alembic/                # Database migrations
│   ├── 📄 env.py
│   └── 📁 versions/
│       ├── 📄 001_initial_schema.py
│       └── 📄 002_notifications_scheduler.py
│
├── 📁 apps/
│   ├── 📁 api/                # FastAPI backend
│   │   ├── 📄 main.py         # App entry + middleware
│   │   ├── 📁 middleware/     # Tracing, security
│   │   └── 📁 routes/        # 15 API routers
│   └── 📁 web/                # Next.js frontend
│       └── 📁 app/            # 8 pages
│
├── 📁 packages/               # 28 Python packages
│   ├── 📁 runtime/            # Core agent runtime
│   ├── 📁 security/           # Auth, RBAC, secrets
│   ├── 📁 governance/         # Policy engine
│   ├── 📁 resilience/         # Circuit breaker
│   ├── 📁 memory/             # Knowledge store
│   ├── 📁 evals/              # Evaluation harness
│   ├── 📁 schemas/            # ORM models
│   ├── 📁 middleware/         # Rate limit, idempotency
│   ├── 📁 infrastructure/     # Supabase, external
│   ├── 📁 logging/            # Structured logging
│   ├── 📁 websocket/          # Connection manager
│   ├── 📁 scheduler/          # Job scheduling
│   ├── 📁 notifications/      # Webhook delivery
│   ├── 📁 fleet/              # Multi-agent orchestration
│   └── 📁 graphify/           # Knowledge graph
│
└── 📁 tests/                  # 1256 tests
    ├── 📁 runtime/
    ├── 📁 security/
    ├── 📁 governance/
    ├── 📁 resilience/
    ├── 📁 memory/
    ├── 📁 evals/
    ├── 📁 middleware/
    ├── 📁 infrastructure/
    ├── 📁 websocket/
    ├── 📁 notifications/
    ├── 📁 fleet/
    └── 📁 graphify/
```

---

<br>

## 🎯 Key Features

<table>
<tr>
<td width="50%">

### 🧠 Runtime
- **LangGraph state machine** with 9 nodes
- **Real LLM execution** via OpenAI/9router
- **Budget enforcement** (cost, iterations, time)
- **Checkpoint save/load** for state persistence
- **8 terminal states** for clean shutdown

</td>
<td width="50%">

### 🔒 Security
- **PyJWT** with per-manager secret keys
- **RBAC** role-based access control
- **Fernet encryption** vault for secrets
- **CORS** with configurable origins
- **SSRF protection** URL validation

</td>
</tr>
<tr>
<td>

### 📊 Observability
- **Langfuse** tracing on every LLM call
- **Structured JSON** logging
- **In-memory log buffer** for API access
- **Cost estimation** per token count
- **Request tracing** middleware

</td>
<td>

### 🔄 Resilience
- **Circuit breaker** (CLOSED→OPEN→HALF_OPEN)
- **Rate limiting** sliding window
- **Idempotency** for write operations
- **Graceful shutdown** with request tracking
- **Error boundaries** with fallback behavior

</td>
</tr>
<tr>
<td>

### 🧠 Memory
- **CRUD with deduplication** (content hash)
- **TTL-based expiry** for ephemeral memories
- **Confidence-based write filters**
- **Graph concept linking**
- **Source attribution** for audit trail

</td>
<td>

### 🏢 Fleet
- **Multi-agent orchestration** coordinator
- **Swarm-based parallel** execution
- **Security gateway** for tool access
- **Compliance layer** for audit trails
- **Graph-aware task routing**

</td>
</tr>
</table>

---

<br>

## 🛠️ Development

### Code Quality

```bash
# Linting
ruff check packages/ apps/ tests/

# Type checking
mypy packages/ apps/

# Formatting
ruff format packages/ apps/ tests/
```

### Adding a New Route

```python
# apps/api/routes/my_route.py
from fastapi import APIRouter, Depends
from packages.security.dependencies import get_current_user

router = APIRouter(prefix="/my-route", tags=["my-route"])

@router.get("/")
async def list_items(user = Depends(get_current_user)):
    return {"items": []}
```

### Adding a New Test

```python
# tests/my_module/test_my_feature.py
import pytest
from packages.my_module import my_function

class TestMyFeature:
    def test_basic_behavior(self):
        result = my_function("input")
        assert result == "expected"
```

---

<br>

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [CONTEXT.md](./CONTEXT.md) | Full project history, session logs, honest assessment |
| [specs/agentic-loop-platform.md](./specs/agentic-loop-platform.md) | Architecture spec (543 lines) |
| [docs/hardening-plan.md](./docs/hardening-plan.md) | 11-section security guide |
| [feature_list.json](./feature_list.json) | 220 tracked features |
| `/docs` (API) | Interactive OpenAPI documentation |
| `/redoc` (API) | ReDoc API documentation |

---

<br>

## 🗺️ Roadmap

### ✅ Done
- [x] Core runtime with LangGraph
- [x] Auth system (PyJWT + Fernet)
- [x] Policy engine with risk tiers
- [x] Circuit breaker
- [x] Memory store with dedup
- [x] 15 API routes
- [x] WebSocket with auth
- [x] Next.js dashboard (8 pages)
- [x] 1256 tests
- [x] Security hardening (10 findings fixed)

### 🔄 In Progress
- [ ] Fix RLS middleware
- [ ] Fix SQL injection pattern
- [ ] Integration tests with real DB

### 📋 Planned
- [ ] Docker + docker-compose
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Vector similarity search for memory
- [ ] Real cron parsing in scheduler
- [ ] LLM-based planning (replace hardcoded actions)
- [ ] RunDetail + MemoryBoard frontend pages
- [ ] Redis for distributed rate limiting
- [ ] Input size caps on all API models

---

<br>

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

### Commit Convention

```
feat:     New feature
fix:      Bug fix
docs:     Documentation
test:     Adding tests
refactor: Code refactoring
security: Security improvement
chore:    Maintenance
```

---

<br>

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<br>

<p align="center">
  <img src="https://img.shields.io/badge/BUILT%20WITH-%E2%9D%A4%EF%B8%8F-FF6B6B?style=for-the-badge" alt="Built with Love"/>
  <br><br>
  <img src="https://img.shields.io/badge/PYTHON-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/FASTAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/LANGGRAPH-FF6B6B?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph"/>
  <img src="https://img.shields.io/badge/POSTGRES-15+-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL"/>
  <img src="https://img.shields.io/badge/NEXT.JS-14-000000?style=flat-square&logo=next.js&logoColor=white" alt="Next.js"/>
  <img src="https://img.shields.io/badge/LANGFUSE-FFD93D?style=flat-square&logoColor=black" alt="Langfuse"/>
</p>

<p align="center">
  <sub>Made with 🧠 by the Agentic Loop Team</sub>
</p>
