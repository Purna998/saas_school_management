@echo off
setlocal
cd /d "%~dp0"

set "BACKEND_DIR=%CD%\backend"
set "FRONTEND_DIR=%CD%\frontend"
set "PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "FRONTEND_MODE=dev"
if /I "%~1"=="preview" set "FRONTEND_MODE=preview"

echo ======================================
echo Nepal SMS - Local Development
echo ======================================

if not exist "%PYTHON%" (
    echo [INFO] Creating the backend virtual environment...
    python -m venv "%BACKEND_DIR%\.venv" || goto :error
)

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The existing backend virtual environment is broken.
    echo Delete backend\.venv and run this script again.
    goto :error
)

"%PYTHON%" -m pip --version >nul 2>&1
if errorlevel 1 "%PYTHON%" -m ensurepip --upgrade || goto :error

"%PYTHON%" -c "import fastapi, sqlalchemy, redis, asyncpg, pydantic_settings, jwt, pyotp, qrcode" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing backend dependencies...
    "%PYTHON%" -m pip install -r "%BACKEND_DIR%\requirements-local.txt" || goto :error
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo [INFO] Installing frontend dependencies...
    pushd "%FRONTEND_DIR%"
    call npm install || (popd & goto :error)
    popd
)

if not exist ".env" (
    copy ".env.example" ".env" >nul || goto :error
    echo [INFO] Created .env from .env.example
)

if not exist "keys\jwt_private.pem" (
    pushd "%BACKEND_DIR%"
    "%PYTHON%" scripts\generate_jwt_keys.py || (popd & goto :error)
    popd
)

echo [INFO] Preparing the local PostgreSQL database...
pushd "%BACKEND_DIR%"
"%PYTHON%" scripts\setup_database.py || (popd & goto :services_error)
popd

start "Nepal SMS API" /D "%BACKEND_DIR%" cmd /k ""%PYTHON%" -m uvicorn main:app --reload --port 8080"
start "Nepal SMS Frontend" /D "%FRONTEND_DIR%" cmd /k "npm run %FRONTEND_MODE%"

echo.
echo [OK] Local applications are starting.
echo Frontend: http://localhost:3001
echo API docs: http://localhost:8080/docs
echo Frontend mode: %FRONTEND_MODE% ^(use start-local.bat preview for performance checks^)
echo Close the application windows to stop development servers.
exit /b 0

:services_error
echo.
echo [ERROR] Database setup failed. Ensure local PostgreSQL is running and .env has the correct credentials.
exit /b 1

:error
echo.
echo [ERROR] Local setup failed. Review the message above.
exit /b 1
