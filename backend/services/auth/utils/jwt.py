"""
Nepal School Management System - JWT Utilities
JWT token generation, validation, and management using RS256
"""

import jwt
import uuid
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from shared.config.settings import PROJECT_ROOT, settings
from shared.utils.exceptions import InvalidTokenError, AuthenticationError
from shared.utils.redis_client import add_token_to_blocklist, is_token_blocklisted


# Load RSA keys
def _resolve_key_path(configured_path: str | None) -> Path:
    """Resolve key paths relative to the repository root."""
    if not configured_path:
        raise FileNotFoundError("JWT key path is not configured")

    key_path = Path(configured_path)
    return key_path if key_path.is_absolute() else PROJECT_ROOT / key_path


def _load_private_key() -> RSAPrivateKey:
    """Load RSA private key from file"""
    key_path = _resolve_key_path(settings.jwt_private_key_path)
    if not key_path.exists():
        raise FileNotFoundError(
            f"JWT private key not found at {key_path}. "
            "Run: python scripts/generate_jwt_keys.py"
        )
    with open(key_path, "rb") as key_file:
        key = serialization.load_pem_private_key(key_file.read(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise TypeError("JWT private key must be an RSA private key")
    return key


def _load_public_key() -> RSAPublicKey:
    """Load RSA public key from file"""
    key_path = _resolve_key_path(settings.jwt_public_key_path)
    if not key_path.exists():
        raise FileNotFoundError(
            f"JWT public key not found at {key_path}. "
            "Run: python scripts/generate_jwt_keys.py"
        )
    with open(key_path, "rb") as key_file:
        key = serialization.load_pem_public_key(key_file.read())
    if not isinstance(key, RSAPublicKey):
        raise TypeError("JWT public key must be an RSA public key")
    return key


# Cache keys in memory (loaded once at module import)
try:
    PRIVATE_KEY = _load_private_key()
    PUBLIC_KEY = _load_public_key()
except FileNotFoundError as e:
    print(f"WARNING: {str(e)}")
    PRIVATE_KEY = None
    PUBLIC_KEY = None


def generate_access_token(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    roles: list[str],
    permissions: list[str],
) -> str:
    """
    Generate JWT access token (RS256, 15-min expiry).

    Args:
        user_id: User UUID
        school_id: School/Tenant UUID
        roles: List of role codes (e.g., ['teacher', 'admin'])
        permissions: List of permission codes (e.g., ['student:read', 'exam:create'])

    Returns:
        Encoded JWT access token string

    Raises:
        AuthenticationError: If keys are not loaded

    Example:
        >>> token = generate_access_token(
        ...     user_id=uuid.uuid4(),
        ...     school_id=uuid.uuid4(),
        ...     roles=['teacher'],
        ...     permissions=['student:read']
        ... )
    """
    if not PRIVATE_KEY:
        raise AuthenticationError("JWT private key not loaded")

    now = datetime.utcnow()
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    # Token claims
    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "school_id": str(school_id),  # Tenant ID
        "roles": roles,  # User roles
        "permissions": permissions,  # User permissions
        "token_type": "access",  # Token type
        "jti": str(uuid.uuid4()),  # JWT ID (for revocation)
        "iat": now,  # Issued at
        "exp": expires_at,  # Expiry
    }

    # Encode token with RS256
    token = jwt.encode(
        payload,
        PRIVATE_KEY,
        algorithm=settings.jwt_algorithm
    )

    return token


def generate_refresh_token(
    user_id: uuid.UUID,
    school_id: uuid.UUID,
    session_id: uuid.UUID,
) -> str:
    """
    Generate JWT refresh token (RS256, 7-day expiry).

    Args:
        user_id: User UUID
        school_id: School/Tenant UUID
        session_id: Session UUID (for session tracking)

    Returns:
        Encoded JWT refresh token string

    Raises:
        AuthenticationError: If keys are not loaded

    Example:
        >>> token = generate_refresh_token(
        ...     user_id=uuid.uuid4(),
        ...     school_id=uuid.uuid4(),
        ...     session_id=uuid.uuid4()
        ... )
    """
    if not PRIVATE_KEY:
        raise AuthenticationError("JWT private key not loaded")

    now = datetime.utcnow()
    expires_at = now + timedelta(days=settings.jwt_refresh_token_expire_days)

    # Token claims
    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "school_id": str(school_id),  # Tenant ID
        "session_id": str(session_id),  # Session ID
        "token_type": "refresh",  # Token type
        "jti": str(uuid.uuid4()),  # JWT ID (for revocation)
        "iat": now,  # Issued at
        "exp": expires_at,  # Expiry
    }

    # Encode token with RS256
    token = jwt.encode(
        payload,
        PRIVATE_KEY,
        algorithm=settings.jwt_algorithm
    )

    return token


async def decode_token(token: str, verify_blocklist: bool = True) -> dict:
    """
    Decode and validate JWT token.

    Verifies:
    - Signature (RS256 with public key)
    - Expiry (exp claim)
    - Blocklist status (Redis)

    Args:
        token: JWT token string
        verify_blocklist: Check if token is blocklisted (default True)

    Returns:
        Decoded token claims dictionary

    Raises:
        InvalidTokenError: If token is invalid, expired, or blocklisted

    Example:
        >>> claims = await decode_token(token)
        >>> print(claims['sub'])  # User ID
    """
    if not PUBLIC_KEY:
        raise AuthenticationError("JWT public key not loaded")

    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=[settings.jwt_algorithm]
        )

        # Check if token is blocklisted
        if verify_blocklist:
            jti = payload.get("jti")
            if jti and await is_token_blocklisted(jti):
                raise InvalidTokenError("Token has been revoked")

        return payload

    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise InvalidTokenError(f"Token validation failed: {str(e)}")


async def extract_user_from_token(token: str) -> dict:
    """
    Extract user information from JWT token.

    Args:
        token: JWT token string

    Returns:
        Dictionary with user info:
        {
            "user_id": UUID,
            "school_id": UUID,
            "roles": list[str],
            "permissions": list[str],
            "jti": str,
            "token_type": str
        }

    Raises:
        InvalidTokenError: If token is invalid

    Example:
        >>> user_info = await extract_user_from_token(token)
        >>> print(user_info['user_id'])
    """
    payload = await decode_token(token)

    return {
        "user_id": uuid.UUID(payload["sub"]),
        "school_id": uuid.UUID(payload["school_id"]),
        "roles": payload.get("roles", []),
        "permissions": payload.get("permissions", []),
        "jti": payload.get("jti"),
        "token_type": payload.get("token_type"),
        "session_id": uuid.UUID(payload["session_id"]) if "session_id" in payload else None,
    }


def get_token_expiry(token: str) -> Optional[datetime]:
    """
    Get token expiry datetime (without full verification).

    Useful for checking expiry before attempting full validation.

    Args:
        token: JWT token string

    Returns:
        Expiry datetime or None if cannot decode

    Example:
        >>> expiry = get_token_expiry(token)
        >>> print(f"Expires at: {expiry}")
    """
    try:
        # Decode without verification
        payload = jwt.decode(
            token,
            options={"verify_signature": False}
        )
        exp = payload.get("exp")
        if exp:
            return datetime.utcfromtimestamp(exp)
        return None
    except Exception:
        return None


async def revoke_token(jti: str, expires_in_seconds: int):
    """
    Revoke token by adding JTI to Redis blocklist.

    Args:
        jti: JWT ID (jti claim)
        expires_in_seconds: Token remaining lifetime in seconds

    Example:
        >>> await revoke_token("abc-123", 900)  # 15 minutes
    """
    await add_token_to_blocklist(jti, expires_in_seconds)


async def revoke_token_from_string(token: str):
    """
    Revoke token by extracting JTI and adding to blocklist.

    Args:
        token: JWT token string

    Example:
        >>> await revoke_token_from_string(access_token)
    """
    # Decode without blocklist check (to allow revoking already-expired tokens)
    payload = await decode_token(token, verify_blocklist=False)
    jti = payload.get("jti")
    exp = payload.get("exp")

    if jti and exp:
        # Calculate remaining time
        expires_at = datetime.utcfromtimestamp(exp)
        now = datetime.utcnow()
        remaining_seconds = max(0, int((expires_at - now).total_seconds()))

        # Add to blocklist with remaining lifetime
        await revoke_token(jti, remaining_seconds)


def verify_token_type(payload: dict, expected_type: str):
    """
    Verify token type matches expected type.

    Args:
        payload: Decoded token payload
        expected_type: Expected token type ('access' or 'refresh')

    Raises:
        InvalidTokenError: If token type doesn't match

    Example:
        >>> payload = await decode_token(token)
        >>> verify_token_type(payload, "access")
    """
    token_type = payload.get("token_type")
    if token_type != expected_type:
        raise InvalidTokenError(
            f"Invalid token type. Expected '{expected_type}', got '{token_type}'"
        )


# Helper function to get remaining token lifetime
def get_token_remaining_lifetime(payload: dict) -> int:
    """
    Get remaining token lifetime in seconds.

    Args:
        payload: Decoded token payload

    Returns:
        Remaining seconds (0 if expired)

    Example:
        >>> payload = await decode_token(token)
        >>> remaining = get_token_remaining_lifetime(payload)
        >>> print(f"Token expires in {remaining} seconds")
    """
    exp = payload.get("exp")
    if exp:
        expires_at = datetime.utcfromtimestamp(exp)
        now = datetime.utcnow()
        remaining = (expires_at - now).total_seconds()
        return max(0, int(remaining))
    return 0
