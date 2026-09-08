"""
Nepal School Management System - Student API Routes
Student management endpoints
"""

import asyncio
import uuid
import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import (
    StudentNotFoundError,
    DuplicateEMISError,
)
from services.auth.dependencies.auth import (
    get_current_active_user,
    require_permission,
)
from services.auth.models.user import User
from services.student.schemas.student import (
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    StudentListResponse,
    GuardianResponse,
    BulkImportResponse,
)
from services.student.services.student_service import StudentService

router = APIRouter()


def _student_to_response(student, *, include_guardians: bool = True) -> StudentResponse:
    """Convert student model to response schema"""
    return StudentResponse(
        id=student.id,
        emis_student_id=student.emis_student_id,
        admission_number=student.admission_number,
        roll_number=student.roll_number,
        full_name_en=student.full_name_en,
        full_name_np=student.full_name_np,
        gender=student.gender.value,
        date_of_birth_ad=student.date_of_birth_ad,
        date_of_birth_bs=student.date_of_birth_bs,
        phone=student.phone,
        email=student.email,
        address_permanent=student.address_permanent,
        address_temporary=student.address_temporary,
        current_grade=student.current_grade,
        current_section=student.current_section,
        current_faculty=student.current_faculty,
        caste_ethnicity=student.caste_ethnicity.value if student.caste_ethnicity else None,
        religion=student.religion,
        mother_tongue=student.mother_tongue,
        nationality=student.nationality,
        disability_type=student.disability_type,
        status=student.status.value,
        photo_url=student.photo_url,
        school_id=student.school_id,
        guardians=[
            GuardianResponse(
                id=g.id,
                relation=g.relation.value,
                full_name_en=g.full_name_en,
                full_name_np=g.full_name_np,
                phone=g.phone,
                email=g.email,
                occupation=g.occupation,
                is_primary_contact=g.is_primary_contact,
            )
            for g in (student.guardians or [])
        ] if include_guardians else [],
        created_at=student.created_at,
        updated_at=student.updated_at,
    )


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
    student_data: StudentCreate,
    current_user: User = Depends(require_permission("student:create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Add a new student.

    Requires: student:create permission

    Status Codes:
        - 201: Student created
        - 409: Duplicate EMIS ID
    """
    try:
        service = StudentService(db)
        student = await service.create_student(
            data=student_data,
            school_id=current_user.school_id,
        )
        # Reload with relationships
        student = await service.get_student(student.id, current_user.school_id)
        return _student_to_response(student)

    except DuplicateEMISError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(str(e), "DUPLICATE_EMIS_ID"),
        )


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
    student_id: uuid.UUID,
    current_user: User = Depends(require_permission("student:read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Get student details by ID.

    Requires: student:read permission

    Status Codes:
        - 200: Success
        - 404: Student not found
    """
    try:
        service = StudentService(db)
        student = await service.get_student(student_id, current_user.school_id)
        return _student_to_response(student)

    except StudentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STUDENT_NOT_FOUND"),
        )


@router.patch("/{student_id}", response_model=StudentResponse)
async def update_student(
    student_id: uuid.UUID,
    student_data: StudentUpdate,
    current_user: User = Depends(require_permission("student:update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Update student details.

    Requires: student:update permission

    Status Codes:
        - 200: Updated
        - 404: Student not found
    """
    try:
        service = StudentService(db)
        student = await service.update_student(student_id, student_data, current_user.school_id)
        student = await service.get_student(student.id, current_user.school_id)
        return _student_to_response(student)

    except StudentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STUDENT_NOT_FOUND"),
        )


@router.delete("/{student_id}")
async def delete_student(
    student_id: uuid.UUID,
    current_user: User = Depends(require_permission("student:delete")),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a student.

    Requires: student:delete permission

    Status Codes:
        - 200: Deleted
        - 404: Student not found
    """
    try:
        service = StudentService(db)
        await service.delete_student(student_id, current_user.school_id)
        return success_response(data={"message": "Student deleted successfully"})

    except StudentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STUDENT_NOT_FOUND"),
        )


@router.get("", response_model=StudentListResponse)
async def list_students(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    grade: Optional[int] = Query(default=None, ge=1, le=12),
    section: Optional[str] = Query(default=None),
    student_status: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(require_permission("student:read")),
    db: AsyncSession = Depends(get_db)
):
    """
    List students with pagination and filters.

    Requires: student:read permission

    Status Codes:
        - 200: Success
    """
    from services.student.models.student import StudentStatus as SS

    service = StudentService(db)
    status_enum = SS(student_status) if student_status else None

    students, total = await service.list_students(
        school_id=current_user.school_id,
        page=page,
        limit=limit,
        search=search,
        grade=grade,
        section=section,
        status_filter=status_enum,
    )

    return StudentListResponse(
        # List views do not use guardian details. Avoid both the relationship
        # query and the extra response payload; details still include them.
        students=[_student_to_response(s, include_guardians=False) for s in students],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/search")
async def search_students(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(require_permission("student:read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Quick search students by name or ID.

    Status Codes:
        - 200: Success
    """
    service = StudentService(db)
    students = await service.search_students(
        school_id=current_user.school_id,
        query_str=q,
        limit=limit,
    )

    return success_response(data={
        "students": [_student_to_response(s) for s in students],
        "total": len(students),
    })


@router.post("/bulk-import", response_model=BulkImportResponse)
async def bulk_import_students(
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("student:create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk import students from CSV file.

    CSV should have columns: full_name_en, gender, date_of_birth_ad, current_grade, current_section

    Requires: student:create permission

    Status Codes:
        - 200: Import complete (with summary)
        - 400: Invalid file format
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Only CSV files are supported", "INVALID_FILE_TYPE"),
        )

    contents = await file.read()
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(text))
    students_data = []

    for row in reader:
        student_dict = {
            "full_name_en": row.get("full_name_en", "").strip(),
            "gender": row.get("gender", "").strip().lower(),
            "date_of_birth_ad": row.get("date_of_birth_ad", "").strip(),
            "current_grade": int(row.get("current_grade", 0)),
            "current_section": row.get("current_section", "").strip() or None,
            "full_name_np": row.get("full_name_np", "").strip() or None,
            "phone": row.get("phone", "").strip() or None,
            "roll_number": int(row["roll_number"]) if row.get("roll_number") else None,
            "emis_student_id": row.get("emis_student_id", "").strip() or None,
            "admission_number": row.get("admission_number", "").strip() or None,
            "caste_ethnicity": row.get("caste_ethnicity", "").strip() or None,
        }
        if student_dict["full_name_en"] and student_dict["current_grade"]:
            students_data.append(student_dict)

    service = StudentService(db)
    result = await service.bulk_import(
        school_id=current_user.school_id,
        students_data=students_data,
    )

    return BulkImportResponse(**result)


@router.post("/{student_id}/upload-photo")
async def upload_student_photo(
    student_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(require_permission("student:update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload student photo.

    Status Codes:
        - 200: Photo uploaded
        - 400: Invalid file
        - 404: Student not found
    """
    import os
    from shared.config.settings import settings

    service = StudentService(db)
        student = await service.get_student(student_id, current_user.school_id)

    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("Invalid file type. Allowed: JPEG, PNG", "INVALID_FILE_TYPE"),
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=error_response(f"File size exceeds {settings.max_upload_size_mb}MB limit", "FILE_SIZE_EXCEEDED"),
        )

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    upload_dir = os.path.join("uploads", "photos", "students", str(student.school_id))
    filename = f"{student.id}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    def write_photo() -> None:
        os.makedirs(upload_dir, exist_ok=True)
        with open(filepath, "wb") as destination:
            destination.write(contents)

    await asyncio.to_thread(write_photo)

    photo_url = f"/uploads/photos/students/{student.school_id}/{filename}"
    student.photo_url = photo_url
    await db.commit()

    return success_response(data={"photo_url": photo_url})
