"""
Nepal School Management System - Student Model
Student profile, enrollment, and guardian data
"""

from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, DateTime, Date, Integer, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin, SoftDeleteMixin


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class StudentStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRANSFERRED = "transferred"
    GRADUATED = "graduated"
    DROPPED_OUT = "dropped_out"


class EnrollmentStatus(str, enum.Enum):
    ENROLLED = "enrolled"
    PROMOTED = "promoted"
    REPEATED = "repeated"
    TRANSFERRED_OUT = "transferred_out"
    DROPPED = "dropped"


class GuardianRelation(str, enum.Enum):
    FATHER = "father"
    MOTHER = "mother"
    GUARDIAN = "guardian"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    UNCLE = "uncle"
    AUNT = "aunt"
    OTHER = "other"


class CasteEthnicity(str, enum.Enum):
    """EMIS-compliant caste/ethnicity categories"""
    BRAHMIN_HILL = "brahmin_hill"
    CHHETRI = "chhetri"
    THAKURI = "thakuri"
    SANYASI = "sanyasi"
    NEWAR = "newar"
    JANAJATI_HILL = "janajati_hill"
    JANAJATI_TERAI = "janajati_terai"
    MADHESI = "madhesi"
    DALIT_HILL = "dalit_hill"
    DALIT_TERAI = "dalit_terai"
    MUSLIM = "muslim"
    OTHER = "other"


class Student(Base, BaseModel, TimestampMixin, TenantMixin, SoftDeleteMixin):
    """
    Student model with EMIS compliance.

    Supports both English and Nepali names, BS/AD dates,
    and Nepal-specific fields like caste/ethnicity.
    """

    __tablename__ = "students"

    # Identification
    emis_student_id = Column(
        String(30),
        unique=True,
        nullable=True,
        index=True,
        comment="EMIS Student ID (Ministry assigned)"
    )
    admission_number = Column(
        String(30),
        nullable=True,
        index=True,
        comment="School admission number"
    )
    roll_number = Column(
        Integer,
        nullable=True,
        comment="Current roll number in class"
    )

    # Personal info
    full_name_en = Column(String(200), nullable=False, comment="Full name in English")
    full_name_np = Column(String(200), nullable=True, comment="Full name in Nepali")
    gender = Column(SQLEnum(Gender), nullable=False, comment="Gender")
    date_of_birth_ad = Column(Date, nullable=False, comment="Date of birth (AD)")
    date_of_birth_bs = Column(String(12), nullable=True, comment="Date of birth (BS: YYYY-MM-DD)")

    # Contact
    phone = Column(String(20), nullable=True, comment="Student phone (if applicable)")
    email = Column(String(255), nullable=True, comment="Student email (if applicable)")
    address_permanent = Column(Text, nullable=True, comment="Permanent address")
    address_temporary = Column(Text, nullable=True, comment="Temporary/current address")

    # Academic
    current_grade = Column(Integer, nullable=True, comment="Current grade (1-12)")
    current_section = Column(String(10), nullable=True, comment="Current section (A, B, C)")
    current_faculty = Column(String(50), nullable=True, comment="Faculty for Grade 11-12")
    admission_date_ad = Column(Date, nullable=True, comment="Admission date (AD)")
    admission_date_bs = Column(String(12), nullable=True, comment="Admission date (BS)")

    # Demographics (EMIS)
    caste_ethnicity = Column(SQLEnum(CasteEthnicity), nullable=True, comment="Caste/ethnicity (EMIS)")
    religion = Column(String(50), nullable=True, comment="Religion")
    mother_tongue = Column(String(50), nullable=True, comment="Mother tongue")
    nationality = Column(String(50), default="Nepali", comment="Nationality")
    disability_type = Column(String(100), nullable=True, comment="Disability type (if any)")

    # Status
    status = Column(
        SQLEnum(StudentStatus),
        default=StudentStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="Student status"
    )

    # Photo
    photo_url = Column(String(500), nullable=True, comment="Student photo URL")

    # Previous school (for transfers)
    previous_school_name = Column(String(255), nullable=True)
    previous_school_emis = Column(String(20), nullable=True)
    transfer_certificate_number = Column(String(50), nullable=True)

    # Relationships
    guardians = relationship("StudentGuardian", back_populates="student", cascade="all, delete-orphan")
    enrollments = relationship("StudentEnrollment", back_populates="student", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Student(id={self.id}, name={self.full_name_en}, grade={self.current_grade})>"

    @property
    def is_active(self) -> bool:
        return self.status == StudentStatus.ACTIVE

    @property
    def is_hs_student(self) -> bool:
        return self.current_grade is not None and self.current_grade >= 11


class StudentGuardian(Base, BaseModel, TimestampMixin):
    """Student guardian/parent information"""

    __tablename__ = "student_guardians"

    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation = Column(SQLEnum(GuardianRelation), nullable=False)
    full_name_en = Column(String(200), nullable=False)
    full_name_np = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True, comment="Phone for SMS notifications")
    email = Column(String(255), nullable=True)
    occupation = Column(String(100), nullable=True)
    is_primary_contact = Column(Boolean, default=False, comment="Primary contact for SMS/calls")

    # Relationship
    student = relationship("Student", back_populates="guardians")

    def __repr__(self):
        return f"<Guardian(name={self.full_name_en}, relation={self.relation})>"


class StudentEnrollment(Base, BaseModel, TimestampMixin, TenantMixin):
    """Student enrollment history per academic year"""

    __tablename__ = "student_enrollments"

    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_year_bs = Column(String(10), nullable=False, comment="Academic year (BS)")
    grade = Column(Integer, nullable=False, comment="Grade enrolled in")
    section = Column(String(10), nullable=True, comment="Section")
    faculty = Column(String(50), nullable=True, comment="Faculty (Grade 11-12)")
    roll_number = Column(Integer, nullable=True)
    status = Column(
        SQLEnum(EnrollmentStatus),
        default=EnrollmentStatus.ENROLLED,
        nullable=False,
    )
    enrolled_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    promoted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship
    student = relationship("Student", back_populates="enrollments")

    def __repr__(self):
        return f"<Enrollment(student={self.student_id}, year={self.academic_year_bs}, grade={self.grade})>"
