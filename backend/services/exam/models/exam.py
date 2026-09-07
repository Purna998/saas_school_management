"""
Nepal School Management System - Exam Models
Exam, marks, and result management with dual grading (GPA + Percentage)
"""

from datetime import datetime, date, time
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Time, Integer, Text,
    ForeignKey, Numeric, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin, SoftDeleteMixin


class ExamType(str, enum.Enum):
    """Types of examinations in Nepal school system"""
    TERMINAL = "terminal"
    UNIT_TEST = "unit_test"
    FINAL = "final"
    PRE_BOARD = "pre_board"
    SEND_UP = "send_up"


class ExamStatus(str, enum.Enum):
    """Exam lifecycle status"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    PUBLISHED = "published"


class ResultStatus(str, enum.Enum):
    """Student result status"""
    PASS = "pass"
    FAIL = "fail"
    ABSENT = "absent"


class Division(str, enum.Enum):
    """Division system for Higher Secondary (Grades 11-12)"""
    FIRST = "first"
    SECOND = "second"
    THIRD = "third"
    FAIL = "fail"


class Exam(Base, BaseModel, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """
    Exam model representing an examination event.

    Supports Nepal education system exam types including
    terminal, unit test, final, pre-board, and send-up exams.
    """

    __tablename__ = "exams"

    name = Column(String(255), nullable=False, comment="Exam name (e.g., First Terminal 2081)")
    exam_type = Column(
        SQLEnum(ExamType),
        nullable=False,
        comment="Type of examination"
    )
    academic_year_bs = Column(
        String(10),
        nullable=False,
        comment="Academic year in BS (e.g., 2081)"
    )
    grade = Column(
        Integer,
        nullable=False,
        comment="Grade level (1-12)"
    )
    start_date_ad = Column(Date, nullable=True, comment="Exam start date (AD)")
    end_date_ad = Column(Date, nullable=True, comment="Exam end date (AD)")
    status = Column(
        SQLEnum(ExamStatus),
        default=ExamStatus.DRAFT,
        nullable=False,
        index=True,
        comment="Exam lifecycle status"
    )
    is_locked = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether marks entry is locked"
    )

    # Relationships
    subjects = relationship("ExamSubject", back_populates="exam", cascade="all, delete-orphan")
    marks = relationship("Mark", back_populates="exam", cascade="all, delete-orphan")
    results = relationship("Result", back_populates="exam", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Exam(id={self.id}, name={self.name}, grade={self.grade}, status={self.status})>"


class ExamSubject(Base, BaseModel, TimestampMixin):
    """
    Subject-wise exam configuration.

    Defines full marks, pass marks, and scheduling for each subject
    within an exam.
    """

    __tablename__ = "exam_subjects"

    exam_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent exam"
    )
    subject_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="Reference to subject (from Academic service)"
    )
    full_marks = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Maximum marks for this subject"
    )
    pass_marks = Column(
        Numeric(5, 2),
        nullable=False,
        comment="Minimum marks required to pass"
    )
    exam_date_ad = Column(Date, nullable=True, comment="Exam date for this subject (AD)")
    start_time = Column(Time, nullable=True, comment="Exam start time")
    end_time = Column(Time, nullable=True, comment="Exam end time")

    # Relationships
    exam = relationship("Exam", back_populates="subjects")
    marks = relationship("Mark", back_populates="exam_subject", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("exam_id", "subject_id", name="uq_exam_subject"),
    )

    def __repr__(self):
        return f"<ExamSubject(exam_id={self.exam_id}, subject_id={self.subject_id}, full={self.full_marks})>"


class Mark(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    Individual student mark for an exam subject.

    Stores marks obtained, computed grade point (for GPA system),
    and entry metadata.
    """

    __tablename__ = "marks"

    exam_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to exam"
    )
    exam_subject_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exam_subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to exam subject"
    )
    student_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Reference to student (from Student service)"
    )
    marks_obtained = Column(
        Numeric(6, 2),
        nullable=False,
        comment="Marks obtained by student"
    )
    grade_point = Column(
        Numeric(3, 1),
        nullable=True,
        comment="Grade point (GPA system, grades 1-10)"
    )
    remarks = Column(
        String(500),
        nullable=True,
        comment="Teacher remarks for this subject"
    )
    entered_by = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="User who entered the marks"
    )

    # Relationships
    exam = relationship("Exam", back_populates="marks")
    exam_subject = relationship("ExamSubject", back_populates="marks")

    __table_args__ = (
        UniqueConstraint("exam_subject_id", "student_id", name="uq_mark_subject_student"),
        {"extend_existing": True},
    )

    def __repr__(self):
        return f"<Mark(student={self.student_id}, marks={self.marks_obtained})>"


class Result(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    Aggregated result for a student in an exam.

    Computes GPA (grades 1-10) or percentage with division (grades 11-12)
    based on Nepal education system grading.
    """

    __tablename__ = "results"

    exam_id = Column(
        UUID(as_uuid=True),
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to exam"
    )
    student_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Reference to student"
    )
    total_marks = Column(
        Numeric(7, 2),
        nullable=True,
        comment="Total marks obtained"
    )
    percentage = Column(
        Numeric(5, 2),
        nullable=True,
        comment="Percentage (primarily for grades 11-12)"
    )
    gpa = Column(
        Numeric(3, 2),
        nullable=True,
        comment="GPA on 4.0 scale (grades 1-10)"
    )
    division = Column(
        SQLEnum(Division),
        nullable=True,
        comment="Division for HS: first/second/third/fail"
    )
    rank = Column(
        Integer,
        nullable=True,
        comment="Rank in class"
    )
    status = Column(
        SQLEnum(ResultStatus),
        nullable=False,
        default=ResultStatus.PASS,
        comment="Result status: pass/fail/absent"
    )

    # Relationships
    exam = relationship("Exam", back_populates="results")

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_result_exam_student"),
        {"extend_existing": True},
    )

    def __repr__(self):
        return f"<Result(student={self.student_id}, gpa={self.gpa}, percentage={self.percentage}, status={self.status})>"
