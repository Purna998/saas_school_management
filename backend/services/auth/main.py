"""
Nepal School Management System - Auth Service
Authentication & Authorization Microservice

Features:
- JWT RS256 authentication (15-min access + 7-day refresh tokens)
- MFA/TOTP for Admin/Accountant roles
- RBAC with permission-based authorization
- Login rate limiting & account lockout
- Session management with Redis
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
from services.auth.api import auth, users, mfa, sessions
from services.auth.utils.exceptions_handler import nepal_sms_exception_handler
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
    logger.info("Starting Auth Service...")
    await init_db()
    logger.info("Auth Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Auth Service...")
    await close_db()
    logger.info("Auth Service shut down successfully")


# Create FastAPI app
app = FastAPI(
    title="Auth Service - Nepal SMS",
    description="Authentication & Authorization microservice for Nepal School Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

install_performance_middleware(app)

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
    return await nepal_sms_exception_handler(request, exc)


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
        "service": "auth-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "service": "Nepal SMS - Auth Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(mfa.router, prefix="/api/v1/auth/mfa", tags=["MFA"])
app.include_router(sessions.router, prefix="/api/v1/auth/sessions", tags=["Sessions"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.auth_service_port,
        reload=settings.debug,
        log_level="info",
    )
