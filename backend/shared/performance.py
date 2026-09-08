"""Low-overhead request and SQL timing for API performance diagnostics."""

from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from fastapi import FastAPI, Request
from sqlalchemy import event

from shared.config.settings import settings
from shared.database.base import engine


@dataclass
class RequestMetrics:
    query_count: int = 0
    database_ms: float = 0.0


_request_metrics: ContextVar[RequestMetrics | None] = ContextVar(
    "request_metrics",
    default=None,
)


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    context._nepal_sms_started_at = perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    metrics = _request_metrics.get()
    started_at = getattr(context, "_nepal_sms_started_at", None)
    if metrics is not None and started_at is not None:
        metrics.query_count += 1
        metrics.database_ms += (perf_counter() - started_at) * 1000


def install_performance_middleware(app: FastAPI) -> None:
    """Expose request/database timing without logging query parameters."""

    @app.middleware("http")
    async def add_server_timing(request: Request, call_next):
        metrics = RequestMetrics()
        token = _request_metrics.set(metrics)
        started_at = perf_counter()
        try:
            response = await call_next(request)
            total_ms = (perf_counter() - started_at) * 1000
            response.headers["Server-Timing"] = (
                f'total;dur={total_ms:.1f}, '
                f'db;dur={metrics.database_ms:.1f};desc="{metrics.query_count} queries"'
            )
            if settings.debug:
                response.headers["X-DB-Query-Count"] = str(metrics.query_count)
            return response
        finally:
            _request_metrics.reset(token)
