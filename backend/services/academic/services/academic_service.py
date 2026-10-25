"""
Nepal School Management System - Academic Service
Academic structure management: grades, sections, subjects, timetable
"""

import uuid
import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from sqlalchemy.orm import selectinload

from shared.utils.exceptions import (
    RecordNotFoundError,
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
    GradeUpdate,
    SectionCreate,
    SectionUpdate,
    SubjectCreate,
    SubjectUpdate,
    TimetableEntryCreate,
    HSFacultyCreate,
    HSFacultyUpdate,
    HSStreamCreate,
    HSStreamUpdate,
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

    async def update_grade(self, grade_id: uuid.UUID, data: GradeUpdate, school_id: uuid.UUID) -> Grade:
        grade = await self.get_grade(grade_id, school_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(grade, field, value)
        if data.grade_number is not None:
            grade.is_hs = data.grade_number >= 11
        await self.db.commit()
        await self.db.refresh(grade)
        return grade

    async def deactivate_grade(self, grade_id: uuid.UUID, school_id: uuid.UUID) -> None:
        grade = await self.get_grade(grade_id, school_id)
        grade.is_active = False
        await self.db.execute(update(Section).where(Section.grade_id == grade_id, Section.school_id == school_id).values(is_active=False))
        await self.db.execute(update(Subject).where(Subject.grade_id == grade_id, Subject.school_id == school_id).values(is_active=False))
        await self.db.commit()

    # --- Sections ---

    async def create_section(self, data: SectionCreate, school_id: uuid.UUID) -> Section:
        grade = await self.get_grade(data.grade_id, school_id)
        if data.stream_id:
            if not grade.is_hs:
                raise ValueError("Streams can only be assigned to Grade 11 or Grade 12 sections")
            await self.get_stream(data.stream_id, school_id)
        section = Section(
            id=uuid.uuid4(),
            school_id=school_id,
            grade_id=data.grade_id,
            name=data.name,
            capacity=data.capacity,
            class_teacher_id=data.class_teacher_id,
            stream_id=data.stream_id,
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

    async def update_section(self, section_id: uuid.UUID, data: SectionUpdate, school_id: uuid.UUID) -> Section:
        section = await self.get_section(section_id, school_id)
        fields = data.model_dump(exclude_unset=True)
        if fields.get("stream_id"):
            grade = await self.get_grade(section.grade_id, school_id)
            if not grade.is_hs:
                raise ValueError("Streams can only be assigned to Grade 11 or Grade 12 sections")
            await self.get_stream(fields["stream_id"], school_id)
        for field, value in fields.items():
            setattr(section, field, value)
        await self.db.commit()
        await self.db.refresh(section)
        return section

    async def deactivate_section(self, section_id: uuid.UUID, school_id: uuid.UUID) -> None:
        section = await self.get_section(section_id, school_id)
        section.is_active = False
        await self.db.commit()

    # --- Subjects ---

    async def create_subject(self, data: SubjectCreate, school_id: uuid.UUID) -> Subject:
        await self.get_grade(data.grade_id, school_id)
        if data.faculty_id:
            await self.get_faculty(data.faculty_id, school_id)
        streams = []
        for stream_id in data.stream_ids:
            stream = await self.get_stream(stream_id, school_id)
            if not data.faculty_id or stream.faculty_id != data.faculty_id:
                raise ValueError("Every selected stream must belong to the selected faculty")
            streams.append(stream)
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
            optional_group=data.optional_group,
            teacher_id=data.teacher_id,
            faculty_id=data.faculty_id,
            streams=streams,
            is_active=True,
        )
        self.db.add(subject)
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def get_subject(self, subject_id: uuid.UUID, school_id: uuid.UUID) -> Subject:
        result = await self.db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id).options(selectinload(Subject.streams))
        )
        subject = result.scalar_one_or_none()
        if not subject:
            raise SubjectNotFoundError(str(subject_id))
        return subject

    async def list_subjects(self, grade_id: uuid.UUID, school_id: uuid.UUID, faculty_id: Optional[uuid.UUID] = None) -> List[Subject]:
        query = select(Subject).where(Subject.grade_id == grade_id, Subject.school_id == school_id, Subject.is_active == True).options(selectinload(Subject.streams))
        if faculty_id:
            query = query.where(Subject.faculty_id == faculty_id)
        query = query.order_by(Subject.code)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_subject(self, subject_id: uuid.UUID, data: SubjectUpdate, school_id: uuid.UUID) -> Subject:
        subject = await self.get_subject(subject_id, school_id)
        fields = data.model_dump(exclude_unset=True)
        stream_ids = fields.pop("stream_ids", None)
        if fields.get("faculty_id"):
            await self.get_faculty(fields["faculty_id"], school_id)
        if stream_ids is not None:
            effective_faculty_id = fields.get("faculty_id", subject.faculty_id)
            streams = []
            for stream_id in stream_ids:
                stream = await self.get_stream(stream_id, school_id)
                if not effective_faculty_id or stream.faculty_id != effective_faculty_id:
                    raise ValueError("Every selected stream must belong to the selected faculty")
                streams.append(stream)
            subject.streams = streams
        for field, value in fields.items():
            if field == "subject_type" and value is not None:
                value = SubjectType(value)
            setattr(subject, field, value)
        await self.db.commit()
        await self.db.refresh(subject)
        return subject

    async def deactivate_subject(self, subject_id: uuid.UUID, school_id: uuid.UUID) -> None:
        subject = await self.get_subject(subject_id, school_id)
        subject.is_active = False
        await self.db.commit()

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

    async def update_faculty(self, faculty_id: uuid.UUID, data: HSFacultyUpdate, school_id: uuid.UUID) -> HSFaculty:
        faculty = await self.get_faculty(faculty_id, school_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(faculty, field, value)
        await self.db.commit()
        await self.db.refresh(faculty)
        return faculty

    async def deactivate_faculty(self, faculty_id: uuid.UUID, school_id: uuid.UUID) -> None:
        faculty = await self.get_faculty(faculty_id, school_id)
        faculty.is_active = False
        await self.db.execute(update(HSStream).where(HSStream.faculty_id == faculty_id, HSStream.school_id == school_id).values(is_active=False))
        await self.db.execute(update(Subject).where(Subject.faculty_id == faculty_id, Subject.school_id == school_id).values(is_active=False))
        await self.db.commit()

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

    async def get_stream(self, stream_id: uuid.UUID, school_id: uuid.UUID) -> HSStream:
        result = await self.db.execute(select(HSStream).where(HSStream.id == stream_id, HSStream.school_id == school_id))
        stream = result.scalar_one_or_none()
        if not stream:
            raise RecordNotFoundError(f"Stream with ID {stream_id} not found")
        return stream

    async def update_stream(self, stream_id: uuid.UUID, data: HSStreamUpdate, school_id: uuid.UUID) -> HSStream:
        stream = await self.get_stream(stream_id, school_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(stream, field, value)
        await self.db.commit()
        await self.db.refresh(stream)
        return stream

    async def deactivate_stream(self, stream_id: uuid.UUID, school_id: uuid.UUID) -> None:
        stream = await self.get_stream(stream_id, school_id)
        stream.is_active = False
        await self.db.commit()
