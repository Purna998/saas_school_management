"""
Nepal School Management System - Academic Service
Academic Structure Microservice

Features:
- Grade management (1-12)
- Section management per grade
- Subject management with marks configuration
- Timetable scheduling
- Higher Secondary faculty & stream management (Grade 11-12)
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging

from shared.config.settings import settings
from shared.database.base import init_db, close_db
from shared.performance import install_performance_middleware
from shared.utils.exceptions import NepalSMSException, exception_to_http
from services.academic.api import academic

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Academic Service...")
    await init_db()
    logger.info("Academic Service started successfully")
    yield
    logger.info("Shutting down Academic Service...")
    await close_db()
    logger.info("Academic Service shut down successfully")


app = FastAPI(
    title="Academic Service - Nepal SMS",
    description="Academic structure management microservice (grades, sections, subjects, timetable)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

install_performance_middleware(app)

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(NepalSMSException)
async def custom_exception_handler(request: Request, exc: NepalSMSException):
    http_exc = exception_to_http(exc)
    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": {} if settings.is_production else {"error": str(exc)},
            },
        },
    )


@app.get("/health", tags=["Health"])
async def health_check():
    from datetime import datetime
    return {
        "status": "healthy",
        "service": "academic-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Nepal SMS - Academic Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


app.include_router(academic.router, prefix="/api/v1/academic", tags=["Academic"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.academic_service_port,
        reload=settings.debug,
        log_level="info",
    )
