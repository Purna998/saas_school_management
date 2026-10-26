"""Single FastAPI application for the Nepal School Management System."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from services.academic.api import academic
from services.attendance.api import attendance
from services.auth.api import auth, mfa, sessions, users
from services.calendar.api import calendar
from services.communication.api import communication
from services.exam.api import exam
from services.fee.api import fee
from services.hostel.api import hostel
from services.inventory.api import inventory
from services.library.api import library
from services.notification_worker.api import notification
from services.report.api import report
from services.staff.api import staff
from services.student.api import students
from services.tenant.api import tenants
from services.transport.api import transport
from services.transport.api import tracking
from shared.config.settings import settings
from shared.database.base import close_db, engine
from shared.performance import install_performance_middleware
from shared.utils.exceptions import NepalSMSException, exception_to_http
from shared.utils.redis_client import redis_client


logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
API_PREFIX = f"/api/{settings.api_version}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Release shared clients cleanly when the process stops."""
    logger.info("Starting %s", settings.app_name)
    yield
    await redis_client.disconnect()
    await close_db()
    logger.info("Stopped %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description="Multi-tenant school management API",
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
async def nepal_sms_exception_handler(
    request: Request,
    exc: NepalSMSException,
) -> JSONResponse:
    http_exc = exception_to_http(exc)
    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unexpected error while handling %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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


@app.get("/", tags=["System"])
async def root():
    return {
        "service": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["System"])
async def health():
    """Lightweight liveness probe that does not depend on external services."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["System"])
async def readiness():
    """Confirm that dependencies required by authenticated requests are ready."""
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        checks["postgresql"] = "ready"
    except Exception:
        logger.exception("PostgreSQL readiness check failed")
        checks["postgresql"] = "unavailable"

    try:
        client = await redis_client.connect()
        await client.ping()
        checks["redis"] = "ready"
    except Exception:
        logger.exception("Redis readiness check failed")
        checks["redis"] = "unavailable"

    ready = all(value == "ready" for value in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if ready else "unavailable", "checks": checks},
    )


app.include_router(auth.router, prefix=f"{API_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{API_PREFIX}/users", tags=["Users"])
app.include_router(mfa.router, prefix=f"{API_PREFIX}/auth/mfa", tags=["MFA"])
app.include_router(sessions.router, prefix=f"{API_PREFIX}/auth/sessions", tags=["Sessions"])
app.include_router(tenants.router, prefix=f"{API_PREFIX}/tenants", tags=["Tenants"])
app.include_router(students.router, prefix=f"{API_PREFIX}/students", tags=["Students"])
app.include_router(academic.router, prefix=f"{API_PREFIX}/academic", tags=["Academic"])
app.include_router(attendance.router, prefix=f"{API_PREFIX}/attendance", tags=["Attendance"])
app.include_router(exam.router, prefix=f"{API_PREFIX}/exams", tags=["Exams"])
app.include_router(fee.router, prefix=f"{API_PREFIX}/fees", tags=["Fees"])
app.include_router(staff.router, prefix=f"{API_PREFIX}/staff", tags=["Staff"])
app.include_router(communication.router, prefix=f"{API_PREFIX}/communication", tags=["Communication"])
app.include_router(library.router, prefix=f"{API_PREFIX}/library", tags=["Library"])
app.include_router(transport.router, prefix=f"{API_PREFIX}/transport", tags=["Transport"])
app.include_router(tracking.router, prefix=f"{API_PREFIX}/transport", tags=["Live transport"])
app.include_router(hostel.router, prefix=f"{API_PREFIX}/hostel", tags=["Hostel"])
app.include_router(inventory.router, prefix=f"{API_PREFIX}/inventory", tags=["Inventory"])
app.include_router(report.router, prefix=f"{API_PREFIX}/reports", tags=["Reports"])
app.include_router(notification.router, prefix=f"{API_PREFIX}/notifications", tags=["Notifications"])
app.include_router(calendar.router, prefix=f"{API_PREFIX}/calendar", tags=["Calendar"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
