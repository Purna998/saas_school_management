"""
Nepal School Management System - Student Schemas
Pydantic models for student endpoints
"""

from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field


class GuardianCreate(BaseModel):
    """Guardian creation schema"""

    relation: str = Field(..., description="Relation to student")
    full_name_en: str = Field(..., min_length=2, description="Full name in English")
    full_name_np: Optional[str] = Field(None, description="Full name in Nepali")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[EmailStr] = Field(None, description="Email")
    occupation: Optional[str] = Field(None, description="Occupation")
    is_primary_contact: bool = Field(default=False, description="Primary contact flag")


class GuardianResponse(BaseModel):
    """Guardian response schema"""

    id: UUID
    relation: str
    full_name_en: str
    full_name_np: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    occupation: Optional[str] = None
    is_primary_contact: bool

    class Config:
        from_attributes = True


class StudentCreate(BaseModel):
    """Create student schema"""

    full_name_en: str = Field(..., min_length=2, max_length=200, description="Full name in English")
    full_name_np: Optional[str] = Field(None, max_length=200, description="Full name in Nepali")
    gender: str = Field(..., description="Gender: male, female, other")
    date_of_birth_ad: date = Field(..., description="Date of birth (AD)")
    date_of_birth_bs: Optional[str] = Field(None, description="Date of birth (BS: YYYY-MM-DD)")

    # Contact
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[EmailStr] = Field(None, description="Email")
    address_permanent: Optional[str] = Field(None, description="Permanent address")
    address_temporary: Optional[str] = Field(None, description="Temporary address")

    # Academic
    current_grade: int = Field(..., ge=1, le=12, description="Grade (1-12)")
    current_section: Optional[str] = Field(None, description="Section (A, B, C)")
    current_faculty: Optional[str] = Field(None, description="Faculty for Grade 11-12")
    admission_date_ad: Optional[date] = Field(None, description="Admission date")
    admission_date_bs: Optional[str] = Field(None, description="Admission date (BS)")

    # Demographics
    caste_ethnicity: Optional[str] = Field(None, description="Caste/ethnicity")
    religion: Optional[str] = Field(None, description="Religion")
    mother_tongue: Optional[str] = Field(None, description="Mother tongue")
    nationality: str = Field(default="Nepali", description="Nationality")
    disability_type: Optional[str] = Field(None, description="Disability type")

    # IDs
    emis_student_id: Optional[str] = Field(None, description="EMIS Student ID")
    admission_number: Optional[str] = Field(None, description="Admission number")
    roll_number: Optional[int] = Field(None, description="Roll number")

    # Previous school
    previous_school_name: Optional[str] = Field(None, description="Previous school name")
    transfer_certificate_number: Optional[str] = Field(None, description="TC number")

    # Guardians
    guardians: List[GuardianCreate] = Field(default_factory=list, description="Guardians")

    class Config:
        json_schema_extra = {
            "example": {
                "full_name_en": "Aarav Sharma",
                "full_name_np": "आरव शर्मा",
                "gender": "male",
                "date_of_birth_ad": "2015-05-15",
                "date_of_birth_bs": "2072-02-01",
                "current_grade": 5,
                "current_section": "A",
                "caste_ethnicity": "brahmin_hill",
                "guardians": [
                    {
                        "relation": "father",
                        "full_name_en": "Ram Sharma",
                        "phone": "+977-9841234567",
                        "is_primary_contact": True,
                    }
                ],
            }
        }


class StudentUpdate(BaseModel):
    """Update student schema"""

    full_name_en: Optional[str] = Field(None, min_length=2, max_length=200)
    full_name_np: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address_permanent: Optional[str] = None
    address_temporary: Optional[str] = None
    current_grade: Optional[int] = Field(None, ge=1, le=12)
    current_section: Optional[str] = None
    current_faculty: Optional[str] = None
    roll_number: Optional[int] = None
    status: Optional[str] = None


class EnrollmentResponse(BaseModel):
    """Enrollment history entry"""

    id: UUID
    academic_year_bs: str
    grade: int
    section: Optional[str] = None
    faculty: Optional[str] = None
    roll_number: Optional[int] = None
    status: str
    enrolled_at: datetime

    class Config:
        from_attributes = True


class StudentResponse(BaseModel):
    """Student response schema"""

    id: UUID
    emis_student_id: Optional[str] = None
    admission_number: Optional[str] = None
    roll_number: Optional[int] = None
    full_name_en: str
    full_name_np: Optional[str] = None
    gender: str
    date_of_birth_ad: date
    date_of_birth_bs: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address_permanent: Optional[str] = None
    address_temporary: Optional[str] = None
    current_grade: Optional[int] = None
    current_section: Optional[str] = None
    current_faculty: Optional[str] = None
    caste_ethnicity: Optional[str] = None
    religion: Optional[str] = None
    mother_tongue: Optional[str] = None
    nationality: Optional[str] = None
    disability_type: Optional[str] = None
    status: str
    photo_url: Optional[str] = None
    school_id: UUID
    guardians: List[GuardianResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StudentListResponse(BaseModel):
    """Student list with pagination"""

    students: List[StudentResponse]
    total: int
    page: int
    limit: int


class BulkImportResponse(BaseModel):
    """Bulk import result"""

    total_rows: int
    imported: int
    failed: int
    errors: List[dict] = []
