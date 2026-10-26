"""Nepal School Management System - Report Models"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Text,
    Enum as SQLEnum,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum
from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class ReportType(str, enum.Enum):
    EMIS_ANNUAL = "emis_annual"
    ENROLLMENT = "enrollment"
    DROPOUT = "dropout"
    ATTENDANCE_MONTHLY = "attendance_monthly"
    EXAM_RESULT = "exam_result"
    FEE_COLLECTION = "fee_collection"
    STAFF_SUMMARY = "staff_summary"
    STUDENT_LIST = "student_list"
    TRANSFER_CERTIFICATE = "transfer_certificate"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"


class ReportStatus(str, enum.Enum):
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


class Report(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "reports"
    report_type = Column(String(40), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    academic_year_bs = Column(String(10), nullable=True)
    grade = Column(Integer, nullable=True)
    section = Column(String(10), nullable=True)
    generated_by = Column(UUID(as_uuid=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    file_url = Column(String(500), nullable=True)
    file_format = Column(SQLEnum(ReportFormat), default=ReportFormat.CSV)
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.GENERATING, index=True)
    parameters = Column(JSONB, default=dict)
    error_message = Column(Text, nullable=True)
    request_id = Column(UUID(as_uuid=True))
    request_hash = Column(String(64))
    snapshot_version = Column(Integer, nullable=False, default=2)
    row_count = Column(Integer, nullable=False, default=0)
    columns = Column(JSONB, nullable=False, default=list)
    summary = Column(JSONB, nullable=False, default=list)
    school_snapshot = Column(JSONB, nullable=False, default=dict)
    notes = Column(JSONB, nullable=False, default=list)
    content_hash = Column(String(64))
    generated_by_name = Column(String(200))
    archived_at = Column(DateTime(timezone=True))
    archive_reason = Column(String(1000))
    __table_args__ = (
        Index("uq_report_request", "school_id", "request_id", unique=True),
        Index("ix_report_history", "school_id", "report_type", "created_at"),
    )


class ReportRow(Base, BaseModel, TenantMixin):
    __tablename__ = "report_rows"
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    ordinal = Column(Integer, nullable=False)
    values = Column(JSONB, nullable=False)
    __table_args__ = (Index("uq_report_row", "report_id", "ordinal", unique=True),)


class ReportEvent(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "report_events"
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="RESTRICT"),
        nullable=False,
    )
    request_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(30), nullable=False)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    actor_name = Column(String(200))
    notes = Column(String(1000))
    __table_args__ = (
        Index("uq_report_event_request", "school_id", "request_id", unique=True),
        Index("ix_report_activity", "school_id", "report_id", "created_at"),
    )
