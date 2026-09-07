"""
Nepal School Management System - Auth API Routes
Authentication endpoints (login, logout, refresh, password reset)
"""

import uuid
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.database.base import get_db
from shared.config.settings import settings
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    AccountLockedError,
    MFARequiredError,
    RecordNotFoundError,
    NepalSMSException,
)
from shared.utils.redis_client import redis_client
from services.auth.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from services.auth.services.auth_service import AuthService
from services.auth.services.mfa_service import MFAService
from services.auth.dependencies.auth import get_current_active_user, oauth2_scheme
from services.auth.models.user import User
from services.auth.utils.password import hash_password, validate_password_strength
from services.auth.utils.jwt import revoke_token_from_string

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    User login with email and password.

    Returns:
        - access_token: JWT access token (15-min expiry)
        - refresh_token: JWT refresh token (7-day expiry)
        - user: User profile
        - requires_mfa: MFA verification required flag

    Status Codes:
        - 200: Login successful
        - 401: Invalid credentials
        - 423: Account locked
    """
    try:
        auth_service = AuthService(db)

        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        result = await auth_service.login(
            email=login_data.email,
            password=login_data.password,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return {
            "success": True,
            "data": result,
            "requires_mfa": False,
        }

    except MFARequiredError:
        return {
            "success": True,
            "data": {"email": login_data.email},
            "requires_mfa": True,
        }

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response(str(e), "INVALID_CREDENTIALS"),
        )

    except AccountLockedError as e:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=error_response(str(e), "ACCOUNT_LOCKED"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response("Login failed", "LOGIN_ERROR"),
        )


@router.post("/mfa-login")
async def mfa_login(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Complete login with MFA verification.

    Called after initial login returns requires_mfa=True.

    Request Body:
        - email: User email
        - code: TOTP code or backup code

    Status Codes:
        - 200: Login successful with tokens
        - 401: Invalid MFA code
    """
    from services.auth.schemas.mfa import MFALoginVerifyRequest
    from pydantic import ValidationError

    body = await request.json()
    try:
        mfa_data = MFALoginVerifyRequest(**body)
    except (ValidationError, Exception) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Invalid request body", "VALIDATION_ERROR"),
        )

    # Get user
    result = await db.execute(
        select(User).where(User.email == mfa_data.email)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("Invalid credentials", "INVALID_CREDENTIALS"),
        )

    # Verify MFA code
    try:
        mfa_service = MFAService(db)
        await mfa_service.verify_mfa_code(user, mfa_data.code)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response("Invalid MFA code", "INVALID_MFA_CODE"),
        )

    # Generate tokens after MFA verification
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    auth_service = AuthService(db)
    tokens = await auth_service._generate_tokens(user, ip_address, user_agent)

    user.last_login_at = datetime.utcnow()
    user.last_login_ip = ip_address
    await db.commit()

    return success_response(data={
        "tokens": tokens,
        "user": auth_service._format_user_info(user),
    })


@router.post("/refresh")
async def refresh_token(
    request: Request,
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Returns:
        - access_token: New JWT access token
        - refresh_token: New JWT refresh token (rotated)

    Status Codes:
        - 200: Token refreshed
        - 401: Invalid or expired refresh token
    """
    try:
        auth_service = AuthService(db)

        ip_address = request.client.host if request.client else None

        tokens = await auth_service.refresh_access_token(
            refresh_token=refresh_data.refresh_token,
            ip_address=ip_address,
        )

        return success_response(data=tokens)

    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_response(str(e), "INVALID_TOKEN"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response("Token refresh failed", "REFRESH_ERROR"),
        )


@router.post("/logout")
async def logout(
    request: Request,
    logout_data: LogoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    User logout - invalidate tokens.

    Adds tokens to Redis blocklist and revokes session.

    Status Codes:
        - 200: Logout successful
        - 401: Unauthorized
    """
    try:
        auth_service = AuthService(db)

        # Get the current access token from the Authorization header
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            access_token = auth_header[7:]
            await revoke_token_from_string(access_token)

        # If user has token info with session, revoke the session
        token_info = getattr(current_user, '_token_info', None)
        if token_info and token_info.get("session_id"):
            from services.auth.models.session import UserSession, SessionStatus
            session_id = token_info["session_id"]

            if logout_data.revoke_all_sessions:
                # Revoke all sessions
                result = await db.execute(
                    select(UserSession).where(
                        UserSession.user_id == current_user.id,
                        UserSession.status == SessionStatus.ACTIVE
                    )
                )
                sessions = result.scalars().all()
                for session in sessions:
                    session.revoke(current_user.id)
            else:
                # Revoke current session only
                result = await db.execute(
                    select(UserSession).where(UserSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.revoke(current_user.id)

            await db.commit()

        return success_response(data={"message": "Logout successful"})

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response("Logout failed", "LOGOUT_ERROR"),
        )


@router.post("/forgot-password")
async def forgot_password(
    forgot_data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset.

    Generates a reset token and stores it. In production, sends via email/SMS.

    Status Codes:
        - 200: Reset token generated (always returns success to prevent email enumeration)
    """
    # Always return success to prevent email enumeration attacks
    result = await db.execute(
        select(User).where(User.email == forgot_data.email)
    )
    user = result.scalar_one_or_none()

    if user:
        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        token_hash = hash_password(reset_token)

        # Store token with 1-hour expiry
        user.password_reset_token = token_hash
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        await db.commit()

        # Store token in Redis for quick lookup (1 hour TTL)
        await redis_client.set(
            f"password_reset:{reset_token}",
            str(user.id),
            expire=3600
        )

        # TODO: Send email/SMS with reset token in production
        # For development, include token in response
        if settings.is_development:
            return success_response(data={
                "message": "Password reset instructions sent",
                "dev_token": reset_token,
            })

    return success_response(
        data={"message": "If an account with that email exists, reset instructions have been sent"}
    )


@router.post("/reset-password")
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using token.

    Status Codes:
        - 200: Password reset successful
        - 400: Invalid or expired token
    """
    # Look up token in Redis
    user_id_str = await redis_client.get(f"password_reset:{reset_data.token}")

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Invalid or expired reset token", "INVALID_RESET_TOKEN"),
        )

    # Get user
    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Invalid reset token", "INVALID_RESET_TOKEN"),
        )

    # Check token expiry
    if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Reset token has expired", "TOKEN_EXPIRED"),
        )

    # Update password
    user.password_hash = hash_password(reset_data.new_password)
    user.password_changed_at = datetime.utcnow()
    user.password_reset_token = None
    user.password_reset_expires = None

    await db.commit()

    # Remove token from Redis
    await redis_client.delete(f"password_reset:{reset_data.token}")

    return success_response(data={"message": "Password reset successful"})


@router.post("/verify-email")
async def verify_email(
    verify_data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify email address using token.

    Status Codes:
        - 200: Email verified
        - 400: Invalid or expired token
    """
    # Look up verification token in Redis
    user_id_str = await redis_client.get(f"email_verify:{verify_data.token}")

    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Invalid or expired verification token", "INVALID_VERIFICATION_TOKEN"),
        )

    user_id = uuid.UUID(user_id_str)
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Invalid verification token", "INVALID_VERIFICATION_TOKEN"),
        )

    if user.email_verified:
        return success_response(data={"message": "Email is already verified"})

    # Verify email
    user.email_verified = True
    user.email_verified_at = datetime.utcnow()
    await db.commit()

    # Remove token from Redis
    await redis_client.delete(f"email_verify:{verify_data.token}")

    return success_response(data={"message": "Email verified successfully"})
