"""
Nepal School Management System - Authentication Dependencies
FastAPI dependencies for JWT authentication and authorization
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.database.base import get_db
from shared.utils.exceptions import (
    InvalidTokenError,
    AuthenticationError,
    AuthorizationError,
)
from services.auth.models.user import User
from services.auth.utils.jwt import extract_user_from_token


# HTTP Bearer token scheme
oauth2_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Extracts and validates JWT from Authorization header,
    then fetches user from database.

    Args:
        credentials: HTTP Bearer token
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException 401: If token is invalid or user not found

    Usage:
        @router.get("/profile")
        async def get_profile(current_user: User = Depends(get_current_user)):
            return current_user
    """
    try:
        # Extract token
        token = credentials.credentials

        # Decode and validate token
        user_info = await extract_user_from_token(token)

        # Get user from database
        user_id = user_info["user_id"]
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "USER_NOT_FOUND",
                        "message": "User not found",
                        "details": {},
                    },
                },
            )

        # Store token info in user object for later use
        user._token_info = user_info  # Private attribute

        return user

    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "INVALID_TOKEN",
                    "message": str(e),
                    "details": {},
                },
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "AUTH_FAILED",
                    "message": "Authentication failed",
                    "details": {"error": str(e)},
                },
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current authenticated and active user.

    Checks that user is active and not locked.

    Args:
        current_user: Current user from get_current_user

    Returns:
        Active User object

    Raises:
        HTTPException 403: If user is inactive or locked

    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_active_user)):
            return {"message": "Access granted"}
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "data": None,
                "error": {
                    "code": "USER_INACTIVE",
                    "message": "User account is inactive or locked",
                    "details": {},
                },
            },
        )

    return current_user


def require_permission(permission: str):
    """
    Dependency factory to require specific permission.

    Args:
        permission: Permission code (e.g., "student:create")

    Returns:
        FastAPI dependency function

    Raises:
        HTTPException 403: If user doesn't have permission

    Usage:
        @router.post("/students", dependencies=[Depends(require_permission("student:create"))])
        async def create_student(...):
            ...
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": f"Permission '{permission}' required",
                        "details": {"required_permission": permission},
                    },
                },
            )
        return current_user

    return permission_checker


def require_role(role: str):
    """
    Dependency factory to require specific role.

    Args:
        role: Role code (e.g., "teacher", "admin")

    Returns:
        FastAPI dependency function

    Raises:
        HTTPException 403: If user doesn't have role

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role("admin"))])
        async def admin_only(...):
            ...
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if not current_user.has_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": f"Role '{role}' required",
                        "details": {"required_role": role},
                    },
                },
            )
        return current_user

    return role_checker


def require_any_role(*roles: str):
    """
    Dependency factory to require any of the specified roles.

    Args:
        *roles: Role codes (e.g., "teacher", "admin")

    Returns:
        FastAPI dependency function

    Raises:
        HTTPException 403: If user doesn't have any of the roles

    Usage:
        @router.get("/staff", dependencies=[Depends(require_any_role("teacher", "admin"))])
        async def staff_only(...):
            ...
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        if not any(current_user.has_role(role) for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": f"One of roles {roles} required",
                        "details": {"required_roles": list(roles)},
                    },
                },
            )
        return current_user

    return role_checker


def require_all_permissions(*permissions: str):
    """
    Dependency factory to require all specified permissions.

    Args:
        *permissions: Permission codes (e.g., "student:read", "student:update")

    Returns:
        FastAPI dependency function

    Raises:
        HTTPException 403: If user doesn't have all permissions

    Usage:
        @router.patch("/students/{id}",
                     dependencies=[Depends(require_all_permissions("student:read", "student:update"))])
        async def update_student(...):
            ...
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        missing_permissions = [
            perm for perm in permissions
            if not current_user.has_permission(perm)
        ]

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "success": False,
                    "data": None,
                    "error": {
                        "code": "INSUFFICIENT_PERMISSIONS",
                        "message": f"Missing permissions: {', '.join(missing_permissions)}",
                        "details": {
                            "required_permissions": list(permissions),
                            "missing_permissions": missing_permissions,
                        },
                    },
                },
            )
        return current_user

    return permission_checker


# Helper to get optional user (doesn't fail if no token)
async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.

    Useful for endpoints that work with or without authentication.

    Args:
        credentials: Optional HTTP Bearer token
        db: Database session

    Returns:
        User object or None

    Usage:
        @router.get("/public-or-private")
        async def mixed_endpoint(user: Optional[User] = Depends(get_optional_user)):
            if user:
                return {"message": "Authenticated", "user": user.email}
            return {"message": "Anonymous"}
    """
    if not credentials:
        return None

    try:
        token = credentials.credentials
        user_info = await extract_user_from_token(token)
        user_id = user_info["user_id"]

        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user._token_info = user_info

        return user
    except Exception:
        return None
