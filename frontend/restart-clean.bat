@echo off
echo ==========================================
echo Nepal SMS - Clean Restart
echo ==========================================
echo.

echo [1] Stopping all Node processes...
taskkill /F /IM node.exe 2>nul
timeout /t 2 /nobreak >nul

echo [2] Clearing all caches...
if exist .next rmdir /s /q .next
if exist .turbo rmdir /s /q .turbo
if exist node_modules\.cache rmdir /s /q node_modules\.cache
echo Cache cleared!
echo.

echo [3] Checking Node.js version...
node --version
echo.

echo [4] Using Webpack (more stable than Turbopack)...
echo Starting dev server on port 3000...
echo.
echo ==========================================
echo Access URLs:
echo   http://127.0.0.1:3000
echo   http://localhost:3000
echo.
echo Press Ctrl+C to stop
echo ==========================================
echo.

npm run dev

pause
