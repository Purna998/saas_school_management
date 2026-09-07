"""
Nepal School Management System - MFA Schemas
Pydantic models for multi-factor authentication endpoints
"""

from typing import List
from pydantic import BaseModel, EmailStr, Field


class MFASetupResponse(BaseModel):
    """MFA setup response schema"""

    secret: str = Field(..., description="TOTP secret (base32 encoded)")
    qr_code: str = Field(..., description="QR code data URL for authenticator app")
    backup_codes: List[str] = Field(..., description="Backup codes for account recovery")
    issuer: str = Field(..., description="Issuer name for authenticator app")
    account: str = Field(..., description="Account identifier (user email)")

    class Config:
        json_schema_extra = {
            "example": {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code": "data:image/png;base64,iVBORw0KGgo...",
                "backup_codes": [
                    "12345678",
                    "23456789",
                    "34567890",
                    "45678901",
                    "56789012",
                ],
                "issuer": "Nepal SMS",
                "account": "teacher@school.edu.np",
            }
        }


class MFAVerifyRequest(BaseModel):
    """MFA verification request schema"""

    code: str = Field(..., min_length=6, max_length=8, description="6-digit TOTP code or 8-digit backup code")

    class Config:
        json_schema_extra = {"example": {"code": "123456"}}


class MFAEnableRequest(BaseModel):
    """MFA enable request schema"""

    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code to confirm setup")

    class Config:
        json_schema_extra = {"example": {"code": "123456"}}


class MFADisableRequest(BaseModel):
    """MFA disable request schema"""

    password: str = Field(..., min_length=1, description="User password for security")
    code: str = Field(..., min_length=6, max_length=6, description="Current TOTP code for verification")

    class Config:
        json_schema_extra = {
            "example": {"password": "SecurePass123!", "code": "123456"}
        }


class MFARegenerateBackupCodesResponse(BaseModel):
    """MFA regenerate backup codes response schema"""

    backup_codes: List[str] = Field(..., description="New backup codes")

    class Config:
        json_schema_extra = {
            "example": {
                "backup_codes": [
                    "12345678",
                    "23456789",
                    "34567890",
                    "45678901",
                    "56789012",
                    "67890123",
                    "78901234",
                    "89012345",
                    "90123456",
                    "01234567",
                ]
            }
        }


class MFALoginVerifyRequest(BaseModel):
    """MFA verification during login flow"""

    email: EmailStr = Field(..., description="User email")
    code: str = Field(..., min_length=6, max_length=8, description="TOTP code or backup code")

    class Config:
        json_schema_extra = {
            "example": {"email": "teacher@school.edu.np", "code": "123456"}
        }
