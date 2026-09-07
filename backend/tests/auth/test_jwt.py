"""
Nepal School Management System - JWT Utilities Tests
Tests for JWT token generation, validation, and management
"""

import pytest
import uuid
from datetime import datetime, timedelta
import asyncio

from services.auth.utils.jwt import (
    generate_access_token,
    generate_refresh_token,
    decode_token,
    extract_user_from_token,
    get_token_expiry,
    revoke_token,
    verify_token_type,
    get_token_remaining_lifetime,
)
from shared.utils.exceptions import InvalidTokenError


class TestTokenGeneration:
    """Test JWT token generation"""

    def test_generate_access_token(self):
        """Test access token generation"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher", "admin"]
        permissions = ["student:read", "exam:create"]

        token = generate_access_token(user_id, school_id, roles, permissions)

        # Check token is not empty
        assert token
        # Check token format (JWT has 3 parts separated by dots)
        parts = token.split(".")
        assert len(parts) == 3

    def test_generate_refresh_token(self):
        """Test refresh token generation"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        session_id = uuid.uuid4()

        token = generate_refresh_token(user_id, school_id, session_id)

        # Check token is not empty
        assert token
        # Check token format
        parts = token.split(".")
        assert len(parts) == 3

    @pytest.mark.asyncio
    async def test_decode_access_token(self):
        """Test decoding access token"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher"]
        permissions = ["student:read"]

        token = generate_access_token(user_id, school_id, roles, permissions)
        payload = await decode_token(token, verify_blocklist=False)

        # Check claims
        assert payload["sub"] == str(user_id)
        assert payload["school_id"] == str(school_id)
        assert payload["roles"] == roles
        assert payload["permissions"] == permissions
        assert payload["token_type"] == "access"
        assert "jti" in payload
        assert "iat" in payload
        assert "exp" in payload

    @pytest.mark.asyncio
    async def test_decode_refresh_token(self):
        """Test decoding refresh token"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        session_id = uuid.uuid4()

        token = generate_refresh_token(user_id, school_id, session_id)
        payload = await decode_token(token, verify_blocklist=False)

        # Check claims
        assert payload["sub"] == str(user_id)
        assert payload["school_id"] == str(school_id)
        assert payload["session_id"] == str(session_id)
        assert payload["token_type"] == "refresh"
        assert "jti" in payload

    @pytest.mark.asyncio
    async def test_extract_user_from_access_token(self):
        """Test extracting user info from access token"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher"]
        permissions = ["student:read"]

        token = generate_access_token(user_id, school_id, roles, permissions)
        user_info = await extract_user_from_token(token)

        # Check extracted info
        assert user_info["user_id"] == user_id
        assert user_info["school_id"] == school_id
        assert user_info["roles"] == roles
        assert user_info["permissions"] == permissions
        assert user_info["token_type"] == "access"
        assert user_info["jti"]

    @pytest.mark.asyncio
    async def test_extract_user_from_refresh_token(self):
        """Test extracting user info from refresh token"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        session_id = uuid.uuid4()

        token = generate_refresh_token(user_id, school_id, session_id)
        user_info = await extract_user_from_token(token)

        # Check extracted info
        assert user_info["user_id"] == user_id
        assert user_info["school_id"] == school_id
        assert user_info["session_id"] == session_id
        assert user_info["token_type"] == "refresh"


class TestTokenValidation:
    """Test JWT token validation"""

    def test_get_token_expiry(self):
        """Test getting token expiry"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher"]
        permissions = ["student:read"]

        token = generate_access_token(user_id, school_id, roles, permissions)
        expiry = get_token_expiry(token)

        # Check expiry is in the future
        assert expiry is not None
        assert expiry > datetime.utcnow()

        # Check expiry is approximately 15 minutes from now
        expected_expiry = datetime.utcnow() + timedelta(minutes=15)
        time_diff = abs((expiry - expected_expiry).total_seconds())
        assert time_diff < 5  # Within 5 seconds

    @pytest.mark.asyncio
    async def test_decode_invalid_token(self):
        """Test decoding invalid token"""
        invalid_token = "invalid.token.here"

        with pytest.raises(InvalidTokenError):
            await decode_token(invalid_token, verify_blocklist=False)

    @pytest.mark.asyncio
    async def test_verify_token_type_access(self):
        """Test verifying access token type"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher"]
        permissions = ["student:read"]

        token = generate_access_token(user_id, school_id, roles, permissions)
        payload = await decode_token(token, verify_blocklist=False)

        # Should not raise for correct type
        verify_token_type(payload, "access")

        # Should raise for incorrect type
        with pytest.raises(InvalidTokenError):
            verify_token_type(payload, "refresh")

    @pytest.mark.asyncio
    async def test_verify_token_type_refresh(self):
        """Test verifying refresh token type"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        session_id = uuid.uuid4()

        token = generate_refresh_token(user_id, school_id, session_id)
        payload = await decode_token(token, verify_blocklist=False)

        # Should not raise for correct type
        verify_token_type(payload, "refresh")

        # Should raise for incorrect type
        with pytest.raises(InvalidTokenError):
            verify_token_type(payload, "access")

    @pytest.mark.asyncio
    async def test_get_token_remaining_lifetime(self):
        """Test getting token remaining lifetime"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher"]
        permissions = ["student:read"]

        token = generate_access_token(user_id, school_id, roles, permissions)
        payload = await decode_token(token, verify_blocklist=False)

        remaining = get_token_remaining_lifetime(payload)

        # Should be approximately 15 minutes (900 seconds)
        assert remaining > 0
        assert 890 < remaining < 910  # Within 10 seconds of 900


class TestTokenTypes:
    """Test different token types"""

    @pytest.mark.asyncio
    async def test_access_token_has_permissions(self):
        """Test that access token contains permissions"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher"]
        permissions = ["student:read", "exam:create"]

        token = generate_access_token(user_id, school_id, roles, permissions)
        user_info = await extract_user_from_token(token)

        assert "permissions" in user_info
        assert len(user_info["permissions"]) == 2
        assert "student:read" in user_info["permissions"]

    @pytest.mark.asyncio
    async def test_refresh_token_has_session_id(self):
        """Test that refresh token contains session ID"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        session_id = uuid.uuid4()

        token = generate_refresh_token(user_id, school_id, session_id)
        user_info = await extract_user_from_token(token)

        assert "session_id" in user_info
        assert user_info["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_token_uniqueness(self):
        """Test that generated tokens are unique"""
        user_id = uuid.uuid4()
        school_id = uuid.uuid4()
        roles = ["teacher"]
        permissions = ["student:read"]

        token1 = generate_access_token(user_id, school_id, roles, permissions)
        token2 = generate_access_token(user_id, school_id, roles, permissions)

        # Tokens should be different (different JTI)
        assert token1 != token2

        # But both should decode successfully
        payload1 = await decode_token(token1, verify_blocklist=False)
        payload2 = await decode_token(token2, verify_blocklist=False)

        # JTIs should be different
        assert payload1["jti"] != payload2["jti"]


# Note: Token blocklist tests require Redis, which should be tested in integration tests
# These unit tests skip Redis operations with verify_blocklist=False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
