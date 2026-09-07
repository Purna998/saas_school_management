"""
Nepal School Management System - Fee Service
Fee Management Microservice

Features:
- Fee structure management (per grade per academic year)
- Fee head configuration (tuition, exam, lab, etc.)
- Automatic ledger entry generation for students
- Fee collection with receipt generation
- Outstanding fees reporting
- Scholarship/discount management
- Fee collection summary and analytics
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from shared.config.settings import settings
from shared.database.base import init_db, close_db
from services.fee.api import fee
from shared.utils.exceptions import NepalSMSException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Fee Service...")
    await init_db()
    logger.info("Fee Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Fee Service...")
    await close_db()
    logger.info("Fee Service shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="Fee Service - Nepal SMS",
    description="Fee Management microservice for Nepal School Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
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
    from shared.utils.exceptions import exception_to_http
    status_code = exception_to_http(exc)
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details or {},
            },
        },
    )


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
        "service": "fee-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "Nepal SMS - Fee Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# Include API routers
app.include_router(fee.router, prefix="/api/v1/fees", tags=["Fees"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.fee_service_port,
        reload=settings.debug,
        log_level="info",
    )
