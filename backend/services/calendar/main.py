"""
Nepal School Management System - Calendar Service
Bikram Sambat (BS) Calendar Microservice

Features:
- BS to AD date conversion
- AD to BS date conversion
- Current BS date
- Academic year calculation
- Nepal holiday calendar
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import logging

from shared.config.settings import settings
from services.calendar.api import calendar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Calendar Service - Nepal SMS",
    description="Bikram Sambat calendar and date conversion microservice",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "service": "calendar-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": "Nepal SMS - Calendar Service",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["Calendar"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.calendar_service_port,
        reload=settings.debug,
        log_level="info",
    )
