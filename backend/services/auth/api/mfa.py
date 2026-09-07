"""
Nepal School Management System - MFA API Routes
Multi-Factor Authentication (TOTP) endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    MFAAlreadyEnabledError,
    MFANotEnabledError,
)
from services.auth.dependencies.auth import get_current_active_user
from services.auth.models.user import User
from services.auth.schemas.mfa import (
    MFASetupResponse,
    MFAVerifyRequest,
    MFAEnableRequest,
    MFADisableRequest,
    MFARegenerateBackupCodesResponse,
)
from services.auth.services.mfa_service import MFAService

router = APIRouter()


@router.post("/setup", response_model=MFASetupResponse)
async def setup_mfa(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Setup MFA/TOTP for current user.

    Returns:
        - secret: TOTP secret (base32)
        - qr_code: QR code data URL for authenticator app
        - backup_codes: List of backup codes

    Status Codes:
        - 200: MFA setup initiated
        - 401: Unauthorized
        - 409: MFA already enabled
    """
    try:
        mfa_service = MFAService(db)
        result = await mfa_service.setup_mfa(current_user)

        return MFASetupResponse(
            secret=result["secret"],
            qr_code=result["qr_code"],
            backup_codes=result["backup_codes"],
            issuer=result.get("issuer", "Nepal SMS"),
            account=current_user.email,
        )

    except MFAAlreadyEnabledError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(str(e), "MFA_ALREADY_ENABLED"),
        )


@router.post("/verify")
async def verify_mfa(
    verify_data: MFAVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify MFA/TOTP code during login or for validation.

    Request Body:
        - code: 6-digit TOTP code or backup code

    Status Codes:
        - 200: MFA verified
        - 401: Invalid code
    """
    try:
        mfa_service = MFAService(db)
        await mfa_service.verify_mfa_code(current_user, verify_data.code)

        return success_response(data={"message": "MFA code verified successfully"})

    except (InvalidCredentialsError, MFANotEnabledError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response(str(e), "INVALID_MFA_CODE"),
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "MFA_CONFIG_ERROR"),
        )


@router.post("/enable")
async def enable_mfa(
    enable_data: MFAEnableRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enable MFA after successful setup and verification.

    Request Body:
        - code: 6-digit TOTP code (to confirm setup)

    Status Codes:
        - 200: MFA enabled
        - 400: Invalid code or setup not initiated
        - 401: Unauthorized
    """
    try:
        mfa_service = MFAService(db)
        await mfa_service.verify_and_enable_mfa(current_user, enable_data.code)

        return success_response(data={"message": "MFA enabled successfully"})

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_MFA_CODE"),
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "MFA_SETUP_ERROR"),
        )


@router.post("/disable")
async def disable_mfa(
    disable_data: MFADisableRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disable MFA for current user.

    Request Body:
        - password: User password (for security)
        - code: Current TOTP code (for verification)

    Status Codes:
        - 200: MFA disabled
        - 400: Invalid password or code
        - 401: Unauthorized
    """
    try:
        mfa_service = MFAService(db)
        await mfa_service.disable_mfa(
            current_user,
            disable_data.password,
            disable_data.code
        )

        return success_response(data={"message": "MFA disabled successfully"})

    except MFANotEnabledError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "MFA_NOT_ENABLED"),
        )

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_CREDENTIALS"),
        )


@router.post("/regenerate-backup-codes", response_model=MFARegenerateBackupCodesResponse)
async def regenerate_backup_codes(
    password_data: MFADisableRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Regenerate MFA backup codes.

    Requires password and current TOTP code for confirmation.

    Returns:
        - backup_codes: New list of backup codes

    Status Codes:
        - 200: Backup codes regenerated
        - 400: Invalid password
        - 401: Unauthorized
        - 403: MFA not enabled
    """
    try:
        mfa_service = MFAService(db)
        backup_codes = await mfa_service.regenerate_backup_codes(
            current_user,
            password_data.password,
        )

        return MFARegenerateBackupCodesResponse(backup_codes=backup_codes)

    except MFANotEnabledError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response(str(e), "MFA_NOT_ENABLED"),
        )

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_CREDENTIALS"),
        )
