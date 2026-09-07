"""
Nepal School Management System - Attendance API Endpoints
REST API for attendance management
"""

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from services.auth.dependencies.auth import get_current_active_user, require_permission
from services.attendance.schemas.attendance import (
    AttendanceMarkRequest,
    AttendanceUpdateRequest,
)
from services.attendance.services.attendance_service import AttendanceService

router = APIRouter()


@router.post(
    "/mark",
    summary="Batch mark attendance",
    description="Mark attendance for an entire class (grade + section) on a given date. "
    "Supports upsert - re-marking will update existing records.",
    dependencies=[Depends(require_permission("attendance:create"))],
)
async def mark_attendance(
    data: AttendanceMarkRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch mark attendance for a class.

    Required permission: attendance:create

    - Marks all students in the entries list for the given date/class
    - If attendance already exists for a student on that date, it will be updated
    - Supports period-based attendance for Higher Secondary (Grade 11-12)
    """
    service = AttendanceService(db)

    # Use school_id from the authenticated user's token
    school_id = current_user._token_info.get("school_id")
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message="School context not found in token",
                code="MISSING_SCHOOL_CONTEXT",
            ),
        )

    result = await service.mark_attendance(
        school_id=UUID(school_id) if isinstance(school_id, str) else school_id,
        data=data,
        marked_by=current_user.id,
    )

    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/date",
    summary="Get attendance by date",
    description="Get attendance records for a specific class on a specific date.",
    dependencies=[Depends(require_permission("attendance:read"))],
)
async def get_attendance_by_date(
    date_ad: date = Query(..., description="Gregorian date (YYYY-MM-DD)"),
    grade: str = Query(..., description="Grade level (e.g., '5', '10')"),
    section: str = Query(..., description="Section (e.g., 'A', 'B')"),
    period_number: Optional[int] = Query(
        default=None,
        ge=1,
        le=8,
        description="Period number for HS (1-8)",
    ),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get attendance for a specific date, grade, and section.

    Required permission: attendance:read
    """
    service = AttendanceService(db)

    school_id = current_user._token_info.get("school_id")
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message="School context not found in token",
                code="MISSING_SCHOOL_CONTEXT",
            ),
        )

    result = await service.get_attendance_by_date(
        school_id=UUID(school_id) if isinstance(school_id, str) else school_id,
        date_ad=date_ad,
        grade=grade,
        section=section,
        period_number=period_number,
    )

    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/student/{student_id}",
    summary="Get student attendance history",
    description="Get attendance history for a specific student within a date range.",
    dependencies=[Depends(require_permission("attendance:read"))],
)
async def get_student_attendance(
    student_id: UUID,
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get attendance history for a specific student.

    Required permission: attendance:read

    Returns attendance records and summary statistics for the given date range.
    """
    service = AttendanceService(db)

    school_id = current_user._token_info.get("school_id")
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message="School context not found in token",
                code="MISSING_SCHOOL_CONTEXT",
            ),
        )

    # Validate date range
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message="start_date must be before or equal to end_date",
                code="INVALID_DATE_RANGE",
            ),
        )

    result = await service.get_student_attendance(
        student_id=student_id,
        start_date=start_date,
        end_date=end_date,
        school_id=UUID(school_id) if isinstance(school_id, str) else school_id,
    )

    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/summary",
    summary="Get monthly attendance summary",
    description="Get monthly attendance summary for a class with daily breakdowns.",
    dependencies=[Depends(require_permission("attendance:read"))],
)
async def get_monthly_summary(
    grade: str = Query(..., description="Grade level"),
    section: str = Query(..., description="Section"),
    year_bs: int = Query(..., ge=2000, le=2100, description="BS year (e.g., 2081)"),
    month_bs: int = Query(..., ge=1, le=12, description="BS month (1-12)"),
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get monthly attendance summary for a class.

    Required permission: attendance:read

    Returns daily attendance counts and average attendance percentage
    for the specified Bikram Sambat month.
    """
    service = AttendanceService(db)

    school_id = current_user._token_info.get("school_id")
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message="School context not found in token",
                code="MISSING_SCHOOL_CONTEXT",
            ),
        )

    result = await service.get_monthly_summary(
        school_id=UUID(school_id) if isinstance(school_id, str) else school_id,
        grade=grade,
        section=section,
        year_bs=year_bs,
        month_bs=month_bs,
    )

    return success_response(data=result.model_dump(mode="json"))


@router.patch(
    "/{attendance_id}",
    summary="Update single attendance record",
    description="Update status or remarks of a single attendance record.",
    dependencies=[Depends(require_permission("attendance:update"))],
)
async def update_attendance(
    attendance_id: UUID,
    data: AttendanceUpdateRequest,
    current_user=Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a single attendance record.

    Required permission: attendance:update

    Can update the status and/or remarks of an existing attendance record.
    """
    service = AttendanceService(db)

    school_id = current_user._token_info.get("school_id")
    if not school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message="School context not found in token",
                code="MISSING_SCHOOL_CONTEXT",
            ),
        )

    result = await service.update_attendance(
        attendance_id=attendance_id,
        school_id=UUID(school_id) if isinstance(school_id, str) else school_id,
        data=data,
        updated_by=current_user.id,
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                message=f"Attendance record {attendance_id} not found",
                code="ATTENDANCE_NOT_FOUND",
            ),
        )

    return success_response(data=result.model_dump(mode="json"))
