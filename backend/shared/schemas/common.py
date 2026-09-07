"""
Nepal School Management System - Common Pydantic Schemas
Reusable schema components and mixins
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UUIDModel(BaseModel):
    """Base model with UUID"""

    id: UUID = Field(..., description="Unique identifier")


class TimestampModel(BaseModel):
    """Model with creation and update timestamps"""

    created_at: datetime = Field(..., description="Creation timestamp (UTC)")
    updated_at: datetime = Field(..., description="Last update timestamp (UTC)")


class NepalDateModel(BaseModel):
    """Model with Nepal-specific date fields (BS and AD)"""

    date_bs: str = Field(
        ...,
        description="Bikram Sambat date (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_ad: datetime = Field(..., description="Gregorian date (AD)")

    @field_validator("date_bs")
    @classmethod
    def validate_bs_date_format(cls, v: str) -> str:
        """Validate BS date format"""
        from shared.utils.nepali_calendar import validate_bs_date

        if not validate_bs_date(v):
            raise ValueError(f"Invalid BS date: {v}")
        return v


class TenantModel(BaseModel):
    """Model with tenant/school ID"""

    school_id: UUID = Field(..., description="School/Tenant ID for isolation")


class SoftDeleteModel(BaseModel):
    """Model with soft delete fields"""

    is_deleted: bool = Field(default=False, description="Soft delete flag")
    deleted_at: Optional[datetime] = Field(default=None, description="Deletion timestamp")
    deleted_by: Optional[UUID] = Field(default=None, description="User who deleted the record")


class AuditModel(BaseModel):
    """Model with audit trail"""

    created_by: Optional[UUID] = Field(default=None, description="User who created the record")
    updated_by: Optional[UUID] = Field(default=None, description="User who last updated the record")


class ActivationModel(BaseModel):
    """Model with activation status"""

    is_active: bool = Field(default=True, description="Active status flag")


class PaginationParams(BaseModel):
    """Standard pagination parameters"""

    page: int = Field(default=1, ge=1, description="Page number (starts from 1)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")
    sort_by: Optional[str] = Field(default=None, description="Field to sort by")
    sort_order: Optional[str] = Field(
        default="asc",
        pattern="^(asc|desc)$",
        description="Sort order: asc or desc",
    )


class DateRangeFilter(BaseModel):
    """Date range filter parameters"""

    start_date_bs: Optional[str] = Field(
        default=None,
        description="Start date in BS (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    end_date_bs: Optional[str] = Field(
        default=None,
        description="End date in BS (YYYY-MM-DD)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )

    @field_validator("start_date_bs", "end_date_bs")
    @classmethod
    def validate_bs_dates(cls, v: Optional[str]) -> Optional[str]:
        """Validate BS date format if provided"""
        if v is not None:
            from shared.utils.nepali_calendar import validate_bs_date

            if not validate_bs_date(v):
                raise ValueError(f"Invalid BS date: {v}")
        return v


class SearchParams(BaseModel):
    """Standard search parameters"""

    q: Optional[str] = Field(default=None, description="Search query string")
    fields: Optional[list[str]] = Field(
        default=None,
        description="Fields to search in (comma-separated)",
    )


class BulkOperationResult(BaseModel):
    """Result of bulk operations"""

    total: int = Field(..., description="Total items processed")
    success: int = Field(..., description="Successfully processed items")
    failed: int = Field(..., description="Failed items")
    errors: list[dict] = Field(default_factory=list, description="Error details")


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str = Field(default="healthy", description="Service health status")
    service_name: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    dependencies: dict = Field(
        default_factory=dict,
        description="Status of dependencies (database, redis, etc.)",
    )
