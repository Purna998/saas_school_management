"""
Nepal School Management System - Academic Models
Grades, Sections, Subjects, Timetable, and Higher Secondary (Faculty/Stream)
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, Integer, ForeignKey, Text, Enum as SQLEnum, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class SubjectType(str, enum.Enum):
    COMPULSORY = "compulsory"
    OPTIONAL = "optional"
    ADDITIONAL = "additional"


class DayOfWeek(str, enum.Enum):
    SUNDAY = "sunday"
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"


class Grade(Base, BaseModel, TimestampMixin, TenantMixin):
    """Grade model (1-12)"""

    __tablename__ = "grades"

    grade_number = Column(Integer, nullable=False, comment="Grade number (1-12)")
    name_en = Column(String(50), nullable=False, comment="Grade name in English")
    name_np = Column(String(50), nullable=True, comment="Grade name in Nepali")
    is_active = Column(Boolean, default=True, nullable=False)
    is_hs = Column(Boolean, default=False, comment="Higher Secondary (Grade 11-12)")
    academic_year_bs = Column(String(10), nullable=True, comment="Academic year")

    # Relationships
    sections = relationship("Section", back_populates="grade", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="grade", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Grade(number={self.grade_number}, name={self.name_en})>"


class Section(Base, BaseModel, TimestampMixin, TenantMixin):
    """Section within a grade (A, B, C, etc.)"""

    __tablename__ = "sections"

    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(10), nullable=False, comment="Section name (A, B, C)")
    capacity = Column(Integer, default=40, comment="Maximum students")
    class_teacher_id = Column(UUID(as_uuid=True), nullable=True, comment="Class teacher user ID")
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    grade = relationship("Grade", back_populates="sections")

    def __repr__(self):
        return f"<Section(grade_id={self.grade_id}, name={self.name})>"


class Subject(Base, BaseModel, TimestampMixin, TenantMixin):
    """Subject model"""

    __tablename__ = "subjects"

    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(20), nullable=False, comment="Subject code")
    name_en = Column(String(100), nullable=False, comment="Subject name in English")
    name_np = Column(String(100), nullable=True, comment="Subject name in Nepali")
    subject_type = Column(SQLEnum(SubjectType), default=SubjectType.COMPULSORY, nullable=False)
    full_marks = Column(Integer, default=100, comment="Full marks")
    pass_marks = Column(Integer, default=40, comment="Pass marks")
    credit_hours = Column(Integer, default=4, comment="Credit hours")
    teacher_id = Column(UUID(as_uuid=True), nullable=True, comment="Assigned teacher")
    is_active = Column(Boolean, default=True, nullable=False)

    # HS specific
    faculty_id = Column(UUID(as_uuid=True), ForeignKey("hs_faculties.id"), nullable=True)

    # Relationships
    grade = relationship("Grade", back_populates="subjects")
    faculty = relationship("HSFaculty", back_populates="subjects")

    def __repr__(self):
        return f"<Subject(code={self.code}, name={self.name_en})>"


class TimetableEntry(Base, BaseModel, TimestampMixin, TenantMixin):
    """Timetable entry (single period slot)"""

    __tablename__ = "timetable_entries"

    grade_id = Column(UUID(as_uuid=True), ForeignKey("grades.id"), nullable=False, index=True)
    section_id = Column(UUID(as_uuid=True), ForeignKey("sections.id"), nullable=False)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("subjects.id"), nullable=False)
    teacher_id = Column(UUID(as_uuid=True), nullable=True)
    day_of_week = Column(SQLEnum(DayOfWeek), nullable=False)
    period_number = Column(Integer, nullable=False, comment="Period number (1-8)")
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    room = Column(String(20), nullable=True, comment="Room/Hall number")
    academic_year_bs = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Timetable(day={self.day_of_week}, period={self.period_number})>"


# Higher Secondary (Grade 11-12) specific models

class HSFaculty(Base, BaseModel, TimestampMixin, TenantMixin):
    """Faculty for Grade 11-12 (Science, Management, Humanities, Education)"""

    __tablename__ = "hs_faculties"

    name_en = Column(String(100), nullable=False, comment="Faculty name in English")
    name_np = Column(String(100), nullable=True, comment="Faculty name in Nepali")
    code = Column(String(20), nullable=False, comment="Faculty code (SCI, MGT, HUM, EDU)")
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    max_students = Column(Integer, default=60, comment="Max students per faculty")

    # Relationships
    subjects = relationship("Subject", back_populates="faculty")
    streams = relationship("HSStream", back_populates="faculty", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<HSFaculty(code={self.code}, name={self.name_en})>"


class HSStream(Base, BaseModel, TimestampMixin, TenantMixin):
    """Stream within a faculty (e.g., Science has Bio/Math groups)"""

    __tablename__ = "hs_streams"

    faculty_id = Column(UUID(as_uuid=True), ForeignKey("hs_faculties.id", ondelete="CASCADE"), nullable=False)
    name_en = Column(String(100), nullable=False)
    name_np = Column(String(100), nullable=True)
    code = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    faculty = relationship("HSFaculty", back_populates="streams")

    def __repr__(self):
        return f"<HSStream(code={self.code}, faculty={self.faculty_id})>"
