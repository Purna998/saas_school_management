"""
Nepal School Management System - Staff Schemas
Pydantic models for staff endpoints
"""

from typing import Optional, List
from uuid import UUID
from datetime import date, datetime, time
from decimal import Decimal
from pydantic import BaseModel, EmailStr, Field


# ============ Staff Schemas ============

class StaffCreate(BaseModel):
    """Create staff schema"""

    user_id: Optional[UUID] = Field(None, description="Linked auth user ID")
    employee_id: Optional[str] = Field(None, max_length=30, description="Employee ID")
    full_name_en: str = Field(..., min_length=2, max_length=200, description="Full name in English")
    full_name_np: Optional[str] = Field(None, max_length=200, description="Full name in Nepali")
    gender: str = Field(..., description="Gender: male, female, other")
    date_of_birth_ad: Optional[date] = Field(None, description="Date of birth (AD)")
    date_of_birth_bs: Optional[str] = Field(None, description="Date of birth (BS: YYYY-MM-DD)")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    email: Optional[EmailStr] = Field(None, description="Email address")
    address: Optional[str] = Field(None, description="Address")
    photo_url: Optional[str] = Field(None, description="Photo URL")
    staff_type: str = Field(..., description="Staff type: teaching, non_teaching, administrative")
    designation: Optional[str] = Field(None, max_length=100, description="Designation/title")
    department: Optional[str] = Field(None, max_length=100, description="Department")
    qualification: Optional[str] = Field(None, max_length=255, description="Highest qualification")
    tsc_number: Optional[str] = Field(None, description="TSC number (format: TSC-XXXXX)")
    joined_date_ad: Optional[date] = Field(None, description="Joining date (AD)")
    joined_date_bs: Optional[str] = Field(None, description="Joining date (BS: YYYY-MM-DD)")
    salary: Optional[Decimal] = Field(None, ge=0, description="Monthly salary in NPR")

    class Config:
        json_schema_extra = {
            "example": {
                "full_name_en": "Ram Bahadur Thapa",
                "full_name_np": "राम बहादुर थापा",
                "gender": "male",
                "date_of_birth_ad": "1985-03-15",
                "date_of_birth_bs": "2041-11-30",
                "phone": "+977-9841234567",
                "email": "ram.thapa@school.edu.np",
                "staff_type": "teaching",
                "designation": "Senior Teacher",
                "department": "Science",
                "qualification": "M.Ed.",
                "tsc_number": "TSC-12345",
                "joined_date_ad": "2010-04-01",
                "salary": 45000.00,
            }
        }


class StaffUpdate(BaseModel):
    """Update staff schema"""

    full_name_en: Optional[str] = Field(None, min_length=2, max_length=200)
    full_name_np: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    designation: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=100)
    qualification: Optional[str] = Field(None, max_length=255)
    tsc_number: Optional[str] = None
    status: Optional[str] = Field(None, description="Status: active, on_leave, resigned, retired, terminated")
    salary: Optional[Decimal] = Field(None, ge=0)
    staff_type: Optional[str] = None


class StaffResponse(BaseModel):
    """Staff response schema"""

    id: UUID
    school_id: UUID
    user_id: Optional[UUID] = None
    employee_id: Optional[str] = None
    full_name_en: str
    full_name_np: Optional[str] = None
    gender: str
    date_of_birth_ad: Optional[date] = None
    date_of_birth_bs: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    photo_url: Optional[str] = None
    staff_type: str
    designation: Optional[str] = None
    department: Optional[str] = None
    qualification: Optional[str] = None
    tsc_number: Optional[str] = None
    joined_date_ad: Optional[date] = None
    joined_date_bs: Optional[str] = None
    status: str
    salary: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaffListResponse(BaseModel):
    """Staff list with pagination"""

    staff: List[StaffResponse]
    total: int
    page: int
    limit: int


# ============ Leave Schemas ============

class LeaveRequestCreate(BaseModel):
    """Leave request creation schema"""

    staff_id: UUID = Field(..., description="Staff member ID")
    leave_type: str = Field(..., description="Leave type: casual, sick, maternity, paternity, study, unpaid")
    start_date_ad: date = Field(..., description="Leave start date (AD)")
    end_date_ad: date = Field(..., description="Leave end date (AD)")
    reason: Optional[str] = Field(None, description="Reason for leave")

    class Config:
        json_schema_extra = {
            "example": {
                "staff_id": "550e8400-e29b-41d4-a716-446655440000",
                "leave_type": "casual",
                "start_date_ad": "2081-05-15",
                "end_date_ad": "2081-05-17",
                "reason": "Family function",
            }
        }


class LeaveResponse(BaseModel):
    """Leave response schema"""

    id: UUID
    school_id: UUID
    staff_id: UUID
    leave_type: str
    start_date_ad: date
    end_date_ad: date
    days: int
    reason: Optional[str] = None
    status: str
    approved_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ Attendance Schemas ============

class StaffAttendanceEntry(BaseModel):
    """Single staff attendance entry for batch marking"""

    staff_id: UUID = Field(..., description="Staff member ID")
    status: str = Field(..., description="Attendance status: present, absent, late, half_day, leave")
    check_in_time: Optional[time] = Field(None, description="Check-in time")
    check_out_time: Optional[time] = Field(None, description="Check-out time")


class StaffAttendanceMarkRequest(BaseModel):
    """Batch attendance marking request"""

    date_ad: date = Field(..., description="Attendance date (AD)")
    date_bs: Optional[str] = Field(None, description="Attendance date (BS: YYYY-MM-DD)")
    attendances: List[StaffAttendanceEntry] = Field(..., description="List of staff attendance entries")

    class Config:
        json_schema_extra = {
            "example": {
                "date_ad": "2024-01-15",
                "date_bs": "2080-10-01",
                "attendances": [
                    {
                        "staff_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "present",
                        "check_in_time": "09:00:00",
                        "check_out_time": "16:00:00",
                    },
                    {
                        "staff_id": "550e8400-e29b-41d4-a716-446655440001",
                        "status": "absent",
                    },
                ],
            }
        }


class StaffAttendanceResponse(BaseModel):
    """Staff attendance response schema"""

    id: UUID
    school_id: UUID
    staff_id: UUID
    date_ad: date
    date_bs: Optional[str] = None
    status: str
    check_in_time: Optional[time] = None
    check_out_time: Optional[time] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AttendanceSummary(BaseModel):
    """Staff attendance summary"""

    staff_id: UUID
    staff_name: str
    total_days: int
    present: int
    absent: int
    late: int
    half_day: int
    on_leave: int
    attendance_percentage: float
