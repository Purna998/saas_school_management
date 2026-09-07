"""
Nepal School Management System - Rate Limiter
Redis-based rate limiting for login attempts and API calls
"""

import logging
from typing import Optional
from datetime import datetime, timedelta

from shared.config.settings import settings
from shared.utils.redis_client import (
    increment_rate_limit,
    get_rate_limit,
    reset_rate_limit,
)
from shared.utils.exceptions import AccountLockedError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiting service using Redis"""

    @staticmethod
    async def check_login_attempts(identifier: str) -> bool:
        """
        Check if login attempts are within limit.

        Args:
            identifier: IP address or email

        Returns:
            True if allowed, False if rate limited

        Raises:
            AccountLockedError: If account is locked due to too many attempts
        """
        key = f"login:attempts:{identifier}"
        lockout_key = f"login:lockout:{identifier}"

        # Check if currently locked out
        lockout_count = await get_rate_limit(lockout_key)
        if lockout_count > 0:
            raise AccountLockedError(
                f"Account locked due to too many failed login attempts. "
                f"Try again in {settings.login_lockout_duration_minutes} minutes."
            )

        # Check attempt count
        attempts = await get_rate_limit(key)
        if attempts >= settings.max_login_attempts:
            # Lock account
            await increment_rate_limit(
                lockout_key,
                settings.login_lockout_duration_minutes * 60
            )
            logger.warning(f"Account locked due to {attempts} failed login attempts: {identifier}")
            raise AccountLockedError(
                f"Too many failed login attempts. "
                f"Account locked for {settings.login_lockout_duration_minutes} minutes."
            )

        return True

    @staticmethod
    async def record_failed_login(identifier: str):
        """
        Record a failed login attempt.

        Args:
            identifier: IP address or email
        """
        key = f"login:attempts:{identifier}"
        # Increment with 15-minute window
        count = await increment_rate_limit(key, 15 * 60)
        logger.info(f"Failed login attempt {count}/{settings.max_login_attempts} for: {identifier}")

    @staticmethod
    async def reset_login_attempts(identifier: str):
        """
        Reset login attempts (after successful login).

        Args:
            identifier: IP address or email
        """
        key = f"login:attempts:{identifier}"
        await reset_rate_limit(key)

    @staticmethod
    async def check_api_rate_limit(
        user_id: str,
        endpoint: str,
        limit_per_minute: Optional[int] = None
    ) -> bool:
        """
        Check API rate limit for a user endpoint.

        Args:
            user_id: User ID
            endpoint: API endpoint path
            limit_per_minute: Rate limit (default from settings)

        Returns:
            True if allowed, False if rate limited
        """
        if limit_per_minute is None:
            limit_per_minute = settings.rate_limit_per_minute

        key = f"api:ratelimit:{user_id}:{endpoint}"
        count = await increment_rate_limit(key, 60)  # 1-minute window

        if count > limit_per_minute:
            logger.warning(
                f"Rate limit exceeded for user {user_id} on {endpoint}: "
                f"{count}/{limit_per_minute} per minute"
            )
            return False

        return True

    @staticmethod
    async def get_remaining_attempts(identifier: str) -> int:
        """
        Get remaining login attempts before lockout.

        Args:
            identifier: IP address or email

        Returns:
            Number of remaining attempts
        """
        key = f"login:attempts:{identifier}"
        attempts = await get_rate_limit(key)
        return max(0, settings.max_login_attempts - attempts)

    @staticmethod
    async def is_locked_out(identifier: str) -> bool:
        """
        Check if identifier is currently locked out.

        Args:
            identifier: IP address or email

        Returns:
            True if locked out, False otherwise
        """
        lockout_key = f"login:lockout:{identifier}"
        lockout_count = await get_rate_limit(lockout_key)
        return lockout_count > 0
