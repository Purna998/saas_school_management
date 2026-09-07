"""
Nepal School Management System - Auth Service Schemas
Pydantic request/response models for authentication endpoints
"""

from services.auth.schemas.auth import (
    LoginRequest,
    LoginResponse,
    TokenResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from services.auth.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    ChangePasswordRequest,
    UploadPhotoResponse,
)
from services.auth.schemas.mfa import (
    MFASetupResponse,
    MFAVerifyRequest,
    MFAEnableRequest,
    MFADisableRequest,
    MFARegenerateBackupCodesResponse,
)
from services.auth.schemas.session import (
    SessionResponse,
    SessionListResponse,
    RevokeSessionRequest,
)

__all__ = [
    # Auth
    "LoginRequest",
    "LoginResponse",
    "TokenResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "LogoutRequest",
    "ForgotPasswordRequest",
    "ResetPasswordRequest",
    "VerifyEmailRequest",
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserListResponse",
    "ChangePasswordRequest",
    "UploadPhotoResponse",
    # MFA
    "MFASetupResponse",
    "MFAVerifyRequest",
    "MFAEnableRequest",
    "MFADisableRequest",
    "MFARegenerateBackupCodesResponse",
    # Session
    "SessionResponse",
    "SessionListResponse",
    "RevokeSessionRequest",
]
