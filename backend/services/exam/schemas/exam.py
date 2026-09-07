"""
Nepal School Management System - Exam Schemas
Pydantic models for exam, marks, and results endpoints
"""

from typing import Optional, List
from uuid import UUID
from datetime import date, time, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ============================================================
# Exam Schemas
# ============================================================

class ExamSubjectCreate(BaseModel):
    """Subject configuration for an exam"""

    subject_id: UUID = Field(..., description="Subject UUID from Academic service")
    full_marks: Decimal = Field(..., gt=0, le=100, description="Maximum marks")
    pass_marks: Decimal = Field(..., gt=0, le=100, description="Minimum passing marks")
    exam_date_ad: Optional[date] = Field(None, description="Exam date for this subject (AD)")
    start_time: Optional[time] = Field(None, description="Exam start time")
    end_time: Optional[time] = Field(None, description="Exam end time")


class ExamSubjectResponse(BaseModel):
    """Exam subject response"""

    id: UUID
    exam_id: UUID
    subject_id: UUID
    full_marks: Decimal
    pass_marks: Decimal
    exam_date_ad: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    class Config:
        from_attributes = True


class ExamCreate(BaseModel):
    """Create exam schema"""

    name: str = Field(..., min_length=3, max_length=255, description="Exam name")
    exam_type: str = Field(..., description="Type: terminal/unit_test/final/pre_board/send_up")
    academic_year_bs: str = Field(..., min_length=4, max_length=10, description="Academic year in BS")
    grade: int = Field(..., ge=1, le=12, description="Grade level (1-12)")
    start_date_ad: Optional[date] = Field(None, description="Exam start date (AD)")
    end_date_ad: Optional[date] = Field(None, description="Exam end date (AD)")
    subjects: List[ExamSubjectCreate] = Field(
        default_factory=list,
        description="Subject configurations for this exam"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "First Terminal Exam 2081",
                "exam_type": "terminal",
                "academic_year_bs": "2081",
                "grade": 8,
                "start_date_ad": "2024-09-15",
                "end_date_ad": "2024-09-25",
                "subjects": [
                    {
                        "subject_id": "550e8400-e29b-41d4-a716-446655440001",
                        "full_marks": 100,
                        "pass_marks": 40,
                        "exam_date_ad": "2024-09-15",
                        "start_time": "10:00:00",
                        "end_time": "13:00:00",
                    }
                ],
            }
        }


class ExamUpdate(BaseModel):
    """Update exam schema"""

    name: Optional[str] = Field(None, min_length=3, max_length=255)
    start_date_ad: Optional[date] = None
    end_date_ad: Optional[date] = None


class ExamStatusUpdate(BaseModel):
    """Update exam status"""

    status: str = Field(..., description="New status: draft/scheduled/ongoing/completed/published")


class ExamResponse(BaseModel):
    """Exam response schema"""

    id: UUID
    school_id: UUID
    name: str
    exam_type: str
    academic_year_bs: str
    grade: int
    start_date_ad: Optional[date] = None
    end_date_ad: Optional[date] = None
    status: str
    is_locked: bool
    subjects: List[ExamSubjectResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExamListResponse(BaseModel):
    """Exam list with pagination"""

    exams: List[ExamResponse]
    total: int
    page: int
    limit: int


# ============================================================
# Mark Schemas
# ============================================================

class MarkEntry(BaseModel):
    """Single mark entry for a student"""

    student_id: UUID = Field(..., description="Student UUID")
    marks_obtained: Decimal = Field(..., ge=0, description="Marks obtained")
    remarks: Optional[str] = Field(None, max_length=500, description="Remarks")


class MarkEntryRequest(BaseModel):
    """Batch mark entry request"""

    exam_subject_id: UUID = Field(..., description="Exam subject UUID")
    entries: List[MarkEntry] = Field(..., min_length=1, description="List of mark entries")

    class Config:
        json_schema_extra = {
            "example": {
                "exam_subject_id": "550e8400-e29b-41d4-a716-446655440001",
                "entries": [
                    {
                        "student_id": "550e8400-e29b-41d4-a716-446655440010",
                        "marks_obtained": 85.5,
                        "remarks": "Excellent performance",
                    },
                    {
                        "student_id": "550e8400-e29b-41d4-a716-446655440011",
                        "marks_obtained": 42.0,
                    },
                ],
            }
        }


class MarkResponse(BaseModel):
    """Mark response schema"""

    id: UUID
    exam_id: UUID
    exam_subject_id: UUID
    student_id: UUID
    marks_obtained: Decimal
    grade_point: Optional[Decimal] = None
    remarks: Optional[str] = None
    entered_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class MarkListResponse(BaseModel):
    """List of marks for a subject"""

    exam_subject_id: UUID
    subject_id: UUID
    full_marks: Decimal
    pass_marks: Decimal
    marks: List[MarkResponse]
    total: int


# ============================================================
# Result Schemas
# ============================================================

class SubjectResult(BaseModel):
    """Individual subject result within a report card"""

    subject_id: UUID
    subject_name: Optional[str] = None
    full_marks: Decimal
    pass_marks: Decimal
    marks_obtained: Decimal
    grade_point: Optional[Decimal] = None
    remarks: Optional[str] = None


class ResultResponse(BaseModel):
    """Student result for an exam"""

    id: UUID
    exam_id: UUID
    student_id: UUID
    total_marks: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    gpa: Optional[Decimal] = None
    division: Optional[str] = None
    rank: Optional[int] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ResultListResponse(BaseModel):
    """List of results for an exam"""

    exam_id: UUID
    exam_name: str
    grade: int
    results: List[ResultResponse]
    total: int


class ReportCardResponse(BaseModel):
    """Complete report card for a student"""

    student_id: UUID
    student_name: Optional[str] = None
    exam_id: UUID
    exam_name: str
    exam_type: str
    academic_year_bs: str
    grade: int
    subjects: List[SubjectResult] = []
    total_marks: Optional[Decimal] = None
    full_marks_total: Optional[Decimal] = None
    percentage: Optional[Decimal] = None
    gpa: Optional[Decimal] = None
    division: Optional[str] = None
    rank: Optional[int] = None
    status: str
    grading_system: str = Field(
        ..., description="'gpa' for grades 1-10, 'percentage' for grades 11-12"
    )
