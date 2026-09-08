"""
Nepal School Management System - User Model
User authentication and profile data
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Table, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum
import uuid

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class UserStatus(str, enum.Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    LOCKED = "locked"  # Locked due to failed login attempts


# Association table for many-to-many User <-> Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
    Column("granted_at", DateTime(timezone=True), server_default="now()", nullable=False),
    Column("granted_by", UUID(as_uuid=True), nullable=True),
)


class User(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    User model for authentication and authorization.

    Supports multiple roles per user with school-level isolation.
    """

    __tablename__ = "users"

    # Authentication
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Email address - used for login"
    )
    password_hash = Column(
        String(255),
        nullable=False,
        comment="Bcrypt password hash"
    )

    # Profile
    full_name_en = Column(
        String(200),
        nullable=False,
        comment="Full name in English"
    )
    full_name_np = Column(
        String(200),
        nullable=True,
        comment="Full name in Nepali (Devanagari)"
    )
    phone = Column(
        String(20),
        nullable=True,
        comment="Contact phone number (Nepal format: +977-9841234567)"
    )
    photo_url = Column(
        String(500),
        nullable=True,
        comment="Profile photo URL (S3/CloudFront)"
    )

    # Status & Security
    status = Column(
        SQLEnum(UserStatus),
        default=UserStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="User account status"
    )
    email_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Email verification status"
    )
    email_verified_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Email verification timestamp"
    )

    # MFA
    mfa_enabled = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="MFA/TOTP enabled flag"
    )
    mfa_enabled_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="MFA activation timestamp"
    )

    # Login tracking
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful login timestamp"
    )
    last_login_ip = Column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="Last login IP address"
    )
    failed_login_attempts = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Consecutive failed login attempts counter"
    )
    locked_until = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Account lockout expiry timestamp"
    )

    # Password management
    password_changed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last password change timestamp"
    )
    password_reset_token = Column(
        String(255),
        nullable=True,
        comment="Password reset token (hashed)"
    )
    password_reset_expires = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Password reset token expiry"
    )

    # Relationships
    roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin"
    )
    mfa_secret = relationship(
        "MFASecret",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    sessions = relationship(
        "UserSession",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    login_attempts = relationship(
        "LoginAttempt",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, school_id={self.school_id})>"

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked"""
        if self.status == UserStatus.LOCKED:
            return True
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    @property
    def is_active(self) -> bool:
        """Check if account is active and not locked"""
        return self.status == UserStatus.ACTIVE and not self.is_locked

    @property
    def requires_mfa(self) -> bool:
        """Check if MFA is required (enabled)"""
        return self.mfa_enabled

    def get_permissions(self) -> set[str]:
        """Get all permissions from all roles"""
        permissions = set()
        for role in self.roles:
            permissions.update(role.get_permissions())
        return permissions

    def has_permission(self, permission_code: str) -> bool:
        """Check if user has specific permission"""
        permissions = self.get_permissions()
        return "*:*" in permissions or permission_code in permissions

    def has_role(self, role_code: str) -> bool:
        """Check if user has specific role"""
        return any(role.code == role_code for role in self.roles)


# For backwards compatibility with old code
UserRole = user_roles
