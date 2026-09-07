"""
Nepal School Management System - Shared Pydantic Schemas
Common request/response models across all services
"""

from shared.schemas.responses import (
    APIResponse,
    SuccessResponse,
    ErrorResponse,
    PaginatedResponse,
    MetaData,
)
from shared.schemas.common import (
    UUIDModel,
    TimestampModel,
    NepalDateModel,
)

__all__ = [
    "APIResponse",
    "SuccessResponse",
    "ErrorResponse",
    "PaginatedResponse",
    "MetaData",
    "UUIDModel",
    "TimestampModel",
    "NepalDateModel",
]
