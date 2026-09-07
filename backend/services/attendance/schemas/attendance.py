"""
Nepal School Management System - Attendance Schemas
Pydantic models for attendance API request/response validation
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AttendanceEntryRequest(BaseModel):
    """Single student attendance entry within a batch request"""

    student_id: UUID = Field(..., description="Student UUID")
    status: str = Field(
        ...,
        description="Attendance status: present, absent, late, leave, holiday",
    )
    remarks: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional remarks for this entry",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"present", "absent", "late", "leave", "holiday"}
        if v.lower() not in allowed:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(allowed))}"
            )
        return v.lower()


class AttendanceMarkRequest(BaseModel):
    """
    Batch attendance marking request.
    Marks attendance for an entire class (grade + section) on a given date.
    """

    date_bs: str = Field(
        ...,
        min_length=10,
        max_length=10,
        description="Bikram Sambat date (YYYY-MM-DD format, e.g., 2081-03-15)",
    )
    date_ad: date = Field(
        ...,
        description="Gregorian (AD) date corresponding to the BS date",
    )
    grade: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Grade level (e.g., '1', '10', '12')",
    )
    section: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Section (e.g., 'A', 'B')",
    )
    period_number: Optional[int] = Field(
        default=None,
        ge=1,
        le=8,
        description="Period number (1-8) for HS period-based attendance",
    )
    entries: list[AttendanceEntryRequest] = Field(
        ...,
        min_length=1,
        description="List of attendance entries for each student",
    )

    @field_validator("date_bs")
    @classmethod
    def validate_date_bs(cls, v: str) -> str:
        """Validate BS date format YYYY-MM-DD"""
        parts = v.split("-")
        if len(parts) != 3:
            raise ValueError("BS date must be in YYYY-MM-DD format")
        year, month, day = parts
        if not (year.isdigit() and month.isdigit() and day.isdigit()):
            raise ValueError("BS date components must be numeric")
        if not (2000 <= int(year) <= 2100):
            raise ValueError("BS year must be between 2000 and 2100")
        if not (1 <= int(month) <= 12):
            raise ValueError("BS month must be between 1 and 12")
        if not (1 <= int(day) <= 32):
            raise ValueError("BS day must be between 1 and 32")
        return v


class AttendanceUpdateRequest(BaseModel):
    """Request to update a single attendance record"""

    status: Optional[str] = Field(
        default=None,
        description="Updated attendance status",
    )
    remarks: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Updated remarks",
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"present", "absent", "late", "leave", "holiday"}
        if v.lower() not in allowed:
            raise ValueError(
                f"Invalid status '{v}'. Must be one of: {', '.join(sorted(allowed))}"
            )
        return v.lower()


class AttendanceResponse(BaseModel):
    """Single attendance record response"""

    id: UUID
    school_id: UUID
    student_id: UUID
    grade: str
    section: str
    date_bs: str
    date_ad: date
    status: str
    marked_by: UUID
    remarks: Optional[str] = None
    period_number: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AttendanceListResponse(BaseModel):
    """List of attendance records for a class on a given date"""

    date_bs: str
    date_ad: date
    grade: str
    section: str
    period_number: Optional[int] = None
    total_students: int
    records: list[AttendanceResponse]


class AttendanceSummaryResponse(BaseModel):
    """Summary statistics for attendance"""

    date_bs: Optional[str] = None
    date_ad: Optional[date] = None
    grade: str
    section: str
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    leave_count: int = 0
    holiday_count: int = 0
    total: int = 0

    @property
    def attendance_percentage(self) -> float:
        """Calculate attendance percentage (present + late counted as attended)"""
        if self.total == 0:
            return 0.0
        attended = self.present_count + self.late_count
        return round((attended / self.total) * 100, 2)


class DailySummary(BaseModel):
    """Daily summary within a monthly report"""

    date_bs: str
    date_ad: date
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    leave_count: int = 0
    holiday_count: int = 0
    total: int = 0


class MonthlyReportResponse(BaseModel):
    """Monthly attendance report for a class"""

    school_id: UUID
    grade: str
    section: str
    year_bs: int
    month_bs: int
    total_school_days: int = 0
    average_attendance_percentage: float = 0.0
    daily_summaries: list[DailySummary] = []


class StudentAttendanceRecord(BaseModel):
    """Attendance record for student history view"""

    id: UUID
    date_bs: str
    date_ad: date
    status: str
    remarks: Optional[str] = None
    period_number: Optional[int] = None

    class Config:
        from_attributes = True


class StudentAttendanceResponse(BaseModel):
    """Student attendance history response"""

    student_id: UUID
    start_date: date
    end_date: date
    total_days: int = 0
    present_count: int = 0
    absent_count: int = 0
    late_count: int = 0
    leave_count: int = 0
    attendance_percentage: float = 0.0
    records: list[StudentAttendanceRecord] = []
