"""
Nepal School Management System - Library Service
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging

from shared.config.settings import settings
from shared.database.base import init_db, close_db
from shared.utils.exceptions import NepalSMSException, exception_to_http
from services.library.api import library

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title="Library Service - Nepal SMS", version="1.0.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(NepalSMSException)
async def custom_exc(request, exc):
    h = exception_to_http(exc)
    return JSONResponse(status_code=h.status_code, content=h.detail)


@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "healthy", "service": "library-service", "timestamp": datetime.utcnow().isoformat()}


app.include_router(library.router, prefix="/api/v1/library", tags=["Library"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.library_service_port, reload=settings.debug)
