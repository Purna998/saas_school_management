"""
Nepal School Management System - Academic Service
Academic structure management: grades, sections, subjects, timetable
"""

import uuid
import logging
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from shared.utils.exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
    GradeNotFoundError,
    SectionNotFoundError,
    SubjectNotFoundError,
    FacultyNotFoundError,
)
from services.academic.models.academic import (
    Grade,
    Section,
    Subject,
    TimetableEntry,
    HSFaculty,
    HSStream,
    SubjectType,
    DayOfWeek,
)
from services.academic.schemas.academic import (
    GradeCreate,
    SectionCreate,
    SubjectCreate,
    TimetableEntryCreate,
    HSFacultyCreate,
    HSStreamCreate,
)

logger = logging.getLogger(__name__)


class AcademicService:
    """Academic structure management service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_overview(self, school_id: uuid.UUID) -> dict[str, int]:
        """Return dashboard counts in one database round trip."""
        grade_count = select(func.count(Grade.id)).where(
            Grade.school_id == school_id,
            Grade.is_active.is_(True),
        )
        section_count = select(func.count(Section.id)).where(
            Section.school_id == school_id,
            Section.is_active.is_(True),
        )
        subject_count = select(func.count(Subject.id)).where(
            Subject.school_id == school_id,
            Subject.is_active.is_(True),
        )
        faculty_count = select(func.count(HSFaculty.id)).where(
            HSFaculty.school_id == school_id,
            HSFaculty.is_active.is_(True),
        )
        result = await self.db.execute(
            select(
                grade_count.scalar_subquery().label("grades"),
                section_count.scalar_subquery().label("sections"),
                subject_count.scalar_subquery().label("subjects"),
                faculty_count.scalar_subquery().label("faculties"),
            )
        )
        return dict(result.one()._mapping)

    # --- Grades ---

    async def create_grade(self, data: GradeCreate, school_id: uuid.UUID) -> Grade:
        """Create a new grade for a school"""
        grade = Grade(
            id=uuid.uuid4(),
            school_id=school_id,
            grade_number=data.grade_number,
            name_en=data.name_en,
            name_np=data.name_np,
            is_hs=data.grade_number >= 11,
            academic_year_bs=data.academic_year_bs,
            is_active=True,
        )
        self.db.add(grade)
        await self.db.commit()
        await self.db.refresh(grade)
        return grade

    async def get_grade(self, grade_id: uuid.UUID, school_id: uuid.UUID) -> Grade:
        result = await self.db.execute(
            select(Grade)
            .where(Grade.id == grade_id, Grade.school_id == school_id)
            .options(selectinload(Grade.sections))
        )
        grade = result.scalar_one_or_none()
        if not grade:
            raise GradeNotFoundError(str(grade_id))
        return grade

    async def list_grades(self, school_id: uuid.UUID) -> List[Grade]:
        result = await self.db.execute(
            select(Grade)
            .where(Grade.school_id == school_id, Grade.is_active == True)
            .options(selectinload(Grade.sections))
            .order_by(Grade.grade_number)
        )
        return result.scalars().all()

    # --- Sections ---

    async def create_section(self, data: SectionCreate, school_id: uuid.UUID) -> Section:
        await self.get_grade(data.grade_id, school_id)
        section = Section(
            id=uuid.uuid4(),
            school_id=school_id,
            grade_id=data.grade_id,
            name=data.name,
            capacity=data.capacity,
            class_teacher_id=data.class_teacher_id,
            is_active=True,
        )
        self.db.add(section)
        await self.db.commit()
        await self.db.refresh(section)
        return section

    async def get_section(self, section_id: uuid.UUID, school_id: uuid.UUID) -> Section:
        result = await self.db.execute(
            select(Section).where(Section.id == section_id, Section.school_id == school_id)
        )
        section = result.scalar_one_or_none()
        if not section:
            raise SectionNotFoundError(str(section_id))
        return section

    async def list_sections(self, grade_id: uuid.UUID, school_id: uuid.UUID) -> List[Section]:
        result = await self.db.execute(
            select(Section)
            .where(Section.grade_id == grade_id, Section.school_id == school_id, Section.is_active == True)
            .order_by(Section.name)
        )
        return result.scalars().all()

    # --- Subjects ---

    async def create_subject(self, data: SubjectCreate, school_id: uuid.UUID) -> Subject:
        await self.get_grade(data.grade_id, school_id)
        if data.faculty_id:
            await self.get_faculty(data.faculty_id, school_id)
        subject = Subject(
            id=uuid.uuid4(),
            school_id=school_id,
            grade_id=data.grade_id,
            code=data.code,
            name_en=data.name_en,
            name_np=data.name_np,
            subject_type=SubjectType(data.subject_type),
            full_marks=data.full_marks,
            pass_marks=data.pass_marks,
            credit_hours=data.credit_hours,
            teacher_id=data.teacher_id,
            faculty_id=data.faculty_id,
            is_active=True,
        )
        self.db.add(subject)
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def get_subject(self, subject_id: uuid.UUID, school_id: uuid.UUID) -> Subject:
        result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise SubjectNotFoundError(str(subject_id))
        return subject

    async def list_subjects(self, grade_id: uuid.UUID, school_id: uuid.UUID, faculty_id: Optional[uuid.UUID] = None) -> List[Subject]:
        query = select(Subject).where(Subject.grade_id == grade_id, Subject.school_id == school_id, Subject.is_active == True)
        if faculty_id:
            query = query.where(Subject.faculty_id == faculty_id)
        query = query.order_by(Subject.code)
        result = await self.db.execute(query)
        return result.scalars().all()

    # --- Timetable ---

    async def create_timetable_entry(self, data: TimetableEntryCreate, school_id: uuid.UUID) -> TimetableEntry:
        await self.get_section(data.section_id, school_id)
        await self.get_subject(data.subject_id, school_id)
        entry = TimetableEntry(
            id=uuid.uuid4(),
            school_id=school_id,
            grade_id=data.grade_id,
            section_id=data.section_id,
            subject_id=data.subject_id,
            teacher_id=data.teacher_id,
            day_of_week=DayOfWeek(data.day_of_week),
            period_number=data.period_number,
            start_time=data.start_time,
            end_time=data.end_time,
            room=data.room,
            is_active=True,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get_timetable(self, section_id: uuid.UUID, school_id: uuid.UUID) -> List[TimetableEntry]:
        result = await self.db.execute(
            select(TimetableEntry)
            .where(TimetableEntry.section_id == section_id, TimetableEntry.school_id == school_id, TimetableEntry.is_active == True)
            .order_by(TimetableEntry.day_of_week, TimetableEntry.period_number)
        )
        return result.scalars().all()

    # --- Higher Secondary Faculties ---

    async def create_faculty(self, data: HSFacultyCreate, school_id: uuid.UUID) -> HSFaculty:
        faculty = HSFaculty(
            id=uuid.uuid4(),
            school_id=school_id,
            name_en=data.name_en,
            name_np=data.name_np,
            code=data.code,
            description=data.description,
            max_students=data.max_students,
            is_active=True,
        )
        self.db.add(faculty)
        await self.db.commit()
        await self.db.refresh(faculty)
        return faculty

    async def get_faculty(self, faculty_id: uuid.UUID, school_id: uuid.UUID) -> HSFaculty:
        result = await self.db.execute(
            select(HSFaculty)
            .where(HSFaculty.id == faculty_id, HSFaculty.school_id == school_id)
            .options(selectinload(HSFaculty.streams))
        )
        faculty = result.scalar_one_or_none()
        if not faculty:
            raise FacultyNotFoundError(str(faculty_id))
        return faculty

    async def list_faculties(self, school_id: uuid.UUID) -> List[HSFaculty]:
        result = await self.db.execute(
            select(HSFaculty)
            .where(HSFaculty.school_id == school_id, HSFaculty.is_active == True)
            .options(selectinload(HSFaculty.streams))
            .order_by(HSFaculty.name_en)
        )
        return result.scalars().all()

    # --- Higher Secondary Streams ---

    async def create_stream(self, data: HSStreamCreate, school_id: uuid.UUID) -> HSStream:
        await self.get_faculty(data.faculty_id, school_id)
        stream = HSStream(
            id=uuid.uuid4(),
            school_id=school_id,
            faculty_id=data.faculty_id,
            name_en=data.name_en,
            name_np=data.name_np,
            code=data.code,
            is_active=True,
        )
        self.db.add(stream)
        await self.db.commit()
        await self.db.refresh(stream)
        return stream
