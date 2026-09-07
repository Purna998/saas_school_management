@echo off
REM Nepal SMS - Quick Start Script for Local Development (Windows)

echo ======================================
echo Nepal SMS - Local Development Setup
echo ======================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Please start Docker Desktop.
    pause
    exit /b 1
)

echo [OK] Docker is running
echo.

REM Check if .env exists
if not exist .env (
    echo [INFO] Creating .env from .env.example
    copy .env.example .env
    echo [OK] .env created
)

REM Check if keys exist
if not exist keys\private_key.pem (
    echo [INFO] Generating RSA keys for JWT using Docker
    mkdir keys 2>nul
    docker run --rm -v %CD%/keys:/keys alpine/openssl genrsa -out /keys/private_key.pem 2048
    docker run --rm -v %CD%/keys:/keys alpine/openssl rsa -in /keys/private_key.pem -pubout -out /keys/public_key.pem
    echo [OK] JWT keys generated
)

echo.
echo Step 1: Starting Infrastructure (PostgreSQL + Redis)
echo -------------------------------------------------------
docker-compose up -d postgres redis

echo.
echo Waiting for services to be healthy...
timeout /t 10 /nobreak >nul

echo.
echo Step 2: Setting up Database
echo -------------------------------------------------------
docker-compose run --rm backend python scripts/setup_database.py
if errorlevel 1 (
    echo [WARN] Database setup failed or already completed
)

echo.
echo Step 3: Starting Backend Services
echo -------------------------------------------------------
docker-compose up -d auth-service tenant-service student-service academic-service calendar-service

echo.
echo Waiting for services to start...
timeout /t 5 /nobreak >nul

echo.
echo ======================================
echo [OK] Backend Services Started!
echo ======================================
echo.
echo Backend Services:
echo   - Auth Service:     http://localhost:8001/docs
echo   - Tenant Service:   http://localhost:8002/docs
echo   - Student Service:  http://localhost:8003/docs
echo   - Academic Service: http://localhost:8004/docs
echo   - Calendar Service: http://localhost:8016/docs
echo.
echo Database:
echo   - PostgreSQL: localhost:5432
echo   - Redis:      localhost:6379
echo.
echo ======================================
echo Now start the Frontend:
echo   cd frontend
echo   npm install
echo   npm run dev
echo ======================================
echo.
echo View logs: docker-compose logs -f auth-service
echo Stop services: docker-compose down
echo.
pause
