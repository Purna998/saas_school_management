"""
Nepal School Management System - Tenant Schemas
Pydantic models for tenant/school endpoints
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class TenantCreate(BaseModel):
    """Create new school/tenant"""

    name_en: str = Field(..., min_length=2, max_length=255, description="School name in English")
    name_np: Optional[str] = Field(None, description="School name in Nepali")
    emis_code: Optional[str] = Field(None, max_length=20, description="EMIS school code")
    registration_number: Optional[str] = Field(None, description="Registration number")
    school_type: str = Field(default="institutional", description="School type")
    school_level: str = Field(default="secondary", description="Highest level offered")
    phone: Optional[str] = Field(None, description="School phone")
    email: Optional[EmailStr] = Field(None, description="School email")
    website: Optional[str] = Field(None, description="School website")
    province: Optional[str] = Field(None, description="Province")
    district: Optional[str] = Field(None, description="District")
    municipality: Optional[str] = Field(None, description="Municipality/VDC")
    ward_no: Optional[int] = Field(None, ge=1, le=33, description="Ward number")
    tole: Optional[str] = Field(None, description="Tole/Street")

    class Config:
        json_schema_extra = {
            "example": {
                "name_en": "Shree Janata Secondary School",
                "name_np": "श्री जनता माध्यमिक विद्यालय",
                "emis_code": "27-01-07-001",
                "school_type": "community",
                "school_level": "secondary",
                "province": "bagmati",
                "district": "Kathmandu",
                "municipality": "Kathmandu Metropolitan City",
                "ward_no": 10,
            }
        }


class TenantUpdate(BaseModel):
    """Update school/tenant"""

    name_en: Optional[str] = Field(None, min_length=2, max_length=255)
    name_np: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    website: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    municipality: Optional[str] = None
    ward_no: Optional[int] = Field(None, ge=1, le=33)
    tole: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    academic_year_bs: Optional[str] = None


class TenantResponse(BaseModel):
    """Tenant response schema"""

    id: UUID
    name_en: str
    name_np: Optional[str] = None
    emis_code: Optional[str] = None
    registration_number: Optional[str] = None
    school_type: str
    school_level: str
    hs_enabled: bool
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    province: Optional[str] = None
    district: Optional[str] = None
    municipality: Optional[str] = None
    ward_no: Optional[int] = None
    tole: Optional[str] = None
    status: str
    subscription_plan: str
    subscription_end: Optional[datetime] = None
    academic_year_bs: Optional[str] = None
    max_students: int
    max_staff: int
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    """Tenant list response"""

    tenants: List[TenantResponse]
    total: int
    page: int
    limit: int


class HSToggleRequest(BaseModel):
    """Higher Secondary toggle request"""

    enable: bool = Field(..., description="Enable or disable Grade 11-12")
    faculties: Optional[List[str]] = Field(
        None,
        description="Faculties to enable (e.g., ['Science', 'Management', 'Humanities'])"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "enable": True,
                "faculties": ["Science", "Management", "Humanities"],
            }
        }


class HSToggleResponse(BaseModel):
    """Higher Secondary toggle response"""

    hs_enabled: bool
    message: str
    faculties: Optional[List[str]] = None


class SubscriptionResponse(BaseModel):
    """Subscription details response"""

    plan: str
    status: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    max_students: int
    max_staff: int
    max_storage_gb: int
    features: List[str]
