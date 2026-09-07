"""
Nepal School Management System - MFA Model
Multi-Factor Authentication (TOTP) secrets
"""

from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin


class MFASecret(Base, BaseModel, TimestampMixin):
    """
    MFA/TOTP secret storage.

    Stores encrypted TOTP secret for each user who enables MFA.
    """

    __tablename__ = "mfa_secrets"

    # User reference
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
        comment="User ID"
    )

    # TOTP secret
    secret = Column(
        String(255),
        nullable=False,
        comment="Encrypted TOTP secret (base32 encoded)"
    )

    # Backup codes
    backup_codes = Column(
        String(1000),
        nullable=True,
        comment="Encrypted backup codes (comma-separated)"
    )

    # Status
    is_verified = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="TOTP setup verified flag"
    )

    # Relationships
    user = relationship("User", back_populates="mfa_secret")

    def __repr__(self):
        return f"<MFASecret(user_id={self.user_id}, verified={self.is_verified})>"
