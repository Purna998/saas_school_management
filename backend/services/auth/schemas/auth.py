"""
Nepal School Management System - Auth Schemas
Pydantic models for authentication endpoints
"""

from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator

from services.auth.utils.password import validate_password_strength


class LoginRequest(BaseModel):
    """Login request schema"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")
    remember_me: bool = Field(default=False, description="Remember login (longer session)")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "teacher@school.edu.np",
                "password": "SecurePass123!",
                "remember_me": False,
            }
        }


class TokenResponse(BaseModel):
    """JWT token response"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "Bearer",
                "expires_in": 900,
            }
        }


class UserInfo(BaseModel):
    """User information in login response"""

    id: UUID = Field(..., description="User ID")
    email: EmailStr = Field(..., description="User email")
    full_name_en: str = Field(..., description="Full name in English")
    full_name_np: Optional[str] = Field(None, description="Full name in Nepali")
    phone: Optional[str] = Field(None, description="Phone number")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    school_id: UUID = Field(..., description="School/Tenant ID")
    roles: List[str] = Field(..., description="User role codes")
    permissions: List[str] = Field(..., description="User permission codes")
    mfa_enabled: bool = Field(..., description="MFA enabled status")


class LoginResponse(BaseModel):
    """Login response schema"""

    success: bool = Field(default=True, description="Success flag")
    data: dict = Field(..., description="Login response data")
    requires_mfa: bool = Field(default=False, description="MFA verification required")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "tokens": {
                        "access_token": "eyJhbGc...",
                        "refresh_token": "eyJhbGc...",
                        "token_type": "Bearer",
                        "expires_in": 900,
                    },
                    "user": {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "email": "teacher@school.edu.np",
                        "full_name_en": "Ram Prasad Sharma",
                        "roles": ["teacher"],
                        "permissions": ["student:read", "attendance:create"],
                    },
                },
                "requires_mfa": False,
            }
        }


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema"""

    refresh_token: str = Field(..., description="JWT refresh token")

    class Config:
        json_schema_extra = {
            "example": {"refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."}
        }


class RefreshTokenResponse(BaseModel):
    """Refresh token response schema"""

    success: bool = Field(default=True, description="Success flag")
    data: TokenResponse = Field(..., description="New token pair")


class LogoutRequest(BaseModel):
    """Logout request schema"""

    revoke_all_sessions: bool = Field(
        default=False, description="Revoke all user sessions"
    )

    class Config:
        json_schema_extra = {"example": {"revoke_all_sessions": False}}


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema"""

    email: EmailStr = Field(..., description="User email address")

    class Config:
        json_schema_extra = {"example": {"email": "teacher@school.edu.np"}}


class ResetPasswordRequest(BaseModel):
    """Reset password request schema"""

    token: str = Field(..., description="Password reset token")
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
                "token": "reset-token-123",
                "new_password": "NewSecure123!",
            }
        }


class VerifyEmailRequest(BaseModel):
    """Verify email request schema"""

    token: str = Field(..., description="Email verification token")

    class Config:
        json_schema_extra = {"example": {"token": "verify-token-123"}}


class RegisterRequest(BaseModel):
    """User registration request schema"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    full_name_en: str = Field(..., min_length=2, description="Full name in English")
    full_name_np: Optional[str] = Field(None, description="Full name in Nepali")
    phone: Optional[str] = Field(None, description="Phone number")
    school_id: UUID = Field(..., description="School/Tenant ID")

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
                "email": "newteacher@school.edu.np",
                "password": "SecurePass123!",
                "full_name_en": "Sita Devi Thapa",
                "full_name_np": "सीता देवी थापा",
                "phone": "+977-9841234567",
                "school_id": "123e4567-e89b-12d3-a456-426614174000",
            }
        }
