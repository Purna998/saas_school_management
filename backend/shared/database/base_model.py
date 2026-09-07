"""
Nepal School Management System - Base Database Models
Mixins for common functionality (timestamps, tenant isolation, soft delete)
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, Boolean, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func


class BaseModel:
    """Base model with UUID primary key"""

    @declared_attr
    def id(cls):
        return Column(
            UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
            unique=True,
            nullable=False,
            index=True,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""

    @declared_attr
    def created_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )


class TenantMixin:
    """
    Mixin for multi-tenant isolation.
    Every table MUST include school_id for Row-Level Security (RLS).
    """

    @declared_attr
    def school_id(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=False,
            index=True,
            comment="Tenant isolation key - enforced by PostgreSQL RLS",
        )

    @declared_attr
    def __table_args__(cls):
        """Add composite index on school_id and common query columns"""
        return (
            Index(f"idx_{cls.__tablename__}_school_id", "school_id"),
        )


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""

    @declared_attr
    def is_deleted(cls):
        return Column(
            Boolean,
            default=False,
            nullable=False,
            index=True,
        )

    @declared_attr
    def deleted_at(cls):
        return Column(
            DateTime(timezone=True),
            nullable=True,
        )

    @declared_attr
    def deleted_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True,
            comment="User ID who deleted the record",
        )

    def soft_delete(self, user_id: uuid.UUID | None = None):
        """Mark record as deleted"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = user_id

    def restore(self):
        """Restore soft-deleted record"""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None


class AuditMixin:
    """Mixin for audit trail (created_by, updated_by)"""

    @declared_attr
    def created_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True,
            comment="User ID who created the record",
        )

    @declared_attr
    def updated_by(cls):
        return Column(
            UUID(as_uuid=True),
            nullable=True,
            comment="User ID who last updated the record",
        )


class NepalDateMixin:
    """
    Mixin for Bikram Sambat (BS) date fields.
    Stores BS date as string (YYYY-MM-DD) and AD date as DATE for indexing.
    """

    @declared_attr
    def date_bs(cls):
        return Column(
            String(10),
            nullable=False,
            comment="Bikram Sambat date (YYYY-MM-DD format)",
        )

    @declared_attr
    def date_ad(cls):
        return Column(
            DateTime(timezone=False),
            nullable=False,
            index=True,
            comment="Gregorian date (converted from BS for sorting/indexing)",
        )


class NepalTimestampMixin:
    """
    Mixin for Nepal-specific timestamps with BS and AD dates.
    UTC stored internally, NPT (UTC+5:45) for display.
    """

    @declared_attr
    def created_at_bs(cls):
        return Column(
            String(10),
            nullable=True,
            comment="Created date in Bikram Sambat (YYYY-MM-DD)",
        )

    @declared_attr
    def created_at_ad(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
            comment="Created timestamp in UTC (convert to NPT for display)",
        )

    @declared_attr
    def updated_at_ad(cls):
        return Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
            comment="Updated timestamp in UTC (convert to NPT for display)",
        )


class ActivationMixin:
    """Mixin for is_active flag"""

    @declared_attr
    def is_active(cls):
        return Column(
            Boolean,
            default=True,
            nullable=False,
            index=True,
            comment="Active status flag",
        )


# Combined model for most common use case
class StandardModel(BaseModel, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """
    Standard model combining most common mixins:
    - UUID primary key
    - Timestamps (created_at, updated_at)
    - Tenant isolation (school_id)
    - Soft delete (is_deleted, deleted_at)
    """

    __abstract__ = True


class AuditedModel(StandardModel, AuditMixin):
    """
    Standard model with audit trail:
    - All StandardModel features
    - Created by / updated by tracking
    """

    __abstract__ = True
