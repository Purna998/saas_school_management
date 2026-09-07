"""Nepal School Management System - Report Models"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, Enum as SQLEnum
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
    report_type = Column(SQLEnum(ReportType), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    academic_year_bs = Column(String(10), nullable=True)
    grade = Column(Integer, nullable=True)
    section = Column(String(10), nullable=True)
    generated_by = Column(UUID(as_uuid=True), nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    file_url = Column(String(500), nullable=True)
    file_format = Column(SQLEnum(ReportFormat), default=ReportFormat.CSV)
    status = Column(SQLEnum(ReportStatus), default=ReportStatus.GENERATING, index=True)
    parameters = Column(JSONB, default={})
    error_message = Column(Text, nullable=True)
