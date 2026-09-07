"""
Nepal School Management System - Password Utilities Tests
Tests for password hashing, verification, and validation
"""

import pytest
from services.auth.utils.password import (
    hash_password,
    verify_password,
    validate_password_strength,
    generate_random_password,
    validate_password_change,
)


class TestPasswordHashing:
    """Test password hashing and verification"""

    def test_hash_password(self):
        """Test password hashing"""
        password = "MySecure123!"
        hashed = hash_password(password)

        # Check hash is not empty
        assert hashed
        # Check hash is different from password
        assert hashed != password
        # Check hash starts with $2b$ (bcrypt identifier)
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "MySecure123!"
        hashed = hash_password(password)

        # Verify correct password
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "MySecure123!"
        hashed = hash_password(password)

        # Verify incorrect password
        assert verify_password("WrongPassword!", hashed) is False

    def test_hash_password_same_input_different_output(self):
        """Test that same password produces different hashes (salt)"""
        password = "MySecure123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to salt
        assert hash1 != hash2

        # But both should verify successfully
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_verify_password_invalid_hash(self):
        """Test password verification with invalid hash"""
        password = "MySecure123!"
        invalid_hash = "not-a-valid-hash"

        # Should return False for invalid hash
        assert verify_password(password, invalid_hash) is False


class TestPasswordStrength:
    """Test password strength validation"""

    def test_validate_strong_password(self):
        """Test validation of strong password"""
        is_valid, error = validate_password_strength("MySecure123!")
        assert is_valid is True
        assert error == ""

    def test_validate_password_too_short(self):
        """Test validation of too short password"""
        is_valid, error = validate_password_strength("Short1!")
        assert is_valid is False
        assert "8 characters" in error

    def test_validate_password_no_uppercase(self):
        """Test validation of password without uppercase"""
        is_valid, error = validate_password_strength("mysecure123!")
        assert is_valid is False
        assert "uppercase" in error.lower()

    def test_validate_password_no_lowercase(self):
        """Test validation of password without lowercase"""
        is_valid, error = validate_password_strength("MYSECURE123!")
        assert is_valid is False
        assert "lowercase" in error.lower()

    def test_validate_password_no_digit(self):
        """Test validation of password without digit"""
        is_valid, error = validate_password_strength("MySecurePass!")
        assert is_valid is False
        assert "digit" in error.lower()

    def test_validate_password_no_special(self):
        """Test validation of password without special character"""
        is_valid, error = validate_password_strength("MySecure123")
        assert is_valid is False
        assert "special" in error.lower()

    def test_validate_various_strong_passwords(self):
        """Test validation of various strong passwords"""
        strong_passwords = [
            "Password1!",
            "MyPass123@",
            "Secure#2024",
            "Testing$456",
            "Valid%Pass7",
        ]

        for password in strong_passwords:
            is_valid, error = validate_password_strength(password)
            assert is_valid is True, f"Password '{password}' should be valid"
            assert error == ""


class TestGenerateRandomPassword:
    """Test random password generation"""

    def test_generate_random_password_default_length(self):
        """Test random password generation with default length"""
        password = generate_random_password()

        # Check length
        assert len(password) == 16

        # Check it meets strength requirements
        is_valid, error = validate_password_strength(password)
        assert is_valid is True, f"Generated password failed: {error}"

    def test_generate_random_password_custom_length(self):
        """Test random password generation with custom length"""
        password = generate_random_password(length=20)

        # Check length
        assert len(password) == 20

        # Check it meets strength requirements
        is_valid, error = validate_password_strength(password)
        assert is_valid is True

    def test_generate_random_password_uniqueness(self):
        """Test that generated passwords are unique"""
        password1 = generate_random_password()
        password2 = generate_random_password()

        # Should be different
        assert password1 != password2

    def test_generate_random_password_minimum_length(self):
        """Test random password generation with minimum length"""
        password = generate_random_password(length=8)

        # Check length
        assert len(password) == 8

        # Check it meets strength requirements
        is_valid, error = validate_password_strength(password)
        assert is_valid is True


class TestPasswordChange:
    """Test password change validation"""

    def test_validate_password_change_success(self):
        """Test successful password change validation"""
        old_password = "OldPass123!"
        current_hash = hash_password(old_password)
        new_password = "NewPass456!"

        is_valid, error = validate_password_change(
            old_password,
            new_password,
            current_hash
        )

        assert is_valid is True
        assert error == ""

    def test_validate_password_change_wrong_old_password(self):
        """Test password change with wrong old password"""
        old_password = "OldPass123!"
        current_hash = hash_password(old_password)
        new_password = "NewPass456!"

        is_valid, error = validate_password_change(
            "WrongOld123!",
            new_password,
            current_hash
        )

        assert is_valid is False
        assert "current password" in error.lower()

    def test_validate_password_change_same_password(self):
        """Test password change with same password"""
        old_password = "OldPass123!"
        current_hash = hash_password(old_password)

        is_valid, error = validate_password_change(
            old_password,
            old_password,  # Same as old
            current_hash
        )

        assert is_valid is False
        assert "different" in error.lower()

    def test_validate_password_change_weak_new_password(self):
        """Test password change with weak new password"""
        old_password = "OldPass123!"
        current_hash = hash_password(old_password)
        new_password = "weak"  # Weak password

        is_valid, error = validate_password_change(
            old_password,
            new_password,
            current_hash
        )

        assert is_valid is False
        assert error != ""  # Should have validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
