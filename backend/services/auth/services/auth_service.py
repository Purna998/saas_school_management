"""
Nepal School Management System - Auth Service
Core authentication business logic: login, logout, refresh tokens
"""

import asyncio
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from shared.config.settings import settings
from shared.utils.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    AccountLockedError,
    MFARequiredError,
)
from services.auth.models.user import User, UserStatus
from services.auth.models.role import Role
from services.auth.models.session import UserSession, LoginAttempt, LoginStatus, SessionStatus
from services.auth.utils.password import verify_password_async
from services.auth.utils.jwt import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    extract_user_from_token,
    revoke_token,
)
from services.auth.services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service for login, logout, and token management"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.rate_limiter = RateLimiter()

    async def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Dict:
        """
        Authenticate user and generate tokens.

        Args:
            email: User email
            password: User password
            ip_address: Client IP address
            user_agent: Client user agent string

        Returns:
            Dictionary with tokens and user info

        Raises:
            InvalidCredentialsError: If credentials are invalid
            AccountLockedError: If account is locked
            MFARequiredError: If MFA verification is required
        """
        # Check rate limiting
        await asyncio.gather(
            self.rate_limiter.check_login_attempts(email),
            self.rate_limiter.check_login_attempts(ip_address or "unknown"),
        )

        # Get user with roles
        result = await self.db.execute(
            select(User)
            .where(User.email == email)
            .options(joinedload(User.roles).joinedload(Role.permissions))
        )
        user = result.unique().scalar_one_or_none()

        if not user:
            await self._record_login_attempt(
                user_id=None,
                email=email,
                status=LoginStatus.FAILED,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="user_not_found",
            )
            await self.rate_limiter.record_failed_login(email)
            raise InvalidCredentialsError("Invalid email or password")

        # Verify password
        if not await verify_password_async(password, user.password_hash):
            await self.rate_limiter.record_failed_login(email)
            await self._record_login_attempt(
                user_id=user.id,
                email=email,
                status=LoginStatus.FAILED,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="invalid_password",
            )
            raise InvalidCredentialsError("Invalid email or password")

        # Check user status
        if user.status == UserStatus.LOCKED or user.is_locked:
            await self._record_login_attempt(
                user_id=user.id,
                email=email,
                status=LoginStatus.BLOCKED,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason="account_locked",
            )
            raise AccountLockedError("Account is locked")

        if user.status != UserStatus.ACTIVE:
            await self._record_login_attempt(
                user_id=user.id,
                email=email,
                status=LoginStatus.BLOCKED,
                ip_address=ip_address,
                user_agent=user_agent,
                failure_reason=f"account_{user.status.value}",
            )
            raise InvalidCredentialsError("Account is not active")

        # Check MFA
        if user.mfa_enabled:
            # MFA verification required - don't issue tokens yet
            await self._record_login_attempt(
                user_id=user.id,
                email=email,
                status=LoginStatus.MFA_REQUIRED,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            raise MFARequiredError("MFA verification required")

        # Reset rate limit on successful login
        await asyncio.gather(
            self.rate_limiter.reset_login_attempts(email),
            self.rate_limiter.reset_login_attempts(ip_address or "unknown"),
        )

        # Generate tokens
        tokens = await self._generate_tokens(user, ip_address, user_agent)

        # Update user last login
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = ip_address
        user.failed_login_attempts = 0

        # Record successful login
        await self._record_login_attempt(
            user_id=user.id,
            email=email,
            status=LoginStatus.SUCCESS,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.db.commit()

        logger.info(f"User logged in successfully: {user.email}")

        return {
            "tokens": tokens,
            "user": self._format_user_info(user),
        }

    async def logout(
        self,
        refresh_token: str,
        revoke_all_sessions: bool = False
    ):
        """
        Logout user by revoking tokens and sessions.

        Args:
            refresh_token: Refresh token to revoke
            revoke_all_sessions: If True, revoke all user sessions

        Raises:
            InvalidTokenError: If token is invalid
        """
        # Decode refresh token
        payload = await decode_token(refresh_token, verify_blocklist=False)
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload.get("session_id"))

        if revoke_all_sessions:
            # Revoke all user sessions
            result = await self.db.execute(
                select(UserSession).where(
                    UserSession.user_id == user_id,
                    UserSession.status == SessionStatus.ACTIVE
                )
            )
            sessions = result.scalars().all()

            for session in sessions:
                session.revoke()
                # Add refresh token to blocklist
                jti = session.refresh_token_jti
                # Calculate remaining lifetime
                remaining = int((session.expires_at - datetime.utcnow()).total_seconds())
                if remaining > 0:
                    await revoke_token(jti, remaining)

            await self.db.commit()
            logger.info(f"Revoked all sessions for user: {user_id}")

        else:
            # Revoke specific session
            result = await self.db.execute(
                select(UserSession).where(UserSession.id == session_id)
            )
            session = result.scalar_one_or_none()

            if session:
                session.revoke(user_id)
                # Add refresh token to blocklist
                jti = payload.get("jti")
                remaining = int((session.expires_at - datetime.utcnow()).total_seconds())
                if remaining > 0:
                    await revoke_token(jti, remaining)

                await self.db.commit()
                logger.info(f"Session revoked: {session_id}")

    async def refresh_access_token(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None
    ) -> Dict:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Valid refresh token
            ip_address: Client IP address

        Returns:
            New token pair

        Raises:
            InvalidTokenError: If refresh token is invalid or expired
        """
        # Decode and validate refresh token
        payload = await decode_token(refresh_token)
        user_id = uuid.UUID(payload["sub"])
        school_id = uuid.UUID(payload["school_id"])
        session_id = uuid.UUID(payload.get("session_id"))
        old_jti = payload.get("jti")

        # Get session
        result = await self.db.execute(
            select(UserSession).where(UserSession.id == session_id)
        )
        session = result.scalar_one_or_none()

        if not session or not session.is_active:
            raise InvalidTokenError("Session is invalid or expired")

        # Get user with roles
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise InvalidTokenError("User is invalid or inactive")

        # Generate new tokens
        roles = [role.code for role in user.roles]
        permissions = list(user.get_permissions())

        new_access_token = generate_access_token(
            user_id=user.id,
            school_id=school_id,
            roles=roles,
            permissions=permissions
        )

        new_refresh_token = generate_refresh_token(
            user_id=user.id,
            school_id=school_id,
            session_id=session.id
        )

        # Decode new refresh token to get JTI
        new_payload = await decode_token(new_refresh_token, verify_blocklist=False)
        new_jti = new_payload.get("jti")

        # Revoke old refresh token
        if old_jti:
            remaining = int((session.expires_at - datetime.utcnow()).total_seconds())
            if remaining > 0:
                await revoke_token(old_jti, remaining)

        # Update session
        session.refresh_token_jti = new_jti
        session.last_activity_at = datetime.utcnow()
        if ip_address:
            session.ip_address = ip_address

        await self.db.commit()

        logger.info(f"Access token refreshed for user: {user.email}")

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "Bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        }

    async def _generate_tokens(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict:
        """Generate access and refresh tokens for user"""
        # Get roles and permissions
        roles = [role.code for role in user.roles]
        permissions = list(user.get_permissions())

        # Generate access token
        access_token = generate_access_token(
            user_id=user.id,
            school_id=user.school_id,
            roles=roles,
            permissions=permissions
        )

        # Create session
        session = UserSession(
            id=uuid.uuid4(),
            user_id=user.id,
            status=SessionStatus.ACTIVE,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days),
            last_activity_at=datetime.utcnow(),
        )

        # Generate refresh token
        refresh_token = generate_refresh_token(
            user_id=user.id,
            school_id=user.school_id,
            session_id=session.id
        )

        # Decode to get JTI
        refresh_payload = await decode_token(refresh_token, verify_blocklist=False)
        session.refresh_token_jti = refresh_payload.get("jti")

        # Save session
        self.db.add(session)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
        }

    async def _record_login_attempt(
        self,
        email: str,
        status: LoginStatus,
        user_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ):
        """Record login attempt in database"""
        attempt = LoginAttempt(
            id=uuid.uuid4(),
            user_id=user_id,
            email=email,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason,
        )
        self.db.add(attempt)

    def _format_user_info(self, user: User) -> Dict:
        """Format user information for response"""
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name_en": user.full_name_en,
            "full_name_np": user.full_name_np,
            "phone": user.phone,
            "photo_url": user.photo_url,
            "school_id": str(user.school_id),
            "status": user.status.value,
            "email_verified": user.email_verified,
            "mfa_enabled": user.mfa_enabled,
            "roles": [role.code for role in user.roles],
            "permissions": list(user.get_permissions()),
        }
