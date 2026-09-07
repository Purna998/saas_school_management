@echo off
echo ======================================
echo Next.js Dev Server Diagnostics
echo ======================================
echo.

echo [1] Checking Node.js version...
node --version
echo.

echo [2] Checking npm version...
npm --version
echo.

echo [3] Checking if port 3000 is in use...
netstat -ano | findstr :3000
echo.

echo [4] Checking Next.js installation...
cd /d %~dp0
if exist node_modules\next (
    echo [OK] Next.js is installed
) else (
    echo [ERROR] Next.js not found! Run: npm install
)
echo.

echo [5] Checking package.json dev script...
findstr "dev" package.json
echo.

echo [6] Killing any existing Node processes on port 3000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000 ^| findstr LISTENING') do (
    echo Killing process %%a
    taskkill /F /PID %%a 2>nul
)
echo.

echo [7] Clearing Next.js cache...
if exist .next (
    rmdir /s /q .next
    echo [OK] Cache cleared
)
echo.

echo [8] Starting dev server...
echo ======================================
echo Server will start at: http://localhost:3000
echo If browser shows connection refused, try:
echo   - http://127.0.0.1:3000
echo   - http://0.0.0.0:3000
echo ======================================
echo.

npm run dev
