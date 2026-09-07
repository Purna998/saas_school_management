"""Nepal School Management System - Transport Service"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config.settings import settings
from shared.database.base import init_db, close_db
from services.transport.api import transport

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(title="Transport Service - Nepal SMS", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "healthy", "service": "transport-service", "timestamp": datetime.utcnow().isoformat()}

app.include_router(transport.router, prefix="/api/v1/transport", tags=["Transport"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.transport_service_port, reload=settings.debug)
