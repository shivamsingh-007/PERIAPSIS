#!/bin/bash
# Dev server launcher for Agentic Loop Platform

set -e

echo "=== Agentic Loop Platform - Dev Server ==="

# Start infrastructure
echo "[1/3] Starting Postgres + Redis..."
docker-compose -f infra/docker/docker-compose.yml up -d

# Wait for Postgres
echo "Waiting for Postgres..."
sleep 3

# Run migrations
echo "[2/3] Running database migrations..."
alembic upgrade head

# Start API server
echo "[3/3] Starting FastAPI server..."
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

echo "=== Server started at http://localhost:8000 ==="
echo "=== API docs at http://localhost:8000/docs ==="
