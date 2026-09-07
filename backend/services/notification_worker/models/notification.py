"""Nepal School Management System - Notification Models"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum
from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class EventType(str, enum.Enum):
    ATTENDANCE_MARKED = "attendance_marked"
    FEE_DUE = "fee_due"
    EXAM_PUBLISHED = "exam_published"
    ANNOUNCEMENT = "announcement"
    LEAVE_APPROVED = "leave_approved"
    STUDENT_ENROLLED = "student_enrolled"


class EventStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class NotificationChannel(str, enum.Enum):
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    NONE = "none"


class NotificationEvent(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "notification_events"
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    payload = Column(JSONB, nullable=False, default={})
    status = Column(SQLEnum(EventStatus), default=EventStatus.PENDING, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)


class NotificationPreference(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "notification_preferences"
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    event_type = Column(SQLEnum(EventType), nullable=False)
    channel = Column(SQLEnum(NotificationChannel), default=NotificationChannel.SMS)
    is_enabled = Column(Boolean, default=True)
