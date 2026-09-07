@echo off
REM Fix Next.js HMR WebSocket Issues

echo ======================================
echo Next.js HMR WebSocket Fix
echo ======================================
echo.

echo Step 1: Stopping any running dev servers...
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo Step 2: Clearing Next.js cache...
if exist .next rmdir /s /q .next
if exist node_modules\.cache rmdir /s /q node_modules\.cache

echo Step 3: Checking package.json...
findstr /C:"--hostname localhost" package.json >nul
if errorlevel 1 (
    echo [WARN] package.json needs updating
    echo Please run: npm run dev -- --hostname localhost
) else (
    echo [OK] package.json is configured correctly
)

echo.
echo Step 4: Starting dev server with localhost binding...
echo ======================================
echo.
echo Server will start at: http://localhost:3000
echo Press Ctrl+C to stop
echo.
echo ======================================
npm run dev

pause
