"""
Nepal School Management System - Redis Client
Redis connection and utility functions
"""

import redis.asyncio as aioredis
from typing import Optional
import json
import logging

from shared.config.settings import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapper"""

    def __init__(self):
        self._client: Optional[aioredis.Redis] = None

    async def connect(self):
        """Connect to Redis"""
        if self._client is None:
            self._client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            logger.info("Redis client connected")

    async def disconnect(self):
        """Disconnect from Redis"""
        if self._client:
            await self._client.close()
            logger.info("Redis client disconnected")

    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if not self._client:
            await self.connect()
        return await self._client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None
    ) -> bool:
        """
        Set key-value pair.

        Args:
            key: Redis key
            value: Value to store
            expire: Expiry time in seconds

        Returns:
            True if successful
        """
        if not self._client:
            await self.connect()
        return await self._client.set(key, value, ex=expire)

    async def delete(self, key: str) -> bool:
        """Delete key"""
        if not self._client:
            await self.connect()
        return await self._client.delete(key) > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self._client:
            await self.connect()
        return await self._client.exists(key) > 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiry on key"""
        if not self._client:
            await self.connect()
        return await self._client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get time-to-live for key"""
        if not self._client:
            await self.connect()
        return await self._client.ttl(key)

    async def incr(self, key: str) -> int:
        """Increment counter"""
        if not self._client:
            await self.connect()
        return await self._client.incr(key)

    async def get_json(self, key: str) -> Optional[dict]:
        """Get JSON value"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON from key: {key}")
                return None
        return None

    async def set_json(
        self,
        key: str,
        value: dict,
        expire: Optional[int] = None
    ) -> bool:
        """Set JSON value"""
        json_str = json.dumps(value)
        return await self.set(key, json_str, expire)

    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern"""
        if not self._client:
            await self.connect()
        return await self._client.keys(pattern)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        keys = await self.keys(pattern)
        if keys:
            return await self._client.delete(*keys)
        return 0


# Global Redis client instance
redis_client = RedisClient()


# Token Blocklist Functions
async def add_token_to_blocklist(jti: str, expire_seconds: int):
    """
    Add token JTI to blocklist.

    Args:
        jti: JWT ID (jti claim)
        expire_seconds: Token expiry time in seconds
    """
    key = f"blocklist:token:{jti}"
    await redis_client.set(key, "1", expire=expire_seconds)
    logger.info(f"Token {jti} added to blocklist")


async def is_token_blocklisted(jti: str) -> bool:
    """
    Check if token is blocklisted.

    Args:
        jti: JWT ID (jti claim)

    Returns:
        True if token is blocklisted
    """
    key = f"blocklist:token:{jti}"
    return await redis_client.exists(key)


# Session Storage Functions
async def store_session(session_id: str, session_data: dict, expire_seconds: int):
    """
    Store user session data.

    Args:
        session_id: Session ID
        session_data: Session data dictionary
        expire_seconds: Session expiry time in seconds
    """
    key = f"session:{session_id}"
    await redis_client.set_json(key, session_data, expire=expire_seconds)


async def get_session(session_id: str) -> Optional[dict]:
    """
    Get user session data.

    Args:
        session_id: Session ID

    Returns:
        Session data or None if not found
    """
    key = f"session:{session_id}"
    return await redis_client.get_json(key)


async def delete_session(session_id: str):
    """
    Delete user session.

    Args:
        session_id: Session ID
    """
    key = f"session:{session_id}"
    await redis_client.delete(key)


# Rate Limiting Functions
async def increment_rate_limit(key: str, window_seconds: int) -> int:
    """
    Increment rate limit counter.

    Args:
        key: Rate limit key (e.g., "login:192.168.1.1")
        window_seconds: Time window in seconds

    Returns:
        Current count
    """
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window_seconds)
    return count


async def get_rate_limit(key: str) -> int:
    """
    Get current rate limit count.

    Args:
        key: Rate limit key

    Returns:
        Current count
    """
    value = await redis_client.get(key)
    return int(value) if value else 0


async def reset_rate_limit(key: str):
    """
    Reset rate limit counter.

    Args:
        key: Rate limit key
    """
    await redis_client.delete(key)


# Cache Functions
async def cache_set(key: str, value: str, expire_seconds: int = 3600):
    """
    Set cache value.

    Args:
        key: Cache key
        value: Value to cache
        expire_seconds: Cache expiry time in seconds (default 1 hour)
    """
    cache_key = f"cache:{key}"
    await redis_client.set(cache_key, value, expire=expire_seconds)


async def cache_get(key: str) -> Optional[str]:
    """
    Get cache value.

    Args:
        key: Cache key

    Returns:
        Cached value or None if not found
    """
    cache_key = f"cache:{key}"
    return await redis_client.get(cache_key)


async def cache_delete(key: str):
    """
    Delete cache value.

    Args:
        key: Cache key
    """
    cache_key = f"cache:{key}"
    await redis_client.delete(cache_key)


async def cache_clear_pattern(pattern: str):
    """
    Clear all cache keys matching pattern.

    Args:
        pattern: Pattern to match (e.g., "user:*")
    """
    cache_pattern = f"cache:{pattern}"
    await redis_client.delete_pattern(cache_pattern)
