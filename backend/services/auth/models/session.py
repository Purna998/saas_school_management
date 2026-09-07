"""
Nepal School Management System - Session & Login Attempt Models
User session tracking and login attempt monitoring
"""

from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin


class SessionStatus(str, enum.Enum):
    """Session status"""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class LoginStatus(str, enum.Enum):
    """Login attempt status"""
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"  # Blocked due to rate limiting
    MFA_REQUIRED = "mfa_required"
    MFA_FAILED = "mfa_failed"


class UserSession(Base, BaseModel, TimestampMixin):
    """
    User session tracking.

    Tracks active JWT refresh tokens and device information.
    Used for session management and security monitoring.
    """

    __tablename__ = "user_sessions"

    # User reference
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User ID"
    )

    # Token tracking
    refresh_token_jti = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="JWT ID (jti) of the refresh token"
    )
    access_token_jti = Column(
        String(255),
        nullable=True,
        comment="JWT ID (jti) of the current access token"
    )

    # Session info
    status = Column(
        SQLEnum(SessionStatus),
        default=SessionStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="Session status"
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Session expiry timestamp"
    )

    # Device & Location info
    ip_address = Column(
        INET,
        nullable=True,
        comment="IP address"
    )
    user_agent = Column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    device_name = Column(
        String(255),
        nullable=True,
        comment="Device name (parsed from user agent)"
    )
    device_type = Column(
        String(50),
        nullable=True,
        comment="Device type: desktop, mobile, tablet, etc."
    )
    browser = Column(
        String(100),
        nullable=True,
        comment="Browser name"
    )
    os = Column(
        String(100),
        nullable=True,
        comment="Operating system"
    )
    location = Column(
        String(255),
        nullable=True,
        comment="Geographic location (city, country)"
    )

    # Tracking
    last_activity_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last activity timestamp"
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Session revocation timestamp"
    )
    revoked_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User ID who revoked the session"
    )

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if session is active and not expired"""
        return (
            self.status == SessionStatus.ACTIVE
            and self.expires_at > datetime.utcnow()
        )

    @property
    def is_expired(self) -> bool:
        """Check if session has expired"""
        return self.expires_at <= datetime.utcnow()

    def revoke(self, revoked_by: UUID | None = None):
        """Revoke the session"""
        self.status = SessionStatus.REVOKED
        self.revoked_at = datetime.utcnow()
        self.revoked_by = revoked_by


class LoginAttempt(Base, BaseModel, TimestampMixin):
    """
    Login attempt tracking for security monitoring and rate limiting.

    Tracks both successful and failed login attempts.
    Used for account lockout and security alerts.
    """

    __tablename__ = "login_attempts"

    # User reference (nullable for failed attempts with invalid email)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="User ID (null if email not found)"
    )

    # Attempt info
    email = Column(
        String(255),
        nullable=False,
        index=True,
        comment="Email used in login attempt"
    )
    status = Column(
        SQLEnum(LoginStatus),
        nullable=False,
        index=True,
        comment="Login attempt status"
    )

    # Device & Location
    ip_address = Column(
        INET,
        nullable=True,
        index=True,
        comment="IP address"
    )
    user_agent = Column(
        Text,
        nullable=True,
        comment="User agent string"
    )
    location = Column(
        String(255),
        nullable=True,
        comment="Geographic location"
    )

    # Failure details
    failure_reason = Column(
        String(255),
        nullable=True,
        comment="Reason for failure (e.g., 'invalid_password', 'account_locked')"
    )

    # MFA
    mfa_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="MFA verification status"
    )

    # Relationships
    user = relationship("User", back_populates="login_attempts")

    def __repr__(self):
        return f"<LoginAttempt(email={self.email}, status={self.status}, ip={self.ip_address})>"
