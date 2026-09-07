#!/bin/bash
# Fix Next.js HMR WebSocket Issues

echo "======================================"
echo "Next.js HMR WebSocket Fix"
echo "======================================"
echo ""

echo "Step 1: Stopping any running dev servers..."
pkill -f "next dev" 2>/dev/null || true
sleep 2

echo "Step 2: Clearing Next.js cache..."
rm -rf .next
rm -rf node_modules/.cache

echo "Step 3: Checking package.json..."
if grep -q "hostname localhost" package.json; then
    echo "[OK] package.json is configured correctly"
else
    echo "[WARN] package.json needs updating"
    echo "Please run: npm run dev -- --hostname localhost"
fi

echo ""
echo "Step 4: Starting dev server with localhost binding..."
echo "======================================"
echo ""
echo "Server will start at: http://localhost:3000"
echo "Press Ctrl+C to stop"
echo ""
echo "======================================"
npm run dev
