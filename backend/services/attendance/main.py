"""
Nepal School Management System - Attendance Service
Attendance Management Microservice

Features:
- Batch attendance marking for classes
- Daily attendance by grade/section
- Student attendance history
- Monthly attendance reports with BS date support
- Period-based attendance for Higher Secondary (Grade 11-12)
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
from services.attendance.api import attendance

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("Starting Attendance Service...")
    await init_db()
    logger.info("Attendance Service started successfully")
    yield
    logger.info("Shutting down Attendance Service...")
    await close_db()
    logger.info("Attendance Service shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="Attendance Service - Nepal SMS",
    description="Attendance management microservice for Nepal School Management System. "
    "Supports daily attendance tracking with Bikram Sambat dates, "
    "batch marking, monthly reports, and period-based HS attendance.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(NepalSMSException)
async def custom_exception_handler(request: Request, exc: NepalSMSException):
    """Handle custom Nepal SMS exceptions"""
    http_exc = exception_to_http(exc)
    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
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


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Service health check"""
    from datetime import datetime
    return {
        "status": "healthy",
        "service": "attendance-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "Nepal SMS - Attendance Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# Include API routers
app.include_router(
    attendance.router,
    prefix="/api/v1/attendance",
    tags=["Attendance"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.attendance_service_port,
        reload=settings.debug,
        log_level="info",
    )
