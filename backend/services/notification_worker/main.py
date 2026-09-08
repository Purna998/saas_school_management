"""Nepal School Management System - Notification Worker Service"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from shared.config.settings import settings
from shared.database.base import init_db, close_db
from services.notification_worker.api import notification

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(title="Notification Worker - Nepal SMS", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "healthy", "service": "notification-worker", "timestamp": datetime.utcnow().isoformat()}

app.include_router(notification.router, prefix="/api/v1/notifications", tags=["Notifications"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.notification_worker_port, reload=settings.debug)
