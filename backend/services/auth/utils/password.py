"""
Nepal School Management System - Password Utilities
Secure password hashing and validation using bcrypt
"""

import re
import bcrypt
from typing import Tuple


# Bcrypt cost factor (as per TRD specification)
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with cost factor 12.

    Args:
        password: Plain text password

    Returns:
        Hashed password string

    Example:
        >>> hashed = hash_password("MySecure123!")
        >>> print(hashed)
        $2b$12$...
    """
    # Convert password to bytes
    password_bytes = password.encode('utf-8')

    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)

    # Return as string
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against bcrypt hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hashed password

    Returns:
        True if password matches, False otherwise

    Example:
        >>> hashed = hash_password("MySecure123!")
        >>> verify_password("MySecure123!", hashed)
        True
        >>> verify_password("WrongPassword", hashed)
        False
    """
    try:
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        # If hash is invalid or verification fails, return False
        return False


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password strength according to security requirements.

    Requirements (as per TRD):
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 digit
    - At least 1 special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

    Args:
        password: Password string to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if password meets all requirements
        - error_message: Empty string if valid, error description if invalid

    Example:
        >>> validate_password_strength("weak")
        (False, "Password must be at least 8 characters long")
        >>> validate_password_strength("MySecure123!")
        (True, "")
    """
    # Check minimum length
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    # Check for uppercase letter
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    # Check for lowercase letter
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    # Check for digit
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    # Check for special character
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]", password):
        return False, "Password must contain at least one special character"

    # All validations passed
    return True, ""


def generate_random_password(length: int = 16) -> str:
    """
    Generate a random secure password.

    Useful for temporary passwords or password resets.

    Args:
        length: Password length (default 16)

    Returns:
        Randomly generated password that meets strength requirements

    Example:
        >>> password = generate_random_password()
        >>> is_valid, _ = validate_password_strength(password)
        >>> is_valid
        True
    """
    import secrets
    import string

    # Ensure password has mix of characters
    uppercase = secrets.choice(string.ascii_uppercase)
    lowercase = secrets.choice(string.ascii_lowercase)
    digit = secrets.choice(string.digits)
    special = secrets.choice("!@#$%^&*()_+-=[]{}|")

    # Fill rest with random characters
    remaining_length = length - 4
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|"
    remaining = ''.join(secrets.choice(all_chars) for _ in range(remaining_length))

    # Combine and shuffle
    password_chars = list(uppercase + lowercase + digit + special + remaining)
    secrets.SystemRandom().shuffle(password_chars)

    return ''.join(password_chars)


# Convenience function for password change validation
def validate_password_change(
    old_password: str,
    new_password: str,
    current_hash: str
) -> Tuple[bool, str]:
    """
    Validate password change request.

    Checks:
    1. Old password is correct
    2. New password meets strength requirements
    3. New password is different from old password

    Args:
        old_password: Current password (plain text)
        new_password: New password (plain text)
        current_hash: Current hashed password

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> current_hash = hash_password("OldPass123!")
        >>> validate_password_change("OldPass123!", "NewPass456!", current_hash)
        (True, "")
        >>> validate_password_change("WrongOld!", "NewPass456!", current_hash)
        (False, "Current password is incorrect")
    """
    # Verify old password
    if not verify_password(old_password, current_hash):
        return False, "Current password is incorrect"

    # Check if new password is different
    if old_password == new_password:
        return False, "New password must be different from current password"

    # Validate new password strength
    is_valid, error = validate_password_strength(new_password)
    if not is_valid:
        return False, error

    return True, ""
