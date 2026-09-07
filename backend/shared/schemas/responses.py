"""
Nepal School Management System - API Response Schemas
Standard response models for all API endpoints
"""

from typing import Generic, TypeVar, Any, Optional
from pydantic import BaseModel, Field


T = TypeVar("T")


class MetaData(BaseModel):
    """Metadata for paginated responses"""

    page: int = Field(default=1, description="Current page number")
    limit: int = Field(default=20, description="Items per page")
    total: int = Field(default=0, description="Total number of items")
    total_pages: int = Field(default=0, description="Total number of pages")
    has_next: bool = Field(default=False, description="Has next page")
    has_previous: bool = Field(default=False, description="Has previous page")


class ErrorDetail(BaseModel):
    """Error detail model"""

    field: Optional[str] = Field(default=None, description="Field name if validation error")
    message: str = Field(..., description="Error message")
    code: Optional[str] = Field(default=None, description="Error code")


class APIResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.

    Attributes:
        success: Indicates if request was successful
        data: Response data (generic type)
        meta: Metadata (pagination, etc.)
        error: Error details if success=False
    """

    success: bool = Field(..., description="Request success status")
    data: Optional[T] = Field(default=None, description="Response data")
    meta: Optional[MetaData] = Field(default=None, description="Response metadata")
    error: Optional[ErrorDetail] = Field(default=None, description="Error details")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"id": "123", "name": "Example"},
                "meta": None,
                "error": None,
            }
        }


class SuccessResponse(APIResponse[T], Generic[T]):
    """
    Success response wrapper.

    Usage:
        return SuccessResponse(data=student)
    """

    success: bool = Field(default=True, description="Always True for success responses")
    error: Optional[ErrorDetail] = Field(default=None, description="Always None for success")


class ErrorResponse(BaseModel):
    """
    Error response model.

    Usage:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(message="Invalid data", code="INVALID_DATA")
            ).dict()
        )
    """

    success: bool = Field(default=False, description="Always False for errors")
    data: None = Field(default=None, description="Always None for errors")
    error: ErrorDetail = Field(..., description="Error details")

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "data": None,
                "error": {
                    "field": "email",
                    "message": "Invalid email format",
                    "code": "INVALID_EMAIL",
                },
            }
        }


class PaginatedResponse(APIResponse[list[T]], Generic[T]):
    """
    Paginated response wrapper.

    Usage:
        return PaginatedResponse(
            data=students,
            meta=MetaData(page=1, limit=20, total=100, total_pages=5)
        )
    """

    success: bool = Field(default=True, description="Always True for success")
    data: list[T] = Field(..., description="List of items")
    meta: MetaData = Field(..., description="Pagination metadata")
    error: None = Field(default=None, description="Always None for success")


# Helper functions to create responses
def success_response(
    data: Any = None,
    meta: Optional[MetaData] = None,
) -> dict:
    """
    Create success response dictionary.

    Args:
        data: Response data
        meta: Metadata (optional)

    Returns:
        Response dictionary
    """
    return {
        "success": True,
        "data": data,
        "meta": meta.model_dump() if meta else None,
        "error": None,
    }


def error_response(
    message: str,
    code: Optional[str] = None,
    field: Optional[str] = None,
) -> dict:
    """
    Create error response dictionary.

    Args:
        message: Error message
        code: Error code (optional)
        field: Field name for validation errors (optional)

    Returns:
        Error response dictionary
    """
    return {
        "success": False,
        "data": None,
        "meta": None,
        "error": {
            "field": field,
            "message": message,
            "code": code,
        },
    }


def paginated_response(
    data: list,
    page: int,
    limit: int,
    total: int,
) -> dict:
    """
    Create paginated response dictionary.

    Args:
        data: List of items
        page: Current page number
        limit: Items per page
        total: Total number of items

    Returns:
        Paginated response dictionary
    """
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_previous = page > 1

    meta = MetaData(
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
        has_next=has_next,
        has_previous=has_previous,
    )

    return {
        "success": True,
        "data": data,
        "meta": meta.model_dump(),
        "error": None,
    }
