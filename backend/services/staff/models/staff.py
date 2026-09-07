"""
Nepal School Management System - Staff Models
Staff profile, leave management, and attendance tracking
"""

from datetime import datetime, date, time
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Integer, Text,
    ForeignKey, Numeric, Time, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin, SoftDeleteMixin


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class StaffType(str, enum.Enum):
    TEACHING = "teaching"
    NON_TEACHING = "non_teaching"
    ADMINISTRATIVE = "administrative"


class StaffStatus(str, enum.Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    RESIGNED = "resigned"
    RETIRED = "retired"
    TERMINATED = "terminated"


class LeaveType(str, enum.Enum):
    CASUAL = "casual"
    SICK = "sick"
    MATERNITY = "maternity"
    PATERNITY = "paternity"
    STUDY = "study"
    UNPAID = "unpaid"


class LeaveStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    HALF_DAY = "half_day"
    LEAVE = "leave"


class Staff(Base, BaseModel, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """
    Staff model for teaching and non-teaching personnel.

    Supports Nepal-specific fields including TSC number,
    BS/AD dates, and bilingual names.
    """

    __tablename__ = "staff"

    # Link to auth user
    user_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="Links to auth service user account"
    )

    # Identification
    employee_id = Column(
        String(30),
        nullable=True,
        index=True,
        comment="School-assigned employee ID"
    )

    # Personal info
    full_name_en = Column(String(200), nullable=False, comment="Full name in English")
    full_name_np = Column(String(200), nullable=True, comment="Full name in Nepali")
    gender = Column(SQLEnum(Gender), nullable=False, comment="Gender")
    date_of_birth_ad = Column(Date, nullable=True, comment="Date of birth (AD)")
    date_of_birth_bs = Column(String(12), nullable=True, comment="Date of birth (BS: YYYY-MM-DD)")

    # Contact
    phone = Column(String(20), nullable=True, comment="Phone number")
    email = Column(String(255), nullable=True, comment="Email address")
    address = Column(Text, nullable=True, comment="Address")
    photo_url = Column(String(500), nullable=True, comment="Staff photo URL")

    # Employment details
    staff_type = Column(
        SQLEnum(StaffType),
        nullable=False,
        index=True,
        comment="Staff type: teaching, non_teaching, administrative"
    )
    designation = Column(String(100), nullable=True, comment="Job designation/title")
    department = Column(String(100), nullable=True, comment="Department")
    qualification = Column(String(255), nullable=True, comment="Highest qualification")

    # Nepal-specific: Teacher Service Commission
    tsc_number = Column(
        String(20),
        nullable=True,
        index=True,
        comment="TSC (Teacher Service Commission) number: TSC-XXXXX"
    )

    # Dates
    joined_date_ad = Column(Date, nullable=True, comment="Joining date (AD)")
    joined_date_bs = Column(String(12), nullable=True, comment="Joining date (BS: YYYY-MM-DD)")

    # Status and salary
    status = Column(
        SQLEnum(StaffStatus),
        default=StaffStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="Staff employment status"
    )
    salary = Column(
        Numeric(12, 2),
        nullable=True,
        comment="Monthly salary in NPR"
    )

    # Relationships
    leaves = relationship("StaffLeave", back_populates="staff", cascade="all, delete-orphan")
    attendances = relationship("StaffAttendance", back_populates="staff", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Staff(id={self.id}, name={self.full_name_en}, type={self.staff_type})>"

    @property
    def is_active(self) -> bool:
        return self.status == StaffStatus.ACTIVE

    @property
    def is_teaching(self) -> bool:
        return self.staff_type == StaffType.TEACHING


class StaffLeave(Base, BaseModel, TimestampMixin, TenantMixin):
    """Staff leave request and tracking"""

    __tablename__ = "staff_leaves"

    staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_type = Column(
        SQLEnum(LeaveType),
        nullable=False,
        comment="Type of leave"
    )
    start_date_ad = Column(Date, nullable=False, comment="Leave start date (AD)")
    end_date_ad = Column(Date, nullable=False, comment="Leave end date (AD)")
    days = Column(Integer, nullable=False, comment="Total leave days")
    reason = Column(Text, nullable=True, comment="Reason for leave")
    status = Column(
        SQLEnum(LeaveStatus),
        default=LeaveStatus.PENDING,
        nullable=False,
        index=True,
        comment="Leave approval status"
    )
    approved_by = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="User ID who approved/rejected the leave"
    )

    # Relationship
    staff = relationship("Staff", back_populates="leaves")

    def __repr__(self):
        return f"<StaffLeave(staff={self.staff_id}, type={self.leave_type}, status={self.status})>"


class StaffAttendance(Base, BaseModel, TimestampMixin, TenantMixin):
    """Daily staff attendance record"""

    __tablename__ = "staff_attendances"

    staff_id = Column(
        UUID(as_uuid=True),
        ForeignKey("staff.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    date_ad = Column(Date, nullable=False, comment="Attendance date (AD)")
    date_bs = Column(String(12), nullable=True, comment="Attendance date (BS: YYYY-MM-DD)")
    status = Column(
        SQLEnum(AttendanceStatus),
        nullable=False,
        comment="Attendance status"
    )
    check_in_time = Column(Time, nullable=True, comment="Check-in time")
    check_out_time = Column(Time, nullable=True, comment="Check-out time")

    # Relationship
    staff = relationship("Staff", back_populates="attendances")

    def __repr__(self):
        return f"<StaffAttendance(staff={self.staff_id}, date={self.date_ad}, status={self.status})>"
