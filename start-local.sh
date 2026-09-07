#!/bin/bash
# Nepal SMS - Quick Start Script for Local Development

set -e

echo "======================================"
echo "Nepal SMS - Local Development Setup"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}! Creating .env from .env.example${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env created${NC}"
fi

# Check if keys exist
if [ ! -f keys/private_key.pem ]; then
    echo -e "${YELLOW}! Generating RSA keys for JWT${NC}"
    mkdir -p keys
    openssl genrsa -out keys/private_key.pem 2048
    openssl rsa -in keys/private_key.pem -pubout -out keys/public_key.pem
    echo -e "${GREEN}✓ JWT keys generated${NC}"
fi

echo ""
echo "Step 1: Starting Infrastructure (PostgreSQL + Redis)"
echo "-------------------------------------------------------"
docker-compose up -d postgres redis

echo ""
echo "Waiting for services to be healthy..."
sleep 10

echo ""
echo "Step 2: Setting up Database"
echo "-------------------------------------------------------"
docker-compose run --rm backend python scripts/setup_database.py || {
    echo -e "${YELLOW}! Database setup failed or already completed${NC}"
}

echo ""
echo "Step 3: Starting Backend Services"
echo "-------------------------------------------------------"
docker-compose up -d auth-service tenant-service student-service academic-service calendar-service

echo ""
echo "Waiting for services to start..."
sleep 5

echo ""
echo "======================================"
echo "✓ Backend Services Started!"
echo "======================================"
echo ""
echo "Backend Services:"
echo "  - Auth Service:     http://localhost:8001/docs"
echo "  - Tenant Service:   http://localhost:8002/docs"
echo "  - Student Service:  http://localhost:8003/docs"
echo "  - Academic Service: http://localhost:8004/docs"
echo "  - Calendar Service: http://localhost:8016/docs"
echo ""
echo "Database:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis:      localhost:6379"
echo ""
echo "======================================"
echo "Now start the Frontend:"
echo "  cd frontend"
echo "  npm install"
echo "  npm run dev"
echo "======================================"
echo ""
echo "View logs: docker-compose logs -f auth-service"
echo "Stop services: docker-compose down"
echo ""
