"""
Nepal School Management System - Tenant/School Model
Multi-tenant school entity with subscription management
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin


class SchoolType(str, enum.Enum):
    """School types in Nepal"""
    COMMUNITY = "community"
    INSTITUTIONAL = "institutional"
    BOTH = "both"


class SchoolLevel(str, enum.Enum):
    """School education levels"""
    ECD = "ecd"  # Early Childhood Development
    PRIMARY = "primary"  # Grade 1-5
    LOWER_SECONDARY = "lower_secondary"  # Grade 6-8
    SECONDARY = "secondary"  # Grade 9-10
    HIGHER_SECONDARY = "higher_secondary"  # Grade 11-12
    ALL = "all"


class TenantStatus(str, enum.Enum):
    """Tenant/School status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TRIAL = "trial"


class SubscriptionPlan(str, enum.Enum):
    """Subscription plan types"""
    FREE = "free"
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class Province(str, enum.Enum):
    """Provinces of Nepal"""
    KOSHI = "koshi"
    MADHESH = "madhesh"
    BAGMATI = "bagmati"
    GANDAKI = "gandaki"
    LUMBINI = "lumbini"
    KARNALI = "karnali"
    SUDURPASHCHIM = "sudurpashchim"


class Tenant(Base, BaseModel, TimestampMixin):
    """
    Tenant/School model.

    Each school is a separate tenant with isolated data.
    """

    __tablename__ = "tenants"

    # School identification
    name_en = Column(
        String(255),
        nullable=False,
        comment="School name in English"
    )
    name_np = Column(
        String(255),
        nullable=True,
        comment="School name in Nepali (Devanagari)"
    )
    emis_code = Column(
        String(20),
        unique=True,
        nullable=True,
        index=True,
        comment="EMIS school code (Ministry of Education)"
    )
    registration_number = Column(
        String(50),
        nullable=True,
        comment="School registration number"
    )

    # School type & level
    school_type = Column(
        SQLEnum(SchoolType),
        default=SchoolType.INSTITUTIONAL,
        nullable=False,
        comment="School type"
    )
    school_level = Column(
        SQLEnum(SchoolLevel),
        default=SchoolLevel.SECONDARY,
        nullable=False,
        comment="Highest education level offered"
    )

    # Higher Secondary (Grade 11-12) feature toggle
    hs_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
        comment="Grade 11-12 (Higher Secondary) enabled"
    )
    hs_enabled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When HS was enabled"
    )

    # Contact info
    phone = Column(String(20), nullable=True, comment="School phone number")
    email = Column(String(255), nullable=True, comment="School email")
    website = Column(String(255), nullable=True, comment="School website URL")

    # Address
    province = Column(SQLEnum(Province), nullable=True, comment="Province")
    district = Column(String(100), nullable=True, comment="District name")
    municipality = Column(String(100), nullable=True, comment="Municipality/VDC")
    ward_no = Column(Integer, nullable=True, comment="Ward number")
    tole = Column(String(100), nullable=True, comment="Tole/Street")

    # Status & subscription
    status = Column(
        SQLEnum(TenantStatus),
        default=TenantStatus.TRIAL,
        nullable=False,
        index=True,
        comment="Tenant status"
    )
    subscription_plan = Column(
        SQLEnum(SubscriptionPlan),
        default=SubscriptionPlan.FREE,
        nullable=False,
        comment="Current subscription plan"
    )
    subscription_start = Column(DateTime(timezone=True), nullable=True)
    subscription_end = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)

    # Academic configuration
    academic_year_bs = Column(
        String(10),
        nullable=True,
        comment="Current academic year in BS (e.g., '2083')"
    )
    academic_year_start_month = Column(
        Integer,
        default=1,
        comment="Academic year start month in BS (1=Baisakh)"
    )

    # Capacity
    max_students = Column(Integer, default=500, comment="Maximum students allowed")
    max_staff = Column(Integer, default=50, comment="Maximum staff members")
    max_storage_gb = Column(Integer, default=5, comment="Storage limit in GB")

    # Branding
    logo_url = Column(String(500), nullable=True, comment="School logo URL")
    primary_color = Column(String(7), default="#1E40AF", comment="Primary brand color")

    # Settings (JSON)
    settings_json = Column(
        JSONB,
        default={},
        nullable=False,
        comment="Tenant-specific settings"
    )

    # Metadata
    onboarded_at = Column(DateTime(timezone=True), nullable=True)
    onboarded_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self):
        return f"<Tenant(id={self.id}, name={self.name_en}, emis={self.emis_code})>"

    @property
    def is_active(self) -> bool:
        return self.status in (TenantStatus.ACTIVE, TenantStatus.TRIAL)

    @property
    def is_trial_expired(self) -> bool:
        if self.status != TenantStatus.TRIAL:
            return False
        if self.trial_ends_at and self.trial_ends_at < datetime.utcnow():
            return True
        return False

    @property
    def is_subscription_active(self) -> bool:
        if self.subscription_plan == SubscriptionPlan.FREE:
            return True
        if self.subscription_end and self.subscription_end < datetime.utcnow():
            return False
        return True
