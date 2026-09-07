"""
Nepal School Management System - Attendance Models
Daily attendance tracking with Bikram Sambat date support
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    Enum,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class AttendanceStatus(str, enum.Enum):
    """Attendance status options"""
    present = "present"
    absent = "absent"
    late = "late"
    leave = "leave"
    holiday = "holiday"


class Attendance(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    Daily attendance record for a student.

    Tracks presence/absence per student per day with Nepal-specific
    Bikram Sambat date alongside the Gregorian (AD) date.
    Supports period-based attendance for Higher Secondary (Grade 11-12).
    """

    __tablename__ = "attendances"

    # Student reference
    student_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="FK to student (validated at service level across microservices)",
    )

    # Class information (denormalized for fast queries)
    grade = Column(
        String(10),
        nullable=False,
        comment="Grade level (e.g., '1', '2', ..., '12')",
    )
    section = Column(
        String(10),
        nullable=False,
        comment="Section (e.g., 'A', 'B', 'C')",
    )

    # Date fields - Nepal Bikram Sambat + Gregorian
    date_bs = Column(
        String(10),
        nullable=False,
        comment="Bikram Sambat date (YYYY-MM-DD format, e.g., 2081-03-15)",
    )
    date_ad = Column(
        Date,
        nullable=False,
        index=True,
        comment="Gregorian (AD) date for indexing and sorting",
    )

    # Attendance status
    status = Column(
        Enum(AttendanceStatus, name="attendance_status_enum"),
        nullable=False,
        default=AttendanceStatus.present,
        comment="Attendance status: present, absent, late, leave, holiday",
    )

    # Who marked the attendance
    marked_by = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="User ID of the teacher/admin who marked attendance",
    )

    # Optional remarks
    remarks = Column(
        Text,
        nullable=True,
        comment="Optional remarks (e.g., reason for absence, late arrival time)",
    )

    # Period number for Higher Secondary (Grade 11-12) period-based attendance
    period_number = Column(
        Integer,
        nullable=True,
        comment="Period number (1-8) for HS period-based attendance; NULL for class-level",
    )

    __table_args__ = (
        # Ensure one attendance record per student per date per period
        UniqueConstraint(
            "school_id",
            "student_id",
            "date_ad",
            "period_number",
            name="uq_attendance_student_date_period",
        ),
        # Composite indexes for common queries
        Index(
            "idx_attendance_school_date_grade_section",
            "school_id",
            "date_ad",
            "grade",
            "section",
        ),
        Index(
            "idx_attendance_student_date_range",
            "student_id",
            "date_ad",
        ),
        Index(
            "idx_attendance_school_date_bs",
            "school_id",
            "date_bs",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Attendance(student_id={self.student_id}, "
            f"date_bs={self.date_bs}, status={self.status})>"
        )
