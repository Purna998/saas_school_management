"""
Nepal School Management System - Staff API Routes
Staff management endpoints
"""

import uuid
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response, paginated_response
from shared.utils.exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
)
from services.auth.dependencies.auth import (
    get_current_active_user,
    require_permission,
)
from services.auth.models.user import User
from services.staff.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    StaffResponse,
    StaffListResponse,
    LeaveRequestCreate,
    LeaveResponse,
    StaffAttendanceMarkRequest,
    StaffAttendanceResponse,
    AttendanceSummary,
)
from services.staff.services.staff_service import StaffService

router = APIRouter()


def _staff_to_response(staff) -> StaffResponse:
    """Convert staff model to response schema"""
    return StaffResponse(
        id=staff.id,
        school_id=staff.school_id,
        user_id=staff.user_id,
        employee_id=staff.employee_id,
        full_name_en=staff.full_name_en,
        full_name_np=staff.full_name_np,
        gender=staff.gender.value,
        date_of_birth_ad=staff.date_of_birth_ad,
        date_of_birth_bs=staff.date_of_birth_bs,
        phone=staff.phone,
        email=staff.email,
        address=staff.address,
        photo_url=staff.photo_url,
        staff_type=staff.staff_type.value,
        designation=staff.designation,
        department=staff.department,
        qualification=staff.qualification,
        tsc_number=staff.tsc_number,
        joined_date_ad=staff.joined_date_ad,
        joined_date_bs=staff.joined_date_bs,
        status=staff.status.value,
        salary=staff.salary,
        created_at=staff.created_at,
        updated_at=staff.updated_at,
    )


def _leave_to_response(leave) -> LeaveResponse:
    """Convert leave model to response schema"""
    return LeaveResponse(
        id=leave.id,
        school_id=leave.school_id,
        staff_id=leave.staff_id,
        leave_type=leave.leave_type.value,
        start_date_ad=leave.start_date_ad,
        end_date_ad=leave.end_date_ad,
        days=leave.days,
        reason=leave.reason,
        status=leave.status.value,
        approved_by=leave.approved_by,
        created_at=leave.created_at,
        updated_at=leave.updated_at,
    )


def _attendance_to_response(attendance) -> StaffAttendanceResponse:
    """Convert attendance model to response schema"""
    return StaffAttendanceResponse(
        id=attendance.id,
        school_id=attendance.school_id,
        staff_id=attendance.staff_id,
        date_ad=attendance.date_ad,
        date_bs=attendance.date_bs,
        status=attendance.status.value,
        check_in_time=attendance.check_in_time,
        check_out_time=attendance.check_out_time,
        created_at=attendance.created_at,
    )


# ============ Staff CRUD Endpoints ============

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_staff(
    staff_data: StaffCreate,
    current_user: User = Depends(require_permission("staff:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new staff member.

    Requires: staff:create permission

    Status Codes:
        - 201: Staff created successfully
        - 409: Duplicate TSC number
        - 400: Invalid TSC number format
    """
    try:
        service = StaffService(db)
        staff = await service.create_staff(
            data=staff_data,
            school_id=current_user.school_id,
        )
        return success_response(data=_staff_to_response(staff).model_dump(mode="json"))

    except DuplicateRecordError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(str(e), "DUPLICATE_TSC_NUMBER"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_TSC_FORMAT"),
        )


@router.get("/")
async def list_staff(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None, description="Search by name, employee ID, or TSC number"),
    department: Optional[str] = Query(default=None, description="Filter by department"),
    designation: Optional[str] = Query(default=None, description="Filter by designation"),
    staff_type: Optional[str] = Query(default=None, description="Filter by staff type"),
    staff_status: Optional[str] = Query(default=None, alias="status", description="Filter by status"),
    current_user: User = Depends(require_permission("staff:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    List staff members with pagination and filters.

    Requires: staff:read permission

    Filters:
        - search: Name, employee ID, or TSC number
        - department: Exact department match
        - designation: Exact designation match
        - staff_type: teaching, non_teaching, administrative
        - status: active, on_leave, resigned, retired, terminated
    """
    service = StaffService(db)
    staff_list, total = await service.list_staff(
        school_id=current_user.school_id,
        page=page,
        limit=limit,
        search=search,
        department=department,
        designation=designation,
        staff_type=staff_type,
        status_filter=staff_status,
    )

    return paginated_response(
        data=[_staff_to_response(s).model_dump(mode="json") for s in staff_list],
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/{staff_id}")
async def get_staff(
    staff_id: uuid.UUID,
    current_user: User = Depends(require_permission("staff:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get staff member details by ID.

    Requires: staff:read permission

    Status Codes:
        - 200: Success
        - 404: Staff not found
    """
    try:
        service = StaffService(db)
        staff = await service.get_staff(staff_id)
        return success_response(data=_staff_to_response(staff).model_dump(mode="json"))

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STAFF_NOT_FOUND"),
        )


@router.patch("/{staff_id}")
async def update_staff(
    staff_id: uuid.UUID,
    staff_data: StaffUpdate,
    current_user: User = Depends(require_permission("staff:update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update staff member details.

    Requires: staff:update permission

    Status Codes:
        - 200: Updated successfully
        - 404: Staff not found
        - 409: Duplicate TSC number
        - 400: Invalid data
    """
    try:
        service = StaffService(db)
        staff = await service.update_staff(
            staff_id=staff_id,
            data=staff_data,
            school_id=current_user.school_id,
        )
        return success_response(data=_staff_to_response(staff).model_dump(mode="json"))

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STAFF_NOT_FOUND"),
        )
    except DuplicateRecordError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(str(e), "DUPLICATE_TSC_NUMBER"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_DATA"),
        )


# ============ Leave Management Endpoints ============

@router.post("/leave", status_code=status.HTTP_201_CREATED)
async def request_leave(
    leave_data: LeaveRequestCreate,
    current_user: User = Depends(require_permission("staff:leave:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Request leave for a staff member.

    Requires: staff:leave:create permission

    Status Codes:
        - 201: Leave request created
        - 404: Staff not found
        - 400: Invalid date range
    """
    try:
        service = StaffService(db)
        leave = await service.request_leave(
            data=leave_data,
            school_id=current_user.school_id,
        )
        return success_response(data=_leave_to_response(leave).model_dump(mode="json"))

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STAFF_NOT_FOUND"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_LEAVE_REQUEST"),
        )


@router.patch("/leave/{leave_id}/approve")
async def approve_leave(
    leave_id: uuid.UUID,
    current_user: User = Depends(require_permission("staff:leave:approve")),
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a pending leave request.

    Requires: staff:leave:approve permission

    Status Codes:
        - 200: Leave approved
        - 404: Leave not found
        - 400: Leave already processed
    """
    try:
        service = StaffService(db)
        leave = await service.approve_leave(
            leave_id=leave_id,
            approved_by=current_user.id,
        )
        return success_response(data=_leave_to_response(leave).model_dump(mode="json"))

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "LEAVE_NOT_FOUND"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "LEAVE_ALREADY_PROCESSED"),
        )


@router.patch("/leave/{leave_id}/reject")
async def reject_leave(
    leave_id: uuid.UUID,
    current_user: User = Depends(require_permission("staff:leave:approve")),
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a pending leave request.

    Requires: staff:leave:approve permission

    Status Codes:
        - 200: Leave rejected
        - 404: Leave not found
        - 400: Leave already processed
    """
    try:
        service = StaffService(db)
        leave = await service.reject_leave(
            leave_id=leave_id,
            rejected_by=current_user.id,
        )
        return success_response(data=_leave_to_response(leave).model_dump(mode="json"))

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "LEAVE_NOT_FOUND"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "LEAVE_ALREADY_PROCESSED"),
        )


# ============ Attendance Endpoints ============

@router.post("/attendance/mark", status_code=status.HTTP_201_CREATED)
async def mark_staff_attendance(
    attendance_data: StaffAttendanceMarkRequest,
    current_user: User = Depends(require_permission("staff:attendance:mark")),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark attendance for multiple staff members (batch operation).

    Requires: staff:attendance:mark permission

    If attendance already exists for a staff member on the given date,
    it will be updated instead of creating a duplicate.

    Status Codes:
        - 201: Attendance marked successfully
    """
    service = StaffService(db)
    records = await service.mark_staff_attendance(
        data=attendance_data,
        school_id=current_user.school_id,
    )

    return success_response(
        data={
            "marked": len(records),
            "date_ad": str(attendance_data.date_ad),
            "date_bs": attendance_data.date_bs,
            "records": [_attendance_to_response(r).model_dump(mode="json") for r in records],
        }
    )


@router.get("/{staff_id}/attendance")
async def get_staff_attendance(
    staff_id: uuid.UUID,
    start_date: Optional[date] = Query(default=None, description="Start date filter (AD)"),
    end_date: Optional[date] = Query(default=None, description="End date filter (AD)"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(require_permission("staff:attendance:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get attendance records for a specific staff member.

    Requires: staff:attendance:read permission

    Status Codes:
        - 200: Success
        - 404: Staff not found
    """
    try:
        service = StaffService(db)
        records, total = await service.get_staff_attendance(
            staff_id=staff_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            limit=limit,
        )

        return paginated_response(
            data=[_attendance_to_response(r).model_dump(mode="json") for r in records],
            page=page,
            limit=limit,
            total=total,
        )

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STAFF_NOT_FOUND"),
        )


@router.get("/{staff_id}/attendance/summary")
async def get_staff_attendance_summary(
    staff_id: uuid.UUID,
    start_date: date = Query(..., description="Summary period start date (AD)"),
    end_date: date = Query(..., description="Summary period end date (AD)"),
    current_user: User = Depends(require_permission("staff:attendance:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get attendance summary for a staff member over a date range.

    Requires: staff:attendance:read permission

    Status Codes:
        - 200: Success with summary data
        - 404: Staff not found
    """
    try:
        service = StaffService(db)
        summary = await service.get_staff_attendance_summary(
            staff_id=staff_id,
            start_date=start_date,
            end_date=end_date,
        )

        return success_response(data=summary)

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "STAFF_NOT_FOUND"),
        )
