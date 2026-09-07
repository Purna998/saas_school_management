"""
Nepal School Management System - Communication Models
SMS, Email, and Push Notification message tracking
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class MessageChannel(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"


class MessageStatus(str, enum.Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"


class MessageType(str, enum.Enum):
    ATTENDANCE = "attendance"
    FEE_REMINDER = "fee_reminder"
    EXAM_RESULT = "exam_result"
    ANNOUNCEMENT = "announcement"
    EMERGENCY = "emergency"
    CUSTOM = "custom"


class SMSProvider(str, enum.Enum):
    SPARROW = "sparrow"
    AAKASH = "aakash"


class Message(Base, BaseModel, TimestampMixin, TenantMixin):
    """Message log for all communication channels"""

    __tablename__ = "messages"

    channel = Column(SQLEnum(MessageChannel), nullable=False)
    message_type = Column(SQLEnum(MessageType), default=MessageType.CUSTOM, nullable=False)
    status = Column(SQLEnum(MessageStatus), default=MessageStatus.QUEUED, nullable=False, index=True)

    # Recipient
    recipient_id = Column(UUID(as_uuid=True), nullable=True, comment="User/Student/Guardian ID")
    recipient_phone = Column(String(20), nullable=True, comment="Phone number (for SMS)")
    recipient_email = Column(String(255), nullable=True, comment="Email address")
    recipient_name = Column(String(200), nullable=True)

    # Content
    subject = Column(String(255), nullable=True, comment="Email subject or notification title")
    body = Column(Text, nullable=False, comment="Message body")
    template_id = Column(String(50), nullable=True, comment="Template identifier")
    template_data = Column(JSONB, nullable=True, comment="Template variables")

    # Delivery tracking
    provider = Column(String(20), nullable=True, comment="SMS/Email provider used")
    provider_message_id = Column(String(100), nullable=True, comment="External message ID")
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Metadata
    sent_by = Column(UUID(as_uuid=True), nullable=True, comment="User who triggered the message")
    cost = Column(String(10), nullable=True, comment="Cost in NPR")

    def __repr__(self):
        return f"<Message(id={self.id}, channel={self.channel}, status={self.status})>"


class SMSTemplate(Base, BaseModel, TimestampMixin, TenantMixin):
    """SMS templates for common messages"""

    __tablename__ = "sms_templates"

    code = Column(String(50), nullable=False, index=True, comment="Template code")
    name_en = Column(String(100), nullable=False)
    name_np = Column(String(100), nullable=True)
    body_en = Column(Text, nullable=False, comment="Template body with {variables}")
    body_np = Column(Text, nullable=True, comment="Nepali template body")
    message_type = Column(SQLEnum(MessageType), nullable=False)
    variables = Column(JSONB, nullable=True, comment="Required template variables")
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<SMSTemplate(code={self.code}, name={self.name_en})>"
