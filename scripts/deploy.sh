#!/bin/bash
set -e

echo "=== Agentic Loop Platform - Deployment ==="

ENV=${1:-staging}
echo "Deploying to: $ENV"

echo ""
echo "1. Running migrations..."
alembic upgrade head

echo ""
echo "2. Running tests..."
python -m pytest tests/ -v --tb=short

echo ""
echo "3. Building Docker image..."
docker build -t agentic-loop-api:$ENV -f infra/docker/Dockerfile .

echo ""
echo "4. Stopping existing containers..."
docker-compose -f infra/docker/docker-compose.$ENV.yml down

echo ""
echo "5. Starting services..."
docker-compose -f infra/docker/docker-compose.$ENV.yml up -d

echo ""
echo "6. Waiting for health check..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health | grep -q '"status":"ok"'; then
        echo "API is healthy!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

echo ""
echo "=== Deployment complete ==="
