"""
Nepal School Management System - User Schemas
Pydantic models for user management endpoints
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

from services.auth.utils.password import validate_password_strength


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr = Field(..., description="User email address")
    full_name_en: str = Field(..., min_length=2, description="Full name in English")
    full_name_np: Optional[str] = Field(None, description="Full name in Nepali")
    phone: Optional[str] = Field(None, description="Phone number")


class UserCreate(UserBase):
    """User creation schema"""

    password: str = Field(..., min_length=8, description="User password")
    school_id: UUID = Field(..., description="School/Tenant ID")
    role_ids: List[UUID] = Field(default_factory=list, description="Role IDs to assign")

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        is_valid, error = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error)
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "email": "teacher@school.edu.np",
                "password": "SecurePass123!",
                "full_name_en": "Ram Prasad Sharma",
                "full_name_np": "राम प्रसाद शर्मा",
                "phone": "+977-9841234567",
                "school_id": "123e4567-e89b-12d3-a456-426614174000",
                "role_ids": ["role-uuid-1", "role-uuid-2"],
            }
        }


class UserUpdate(BaseModel):
    """User update schema"""

    full_name_en: Optional[str] = Field(None, min_length=2, description="Full name in English")
    full_name_np: Optional[str] = Field(None, description="Full name in Nepali")
    phone: Optional[str] = Field(None, description="Phone number")

    class Config:
        json_schema_extra = {
            "example": {
                "full_name_en": "Ram Prasad Sharma",
                "full_name_np": "राम प्रसाद शर्मा",
                "phone": "+977-9841234567",
            }
        }


class RoleInfo(BaseModel):
    """Role information in user response"""

    id: UUID = Field(..., description="Role ID")
    code: str = Field(..., description="Role code")
    name_en: str = Field(..., description="Role name in English")
    name_np: Optional[str] = Field(None, description="Role name in Nepali")


class UserResponse(BaseModel):
    """User response schema"""

    id: UUID = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    full_name_en: str = Field(..., description="Full name in English")
    full_name_np: Optional[str] = Field(None, description="Full name in Nepali")
    phone: Optional[str] = Field(None, description="Phone number")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    school_id: UUID = Field(..., description="School/Tenant ID")
    status: str = Field(..., description="User account status")
    email_verified: bool = Field(..., description="Email verification status")
    mfa_enabled: bool = Field(..., description="MFA enabled status")
    roles: List[RoleInfo] = Field(..., description="User roles")
    permissions: List[str] = Field(..., description="User permissions")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "teacher@school.edu.np",
                "full_name_en": "Ram Prasad Sharma",
                "full_name_np": "राम प्रसाद शर्मा",
                "phone": "+977-9841234567",
                "photo_url": "https://cdn.example.com/photos/user123.jpg",
                "school_id": "school-uuid",
                "status": "active",
                "email_verified": True,
                "mfa_enabled": False,
                "roles": [
                    {
                        "id": "role-uuid",
                        "code": "teacher",
                        "name_en": "Teacher",
                        "name_np": "शिक्षक",
                    }
                ],
                "permissions": ["student:read", "attendance:create"],
                "last_login_at": "2026-06-25T08:30:00Z",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-06-25T08:30:00Z",
            }
        }


class UserListResponse(BaseModel):
    """User list response schema"""

    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")

    class Config:
        json_schema_extra = {
            "example": {
                "users": [],
                "total": 50,
                "page": 1,
                "limit": 20,
            }
        }


class ChangePasswordRequest(BaseModel):
    """Change password request schema"""

    old_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        is_valid, error = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error)
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "old_password": "OldSecure123!",
                "new_password": "NewSecure456!",
            }
        }


class UploadPhotoResponse(BaseModel):
    """Upload photo response schema"""

    photo_url: str = Field(..., description="Uploaded photo URL")

    class Config:
        json_schema_extra = {
            "example": {"photo_url": "https://cdn.example.com/photos/user123.jpg"}
        }
