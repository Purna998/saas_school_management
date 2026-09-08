"""
Nepal School Management System - MFA Service
TOTP-based Multi-Factor Authentication business logic
"""

import uuid
import secrets
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
import asyncio
import base64

from shared.config.settings import settings
from shared.utils.exceptions import (
    AuthenticationError,
    MFAAlreadyEnabledError,
    MFANotEnabledError,
    InvalidCredentialsError,
)
from services.auth.models.user import User
from services.auth.models.mfa import MFASecret
from services.auth.utils.password import verify_password_async

logger = logging.getLogger(__name__)

BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 8


class MFAService:
    """MFA/TOTP service for two-factor authentication"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def setup_mfa(self, user: User) -> dict:
        """
        Generate TOTP secret and QR code for MFA setup.

        Args:
            user: User object

        Returns:
            Dictionary with secret, qr_code, and backup_codes

        Raises:
            MFAAlreadyEnabledError: If MFA is already enabled
        """
        if user.mfa_enabled:
            raise MFAAlreadyEnabledError("MFA is already enabled for this account")

        # Check if there's an existing unverified secret
        result = await self.db.execute(
            select(MFASecret).where(MFASecret.user_id == user.id)
        )
        existing = result.scalar_one_or_none()

        # Generate new TOTP secret
        secret = pyotp.random_base32()

        # Generate backup codes
        backup_codes = self._generate_backup_codes()
        backup_codes_str = ",".join(backup_codes)

        if existing:
            existing.secret = secret
            existing.backup_codes = backup_codes_str
            existing.is_verified = False
        else:
            mfa_secret = MFASecret(
                id=uuid.uuid4(),
                user_id=user.id,
                secret=secret,
                backup_codes=backup_codes_str,
                is_verified=False,
            )
            self.db.add(mfa_secret)

        await self.db.flush()

        # Generate provisioning URI
        totp = pyotp.TOTP(secret, digits=settings.mfa_digits, interval=settings.mfa_interval)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=settings.mfa_issuer_name
        )

        # Generate QR code as base64 data URL
        qr_code_data = await asyncio.to_thread(self._generate_qr_code, provisioning_uri)

        return {
            "secret": secret,
            "qr_code": qr_code_data,
            "provisioning_uri": provisioning_uri,
            "backup_codes": backup_codes,
        }

    async def verify_and_enable_mfa(self, user: User, code: str) -> bool:
        """
        Verify TOTP code and enable MFA.

        Args:
            user: User object
            code: 6-digit TOTP code

        Returns:
            True if verification successful

        Raises:
            AuthenticationError: If no MFA setup found
            InvalidCredentialsError: If code is invalid
        """
        result = await self.db.execute(
            select(MFASecret).where(MFASecret.user_id == user.id)
        )
        mfa_secret = result.scalar_one_or_none()

        if not mfa_secret:
            raise AuthenticationError("MFA has not been set up. Call /mfa/setup first.")

        # Verify TOTP code
        totp = pyotp.TOTP(mfa_secret.secret, digits=settings.mfa_digits, interval=settings.mfa_interval)
        if not totp.verify(code, valid_window=1):
            raise InvalidCredentialsError("Invalid TOTP code")

        # Mark as verified and enable MFA
        mfa_secret.is_verified = True
        user.mfa_enabled = True
        user.mfa_enabled_at = datetime.utcnow()

        await self.db.flush()
        logger.info(f"MFA enabled for user: {user.email}")

        return True

    async def verify_mfa_code(self, user: User, code: str) -> bool:
        """
        Verify MFA code during login (TOTP or backup code).

        Args:
            user: User object
            code: TOTP code or backup code

        Returns:
            True if verification successful

        Raises:
            MFANotEnabledError: If MFA is not enabled
            InvalidCredentialsError: If code is invalid
        """
        if not user.mfa_enabled:
            raise MFANotEnabledError("MFA is not enabled for this account")

        result = await self.db.execute(
            select(MFASecret).where(MFASecret.user_id == user.id)
        )
        mfa_secret = result.scalar_one_or_none()

        if not mfa_secret or not mfa_secret.is_verified:
            raise AuthenticationError("MFA configuration is invalid")

        # Try TOTP verification first
        totp = pyotp.TOTP(mfa_secret.secret, digits=settings.mfa_digits, interval=settings.mfa_interval)
        if totp.verify(code, valid_window=1):
            return True

        # Try backup code
        if self._verify_backup_code(mfa_secret, code):
            await self.db.flush()
            return True

        raise InvalidCredentialsError("Invalid MFA code")

    async def disable_mfa(self, user: User, password: str, code: str) -> bool:
        """
        Disable MFA for user.

        Args:
            user: User object
            password: User's password for confirmation
            code: Current TOTP code

        Returns:
            True if MFA disabled successfully

        Raises:
            MFANotEnabledError: If MFA not enabled
            InvalidCredentialsError: If password or code is invalid
        """
        if not user.mfa_enabled:
            raise MFANotEnabledError("MFA is not enabled for this account")

        # Verify password
        if not await verify_password_async(password, user.password_hash):
            raise InvalidCredentialsError("Invalid password")

        # Verify TOTP code
        result = await self.db.execute(
            select(MFASecret).where(MFASecret.user_id == user.id)
        )
        mfa_secret = result.scalar_one_or_none()

        if not mfa_secret:
            raise AuthenticationError("MFA configuration not found")

        totp = pyotp.TOTP(mfa_secret.secret, digits=settings.mfa_digits, interval=settings.mfa_interval)
        if not totp.verify(code, valid_window=1):
            raise InvalidCredentialsError("Invalid TOTP code")

        # Disable MFA
        user.mfa_enabled = False
        user.mfa_enabled_at = None
        await self.db.delete(mfa_secret)
        await self.db.flush()

        logger.info(f"MFA disabled for user: {user.email}")
        return True

    async def regenerate_backup_codes(self, user: User, password: str) -> List[str]:
        """
        Regenerate backup codes.

        Args:
            user: User object
            password: User's password for confirmation

        Returns:
            List of new backup codes

        Raises:
            MFANotEnabledError: If MFA not enabled
            InvalidCredentialsError: If password is invalid
        """
        if not user.mfa_enabled:
            raise MFANotEnabledError("MFA is not enabled for this account")

        if not await verify_password_async(password, user.password_hash):
            raise InvalidCredentialsError("Invalid password")

        result = await self.db.execute(
            select(MFASecret).where(MFASecret.user_id == user.id)
        )
        mfa_secret = result.scalar_one_or_none()

        if not mfa_secret:
            raise AuthenticationError("MFA configuration not found")

        # Generate new backup codes
        backup_codes = self._generate_backup_codes()
        mfa_secret.backup_codes = ",".join(backup_codes)

        await self.db.flush()
        logger.info(f"Backup codes regenerated for user: {user.email}")

        return backup_codes

    def _generate_backup_codes(self) -> List[str]:
        """Generate a set of backup codes"""
        return [
            secrets.token_hex(BACKUP_CODE_LENGTH // 2).upper()
            for _ in range(BACKUP_CODE_COUNT)
        ]

    def _verify_backup_code(self, mfa_secret: MFASecret, code: str) -> bool:
        """Verify and consume a backup code"""
        if not mfa_secret.backup_codes:
            return False

        codes = mfa_secret.backup_codes.split(",")
        code_upper = code.upper().strip()

        if code_upper in codes:
            codes.remove(code_upper)
            mfa_secret.backup_codes = ",".join(codes)
            return True

        return False

    def _generate_qr_code(self, data: str) -> str:
        """Generate QR code as base64 PNG data URL"""
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
