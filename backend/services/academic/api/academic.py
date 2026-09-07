"""
Nepal School Management System - Academic API Routes
Grade, Section, Subject, Timetable, and Faculty management
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import (
    GradeNotFoundError,
    SectionNotFoundError,
    SubjectNotFoundError,
    FacultyNotFoundError,
    HSNotEnabledError,
)
from services.auth.dependencies.auth import get_current_active_user, require_permission
from services.auth.models.user import User
from services.academic.schemas.academic import (
    GradeCreate,
    GradeResponse,
    SectionCreate,
    SectionResponse,
    SubjectCreate,
    SubjectResponse,
    TimetableEntryCreate,
    TimetableEntryResponse,
    TimetableResponse,
    HSFacultyCreate,
    HSFacultyResponse,
    HSStreamCreate,
    HSStreamResponse,
)
from services.academic.services.academic_service import AcademicService

router = APIRouter()


# --- Grades ---

@router.post("/grades", response_model=GradeResponse, status_code=status.HTTP_201_CREATED)
async def create_grade(
    data: GradeCreate,
    current_user: User = Depends(require_permission("academic:create")),
    db: AsyncSession = Depends(get_db)
):
    """Create a new grade"""
    service = AcademicService(db)
    grade = await service.create_grade(data, current_user.school_id)
    return GradeResponse(
        id=grade.id,
        grade_number=grade.grade_number,
        name_en=grade.name_en,
        name_np=grade.name_np,
        is_active=grade.is_active,
        is_hs=grade.is_hs,
        academic_year_bs=grade.academic_year_bs,
        sections=[],
    )


@router.get("/grades", response_model=list[GradeResponse])
async def list_grades(
    current_user: User = Depends(require_permission("academic:read")),
    db: AsyncSession = Depends(get_db)
):
    """List all grades for the school"""
    service = AcademicService(db)
    grades = await service.list_grades(current_user.school_id)
    return [
        GradeResponse(
            id=g.id,
            grade_number=g.grade_number,
            name_en=g.name_en,
            name_np=g.name_np,
            is_active=g.is_active,
            is_hs=g.is_hs,
            academic_year_bs=g.academic_year_bs,
            sections=[
                SectionResponse(
                    id=s.id, grade_id=s.grade_id, name=s.name,
                    capacity=s.capacity, class_teacher_id=s.class_teacher_id,
                    is_active=s.is_active,
                )
                for s in g.sections
            ],
        )
        for g in grades
    ]


@router.get("/grades/{grade_id}", response_model=GradeResponse)
async def get_grade(
    grade_id: uuid.UUID,
    current_user: User = Depends(require_permission("academic:read")),
    db: AsyncSession = Depends(get_db)
):
    """Get grade details with sections"""
    try:
        service = AcademicService(db)
        grade = await service.get_grade(grade_id)
        return GradeResponse(
            id=grade.id,
            grade_number=grade.grade_number,
            name_en=grade.name_en,
            name_np=grade.name_np,
            is_active=grade.is_active,
            is_hs=grade.is_hs,
            academic_year_bs=grade.academic_year_bs,
            sections=[
                SectionResponse(
                    id=s.id, grade_id=s.grade_id, name=s.name,
                    capacity=s.capacity, class_teacher_id=s.class_teacher_id,
                    is_active=s.is_active,
                )
                for s in grade.sections
            ],
        )
    except GradeNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_response(str(e), "GRADE_NOT_FOUND"))


# --- Sections ---

@router.post("/sections", response_model=SectionResponse, status_code=status.HTTP_201_CREATED)
async def create_section(
    data: SectionCreate,
    current_user: User = Depends(require_permission("academic:create")),
    db: AsyncSession = Depends(get_db)
):
    """Create a new section in a grade"""
    service = AcademicService(db)
    section = await service.create_section(data, current_user.school_id)
    return SectionResponse(
        id=section.id, grade_id=section.grade_id, name=section.name,
        capacity=section.capacity, class_teacher_id=section.class_teacher_id,
        is_active=section.is_active,
    )


@router.get("/grades/{grade_id}/sections", response_model=list[SectionResponse])
async def list_sections(
    grade_id: uuid.UUID,
    current_user: User = Depends(require_permission("academic:read")),
    db: AsyncSession = Depends(get_db)
):
    """List all sections for a grade"""
    service = AcademicService(db)
    sections = await service.list_sections(grade_id)
    return [
        SectionResponse(
            id=s.id, grade_id=s.grade_id, name=s.name,
            capacity=s.capacity, class_teacher_id=s.class_teacher_id,
            is_active=s.is_active,
        )
        for s in sections
    ]


# --- Subjects ---

@router.post("/subjects", response_model=SubjectResponse, status_code=status.HTTP_201_CREATED)
async def create_subject(
    data: SubjectCreate,
    current_user: User = Depends(require_permission("academic:create")),
    db: AsyncSession = Depends(get_db)
):
    """Create a new subject"""
    service = AcademicService(db)
    subject = await service.create_subject(data, current_user.school_id)
    return SubjectResponse(
        id=subject.id, grade_id=subject.grade_id, code=subject.code,
        name_en=subject.name_en, name_np=subject.name_np,
        subject_type=subject.subject_type.value,
        full_marks=subject.full_marks, pass_marks=subject.pass_marks,
        credit_hours=subject.credit_hours, teacher_id=subject.teacher_id,
        faculty_id=subject.faculty_id, is_active=subject.is_active,
    )


@router.get("/grades/{grade_id}/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    grade_id: uuid.UUID,
    faculty_id: Optional[uuid.UUID] = Query(default=None),
    current_user: User = Depends(require_permission("academic:read")),
    db: AsyncSession = Depends(get_db)
):
    """List subjects for a grade (optionally filtered by faculty)"""
    service = AcademicService(db)
    subjects = await service.list_subjects(grade_id, faculty_id)
    return [
        SubjectResponse(
            id=s.id, grade_id=s.grade_id, code=s.code,
            name_en=s.name_en, name_np=s.name_np,
            subject_type=s.subject_type.value,
            full_marks=s.full_marks, pass_marks=s.pass_marks,
            credit_hours=s.credit_hours, teacher_id=s.teacher_id,
            faculty_id=s.faculty_id, is_active=s.is_active,
        )
        for s in subjects
    ]


# --- Timetable ---

@router.post("/timetable", response_model=TimetableEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_timetable_entry(
    data: TimetableEntryCreate,
    current_user: User = Depends(require_permission("academic:create")),
    db: AsyncSession = Depends(get_db)
):
    """Create a timetable entry"""
    service = AcademicService(db)
    entry = await service.create_timetable_entry(data, current_user.school_id)
    return TimetableEntryResponse(
        id=entry.id, grade_id=entry.grade_id, section_id=entry.section_id,
        subject_id=entry.subject_id, teacher_id=entry.teacher_id,
        day_of_week=entry.day_of_week.value, period_number=entry.period_number,
        start_time=str(entry.start_time) if entry.start_time else None,
        end_time=str(entry.end_time) if entry.end_time else None,
        room=entry.room, is_active=entry.is_active,
    )


@router.get("/sections/{section_id}/timetable", response_model=TimetableResponse)
async def get_timetable(
    section_id: uuid.UUID,
    current_user: User = Depends(require_permission("academic:read")),
    db: AsyncSession = Depends(get_db)
):
    """Get full timetable for a section"""
    service = AcademicService(db)
    section = await service.get_section(section_id)
    entries = await service.get_timetable(section_id)

    return TimetableResponse(
        grade_id=section.grade_id,
        section_id=section_id,
        entries=[
            TimetableEntryResponse(
                id=e.id, grade_id=e.grade_id, section_id=e.section_id,
                subject_id=e.subject_id, teacher_id=e.teacher_id,
                day_of_week=e.day_of_week.value, period_number=e.period_number,
                start_time=str(e.start_time) if e.start_time else None,
                end_time=str(e.end_time) if e.end_time else None,
                room=e.room, is_active=e.is_active,
            )
            for e in entries
        ],
    )


# --- Higher Secondary Faculties ---

@router.post("/faculties", response_model=HSFacultyResponse, status_code=status.HTTP_201_CREATED)
async def create_faculty(
    data: HSFacultyCreate,
    current_user: User = Depends(require_permission("academic:create")),
    db: AsyncSession = Depends(get_db)
):
    """Create a Higher Secondary faculty"""
    service = AcademicService(db)
    faculty = await service.create_faculty(data, current_user.school_id)
    return HSFacultyResponse(
        id=faculty.id, name_en=faculty.name_en, name_np=faculty.name_np,
        code=faculty.code, description=faculty.description,
        is_active=faculty.is_active, max_students=faculty.max_students,
        streams=[],
    )


@router.get("/faculties", response_model=list[HSFacultyResponse])
async def list_faculties(
    current_user: User = Depends(require_permission("academic:read")),
    db: AsyncSession = Depends(get_db)
):
    """List all HS faculties for the school"""
    service = AcademicService(db)
    faculties = await service.list_faculties(current_user.school_id)
    return [
        HSFacultyResponse(
            id=f.id, name_en=f.name_en, name_np=f.name_np,
            code=f.code, description=f.description,
            is_active=f.is_active, max_students=f.max_students,
            streams=[
                HSStreamResponse(
                    id=s.id, faculty_id=s.faculty_id,
                    name_en=s.name_en, name_np=s.name_np,
                    code=s.code, is_active=s.is_active,
                )
                for s in f.streams
            ],
        )
        for f in faculties
    ]


@router.get("/faculties/{faculty_id}", response_model=HSFacultyResponse)
async def get_faculty(
    faculty_id: uuid.UUID,
    current_user: User = Depends(require_permission("academic:read")),
    db: AsyncSession = Depends(get_db)
):
    """Get faculty details with streams"""
    try:
        service = AcademicService(db)
        faculty = await service.get_faculty(faculty_id)
        return HSFacultyResponse(
            id=faculty.id, name_en=faculty.name_en, name_np=faculty.name_np,
            code=faculty.code, description=faculty.description,
            is_active=faculty.is_active, max_students=faculty.max_students,
            streams=[
                HSStreamResponse(
                    id=s.id, faculty_id=s.faculty_id,
                    name_en=s.name_en, name_np=s.name_np,
                    code=s.code, is_active=s.is_active,
                )
                for s in faculty.streams
            ],
        )
    except FacultyNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_response(str(e), "FACULTY_NOT_FOUND"))


# --- Streams ---

@router.post("/streams", response_model=HSStreamResponse, status_code=status.HTTP_201_CREATED)
async def create_stream(
    data: HSStreamCreate,
    current_user: User = Depends(require_permission("academic:create")),
    db: AsyncSession = Depends(get_db)
):
    """Create a stream within a faculty"""
    service = AcademicService(db)
    stream = await service.create_stream(data, current_user.school_id)
    return HSStreamResponse(
        id=stream.id, faculty_id=stream.faculty_id,
        name_en=stream.name_en, name_np=stream.name_np,
        code=stream.code, is_active=stream.is_active,
    )
