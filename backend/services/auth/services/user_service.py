"""
Nepal School Management System - User Service
User management business logic: CRUD, profile, password operations
"""

import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from shared.utils.exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
    InvalidCredentialsError,
)
from services.auth.models.user import User, UserStatus
from services.auth.models.role import Role
from services.auth.utils.password import (
    hash_password,
    verify_password,
    validate_password_change,
)
from services.auth.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    """User management service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(self, user_data: UserCreate) -> User:
        """
        Create a new user.

        Args:
            user_data: User creation data

        Returns:
            Created user object

        Raises:
            DuplicateRecordError: If email already exists
        """
        # Check if email already exists
        result = await self.db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise DuplicateRecordError("User", "email", user_data.email)

        # Hash password
        password_hash = hash_password(user_data.password)

        # Create user
        user = User(
            id=uuid.uuid4(),
            email=user_data.email,
            password_hash=password_hash,
            full_name_en=user_data.full_name_en,
            full_name_np=user_data.full_name_np,
            phone=user_data.phone,
            school_id=user_data.school_id,
            status=UserStatus.ACTIVE,
            email_verified=False,
            mfa_enabled=False,
        )

        self.db.add(user)

        # Assign roles if provided
        if user_data.role_ids:
            result = await self.db.execute(
                select(Role).where(Role.id.in_(user_data.role_ids))
            )
            roles = result.scalars().all()
            user.roles.extend(roles)

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User created: {user.email}")

        return user

    async def get_user_by_id(self, user_id: uuid.UUID) -> User:
        """
        Get user by ID.

        Args:
            user_id: User UUID

        Returns:
            User object

        Raises:
            RecordNotFoundError: If user not found
        """
        result = await self.db.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise RecordNotFoundError("User", str(user_id))

        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User object or None
        """
        result = await self.db.execute(
            select(User)
            .where(User.email == email)
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def update_user(
        self,
        user_id: uuid.UUID,
        user_data: UserUpdate
    ) -> User:
        """
        Update user profile.

        Args:
            user_id: User UUID
            user_data: User update data

        Returns:
            Updated user object

        Raises:
            RecordNotFoundError: If user not found
        """
        user = await self.get_user_by_id(user_id)

        # Update fields
        if user_data.full_name_en is not None:
            user.full_name_en = user_data.full_name_en

        if user_data.full_name_np is not None:
            user.full_name_np = user_data.full_name_np

        if user_data.phone is not None:
            user.phone = user_data.phone

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"User updated: {user.email}")

        return user

    async def change_password(
        self,
        user_id: uuid.UUID,
        old_password: str,
        new_password: str
    ):
        """
        Change user password.

        Args:
            user_id: User UUID
            old_password: Current password
            new_password: New password

        Raises:
            RecordNotFoundError: If user not found
            InvalidCredentialsError: If old password is incorrect
            ValueError: If new password is invalid
        """
        user = await self.get_user_by_id(user_id)

        # Validate password change
        is_valid, error = validate_password_change(
            old_password,
            new_password,
            user.password_hash
        )

        if not is_valid:
            if "current password" in error.lower():
                raise InvalidCredentialsError(error)
            raise ValueError(error)

        # Update password
        user.password_hash = hash_password(new_password)
        user.password_changed_at = datetime.utcnow()

        await self.db.commit()

        logger.info(f"Password changed for user: {user.email}")

    async def update_photo(
        self,
        user_id: uuid.UUID,
        photo_url: str
    ) -> User:
        """
        Update user profile photo.

        Args:
            user_id: User UUID
            photo_url: Photo URL (S3/CloudFront)

        Returns:
            Updated user object

        Raises:
            RecordNotFoundError: If user not found
        """
        user = await self.get_user_by_id(user_id)
        user.photo_url = photo_url

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"Profile photo updated for user: {user.email}")

        return user

    async def list_users(
        self,
        school_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        role_code: Optional[str] = None,
        status: Optional[UserStatus] = None
    ) -> tuple[List[User], int]:
        """
        List users with pagination and filters.

        Args:
            school_id: School/Tenant UUID
            page: Page number (1-indexed)
            limit: Items per page
            search: Search query (email or name)
            role_code: Filter by role code
            status: Filter by status

        Returns:
            Tuple of (users list, total count)
        """
        # Build query
        query = select(User).where(User.school_id == school_id)

        # Apply filters
        if search:
            search_pattern = f"%{search}%"
            query = query.where(
                (User.email.ilike(search_pattern)) |
                (User.full_name_en.ilike(search_pattern)) |
                (User.full_name_np.ilike(search_pattern))
            )

        if status:
            query = query.where(User.status == status)

        if role_code:
            query = query.join(User.roles).where(Role.code == role_code)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        query = query.options(selectinload(User.roles))

        # Execute query
        result = await self.db.execute(query)
        users = result.scalars().all()

        return users, total

    async def deactivate_user(self, user_id: uuid.UUID):
        """
        Deactivate user account.

        Args:
            user_id: User UUID

        Raises:
            RecordNotFoundError: If user not found
        """
        user = await self.get_user_by_id(user_id)
        user.status = UserStatus.INACTIVE

        await self.db.commit()

        logger.info(f"User deactivated: {user.email}")

    async def activate_user(self, user_id: uuid.UUID):
        """
        Activate user account.

        Args:
            user_id: User UUID

        Raises:
            RecordNotFoundError: If user not found
        """
        user = await self.get_user_by_id(user_id)
        user.status = UserStatus.ACTIVE

        await self.db.commit()

        logger.info(f"User activated: {user.email}")

    async def verify_email(self, user_id: uuid.UUID):
        """
        Mark user email as verified.

        Args:
            user_id: User UUID

        Raises:
            RecordNotFoundError: If user not found
        """
        user = await self.get_user_by_id(user_id)
        user.email_verified = True
        user.email_verified_at = datetime.utcnow()

        await self.db.commit()

        logger.info(f"Email verified for user: {user.email}")
