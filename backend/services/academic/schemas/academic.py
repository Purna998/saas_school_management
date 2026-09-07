"""
Nepal School Management System - Academic Schemas
Pydantic models for academic management endpoints
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime, time
from pydantic import BaseModel, Field


class GradeCreate(BaseModel):
    grade_number: int = Field(..., ge=1, le=12)
    name_en: str = Field(..., min_length=1)
    name_np: Optional[str] = None
    academic_year_bs: Optional[str] = None


class GradeResponse(BaseModel):
    id: UUID
    grade_number: int
    name_en: str
    name_np: Optional[str] = None
    is_active: bool
    is_hs: bool
    academic_year_bs: Optional[str] = None
    sections: List["SectionResponse"] = []

    class Config:
        from_attributes = True


class SectionCreate(BaseModel):
    grade_id: UUID
    name: str = Field(..., max_length=10)
    capacity: int = Field(default=40, ge=1, le=100)
    class_teacher_id: Optional[UUID] = None


class SectionResponse(BaseModel):
    id: UUID
    grade_id: UUID
    name: str
    capacity: int
    class_teacher_id: Optional[UUID] = None
    is_active: bool

    class Config:
        from_attributes = True


class SubjectCreate(BaseModel):
    grade_id: UUID
    code: str = Field(..., max_length=20)
    name_en: str = Field(..., min_length=1)
    name_np: Optional[str] = None
    subject_type: str = Field(default="compulsory")
    full_marks: int = Field(default=100, ge=1)
    pass_marks: int = Field(default=40, ge=1)
    credit_hours: int = Field(default=4, ge=1)
    teacher_id: Optional[UUID] = None
    faculty_id: Optional[UUID] = None


class SubjectResponse(BaseModel):
    id: UUID
    grade_id: UUID
    code: str
    name_en: str
    name_np: Optional[str] = None
    subject_type: str
    full_marks: int
    pass_marks: int
    credit_hours: int
    teacher_id: Optional[UUID] = None
    faculty_id: Optional[UUID] = None
    is_active: bool

    class Config:
        from_attributes = True


class TimetableEntryCreate(BaseModel):
    grade_id: UUID
    section_id: UUID
    subject_id: UUID
    teacher_id: Optional[UUID] = None
    day_of_week: str
    period_number: int = Field(..., ge=1, le=8)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None


class TimetableEntryResponse(BaseModel):
    id: UUID
    grade_id: UUID
    section_id: UUID
    subject_id: UUID
    teacher_id: Optional[UUID] = None
    day_of_week: str
    period_number: int
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    room: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True


class TimetableResponse(BaseModel):
    """Full timetable for a section"""
    grade_id: UUID
    section_id: UUID
    academic_year_bs: Optional[str] = None
    entries: List[TimetableEntryResponse]


# Higher Secondary schemas

class HSFacultyCreate(BaseModel):
    name_en: str = Field(..., min_length=1)
    name_np: Optional[str] = None
    code: str = Field(..., max_length=20)
    description: Optional[str] = None
    max_students: int = Field(default=60, ge=1)


class HSFacultyResponse(BaseModel):
    id: UUID
    name_en: str
    name_np: Optional[str] = None
    code: str
    description: Optional[str] = None
    is_active: bool
    max_students: int
    streams: List["HSStreamResponse"] = []

    class Config:
        from_attributes = True


class HSStreamCreate(BaseModel):
    faculty_id: UUID
    name_en: str = Field(..., min_length=1)
    name_np: Optional[str] = None
    code: str = Field(..., max_length=20)


class HSStreamResponse(BaseModel):
    id: UUID
    faculty_id: UUID
    name_en: str
    name_np: Optional[str] = None
    code: str
    is_active: bool

    class Config:
        from_attributes = True


# Resolve forward references
GradeResponse.model_rebuild()
HSFacultyResponse.model_rebuild()
