# ERR_CONNECTION_REFUSED Fix Guide

## Problem
Browser shows: `localhost refused to connect` or `ERR_CONNECTION_REFUSED`

## Quick Fixes (Try in Order)

### Fix 1: Kill and Restart Server ✅

```bash
# Windows PowerShell (Run as Administrator)
# Stop all Node processes
Get-Process node | Stop-Process -Force

# Or kill specific port
netstat -ano | findstr :3000
taskkill /F /PID <PID>

# Restart
cd frontend
npm run dev
```

### Fix 2: Use Different Addresses ✅

Try accessing in this order:
1. http://127.0.0.1:3000
2. http://localhost:3000
3. http://[::1]:3000 (IPv6)

### Fix 3: Change Hostname Binding ✅

**Option A: Bind to all interfaces**
```json
// package.json
"dev": "next dev --hostname 0.0.0.0 --port 3000"
```

**Option B: Use 127.0.0.1**
```json
// package.json
"dev": "next dev --hostname 127.0.0.1 --port 3000"
```

Restart:
```bash
npm run dev
```

### Fix 4: Use Different Port ✅

```bash
# Try port 3001
npm run dev -- --port 3001

# Then access: http://localhost:3001
```

### Fix 5: Check Windows Firewall ✅

```powershell
# Run as Administrator
# Allow Node.js
netsh advfirewall firewall add rule name="Node.js" dir=in action=allow program="C:\Program Files\nodejs\node.exe" enable=yes

# Or temporarily disable firewall to test
# Windows Defender Firewall > Turn off (not recommended for permanent)
```

### Fix 6: Check Antivirus ✅

Some antivirus software blocks localhost connections:
- Temporarily disable antivirus
- Add exception for Node.js
- Add exception for port 3000

### Fix 7: Clear Everything and Reinstall ✅

```bash
cd frontend

# Stop server
Ctrl+C

# Delete everything
rm -rf node_modules
rm -rf .next
rm -rf .turbo
rm package-lock.json

# Fresh install
npm install

# Start fresh
npm run dev
```

### Fix 8: Check hosts File ✅

```bash
# Edit hosts file (Run as Administrator)
notepad C:\Windows\System32\drivers\etc\hosts

# Ensure this line exists:
127.0.0.1       localhost

# Save and close
```

### Fix 9: Run Diagnostic Script ✅

```bash
cd frontend
diagnose.bat
```

This will:
- Check Node/npm versions
- Check port 3000
- Kill existing processes
- Clear cache
- Start server

### Fix 10: Use npm instead of next ✅

```bash
# Instead of running next directly
npm run dev

# Not: npx next dev
```

## Common Issues

### Issue: "Server is running but can't connect"

**Symptoms:**
- `netstat` shows port 3000 is LISTENING
- Browser shows connection refused

**Solution:**
Server is binding to IPv6 only. Try:
1. http://[::1]:3000 (IPv6)
2. Or change to IPv4: `--hostname 127.0.0.1`

### Issue: "Port 3000 already in use"

```bash
# Windows
netstat -ano | findstr :3000
taskkill /F /PID <PID>

# PowerShell
Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess | Stop-Process -Force
```

### Issue: "Nothing happens when I run npm run dev"

```bash
# Check if Node is installed
node --version

# Should show: v18.x.x or higher

# Check if npm works
npm --version

# Reinstall Node.js if needed
# Download from: https://nodejs.org/
```

## Step-by-Step Solution

### Step 1: Kill Everything

```powershell
# PowerShell as Administrator
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
```

### Step 2: Update package.json

```json
{
  "scripts": {
    "dev": "next dev --hostname 0.0.0.0 --port 3000"
  }
}
```

### Step 3: Clear Cache

```bash
cd frontend
rm -rf .next node_modules/.cache
```

### Step 4: Restart

```bash
npm run dev
```

### Step 5: Test All URLs

Open browser and try:
1. http://localhost:3000
2. http://127.0.0.1:3000
3. http://0.0.0.0:3000

One of these MUST work!

## Expected Output

When server starts successfully:

```
▲ Next.js 16.2.9 (Turbopack)
- Local:        http://localhost:3000
- Network:      http://192.168.1.x:3000

✓ Starting...
✓ Ready in 1.2s
```

## Still Not Working?

### Check Console Output

Look for errors in the terminal:
- `EADDRINUSE` → Port in use (kill process)
- `EACCES` → Permission denied (run as admin)
- `MODULE_NOT_FOUND` → Missing dependencies (npm install)

### Verbose Logging

```bash
# Run with debug info
npm run dev -- --inspect

# Or with more logging
NODE_OPTIONS='--trace-warnings' npm run dev
```

### Check Browser Console

Press F12 in browser:
- Check Console tab for errors
- Check Network tab for failed requests

## Alternative: Use Different Framework

If Next.js continues to have issues, you can use:

```bash
# Vite (faster alternative)
npm create vite@latest

# Or Create React App
npx create-react-app frontend-backup
```

But let's fix Next.js first!

## My Recommended Fix (Copy-Paste)

```bash
# 1. Stop everything
Get-Process node | Stop-Process -Force

# 2. Navigate to frontend
cd C:\Users\core3\Documents\Projects\saas_school_management_system\frontend

# 3. Update package.json dev script to:
# "dev": "next dev --hostname 0.0.0.0 --port 3000"

# 4. Clear cache
rm -rf .next

# 5. Start
npm run dev

# 6. Open browser to:
# http://127.0.0.1:3000
```

## Success Checklist

- [ ] Port 3000 is listening (check with `netstat`)
- [ ] No errors in terminal
- [ ] Browser can access http://127.0.0.1:3000
- [ ] Page loads (even if shows login page)
- [ ] No firewall blocking

विद्यालय व्यवस्थापन प्रणाली  
© 2026 Nepal SMS Team
