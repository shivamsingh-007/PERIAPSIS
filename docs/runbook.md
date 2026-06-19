# Runbook: Common Operations

## Prerequisites

- Docker Desktop running
- Python 3.11+ installed
- Node.js 18+ installed
- Git installed

## 1. Local Development Setup

```bash
# Clone the repository
git clone https://github.com/shivamsingh-007/PERIAPSIS.git
cd PERIAPSIS

# Install Python dependencies
pip install -e ".[dev]"

# Start infrastructure
docker compose up -d

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn apps.api.main:app --reload --port 8000

# Start the frontend
cd apps/web && npm install && npm run dev
```

## 2. Database Operations

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1

# Check current version
alembic current
```

## 3. Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=packages --cov-report=html

# Run specific test file
pytest tests/test_memory_store.py

# Run in parallel
pytest -n auto
```

## 4. Fleet Operations

```bash
# Check fleet status
curl http://localhost:8000/fleet/status

# Submit a fleet job
curl -X POST http://localhost:8000/fleet/jobs \
  -H "Content-Type: application/json" \
  -d '{"goal": "Refactor auth module", "risk_tier": "medium"}'

# Check job status
curl http://localhost:8000/fleet/jobs/{job_id}
```

## 5. Graph Operations

```bash
# Build knowledge graph
curl -X POST http://localhost:8000/graph/build \
  -H "Content-Type: application/json" \
  -d '{"target_dir": ".", "force": true}'

# Query the graph
curl -X POST http://localhost:8000/graph/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How does authentication work?"}'

# Get architecture overview
curl http://localhost:8000/graph/architecture
```

## 6. Memory Operations

```bash
# Write a memory
curl -X POST http://localhost:8000/memory/write \
  -H "Content-Type: application/json" \
  -d '{"scope": "lesson", "content": "Always validate inputs"}'

# Search memories
curl http://localhost:8000/memory/search?q=validation

# Get graph-linked memories
curl http://localhost:8000/memory/graph-concept/auth
```

## 7. Monitoring

```bash
# Health check
curl http://localhost:8000/health

# View logs
docker compose logs -f api

# Check metrics
curl http://localhost:8000/harness/metrics
```

## 8. Troubleshooting

### Database Connection Issues
```bash
# Check Postgres status
docker compose ps postgres

# Restart Postgres
docker compose restart postgres

# Check connection
docker compose exec postgres psql -U agentic -d agentic_loop
```

### Memory Issues
```bash
# Check memory usage
curl http://localhost:8000/memory/stats

# Expire old memories
curl -X POST http://localhost:8000/memory/expire-old
```

### Fleet Issues
```bash
# Check worker status
curl http://localhost:8000/fleet/workers

# Restart fleet
curl -X POST http://localhost:8000/fleet/restart
```

## 9. Deployment

```bash
# Build production image
docker build -t agentic-loop:latest -f infra/docker/Dockerfile .

# Deploy to staging
./scripts/deploy.sh staging

# Deploy to production
./scripts/deploy.sh production
```

## 10. Emergency Procedures

### Rollback
```bash
# Rollback to previous version
git revert HEAD
git push

# Or rollback database
alembic downgrade -1
```

### Disable Feature
```bash
# Disable a feature flag
curl -X POST http://localhost:8000/features/{flag_name}/disable
```

### Circuit Breaker
```bash
# Check circuit breaker status
curl http://localhost:8000/resilience/circuit-breakers

# Reset circuit breaker
curl -X POST http://localhost:8000/resilience/circuit-breakers/{name}/reset
```
