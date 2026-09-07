"""
Nepal School Management System - Staff Service
Staff management business logic
"""

import re
import uuid
import logging
from typing import Optional, List, Tuple
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from shared.utils.exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
)
from services.staff.models.staff import (
    Staff,
    StaffLeave,
    StaffAttendance,
    StaffType,
    StaffStatus,
    Gender,
    LeaveType,
    LeaveStatus,
    AttendanceStatus,
)
from services.staff.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    LeaveRequestCreate,
    StaffAttendanceMarkRequest,
)

logger = logging.getLogger(__name__)

# TSC number format: TSC-XXXXX (5 digits)
TSC_NUMBER_PATTERN = re.compile(r"^TSC-\d{5}$")


class StaffService:
    """Staff management service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ============ Staff CRUD ============

    async def create_staff(
        self,
        data: StaffCreate,
        school_id: uuid.UUID,
    ) -> Staff:
        """
        Create a new staff member.

        Args:
            data: Staff creation data
            school_id: School/tenant UUID

        Returns:
            Created Staff object

        Raises:
            DuplicateRecordError: If TSC number already exists in school
        """
        # Validate and check TSC number
        if data.tsc_number:
            await self.validate_tsc_number(data.tsc_number, school_id)

        staff = Staff(
            id=uuid.uuid4(),
            school_id=school_id,
            user_id=data.user_id,
            employee_id=data.employee_id,
            full_name_en=data.full_name_en,
            full_name_np=data.full_name_np,
            gender=Gender(data.gender),
            date_of_birth_ad=data.date_of_birth_ad,
            date_of_birth_bs=data.date_of_birth_bs,
            phone=data.phone,
            email=data.email,
            address=data.address,
            photo_url=data.photo_url,
            staff_type=StaffType(data.staff_type),
            designation=data.designation,
            department=data.department,
            qualification=data.qualification,
            tsc_number=data.tsc_number,
            joined_date_ad=data.joined_date_ad,
            joined_date_bs=data.joined_date_bs,
            salary=data.salary,
            status=StaffStatus.ACTIVE,
        )

        self.db.add(staff)
        await self.db.commit()
        await self.db.refresh(staff)

        logger.info(f"Staff created: {staff.full_name_en} (ID: {staff.id})")
        return staff

    async def get_staff(self, staff_id: uuid.UUID) -> Staff:
        """Get staff member by ID"""
        result = await self.db.execute(
            select(Staff)
            .where(Staff.id == staff_id, Staff.is_deleted == False)
            .options(selectinload(Staff.leaves))
        )
        staff = result.scalar_one_or_none()

        if not staff:
            raise RecordNotFoundError(f"Staff member with ID {staff_id} not found")

        return staff

    async def update_staff(self, staff_id: uuid.UUID, data: StaffUpdate, school_id: uuid.UUID) -> Staff:
        """Update staff member details"""
        staff = await self.get_staff(staff_id)

        update_fields = data.model_dump(exclude_unset=True)

        # Validate TSC number if being updated
        if "tsc_number" in update_fields and update_fields["tsc_number"]:
            await self.validate_tsc_number(
                update_fields["tsc_number"],
                school_id,
                exclude_staff_id=staff_id
            )

        for field, value in update_fields.items():
            if value is not None:
                if field == "status":
                    setattr(staff, field, StaffStatus(value))
                elif field == "staff_type":
                    setattr(staff, field, StaffType(value))
                else:
                    setattr(staff, field, value)

        await self.db.commit()
        await self.db.refresh(staff)

        logger.info(f"Staff updated: {staff.full_name_en}")
        return staff

    async def list_staff(
        self,
        school_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        department: Optional[str] = None,
        designation: Optional[str] = None,
        staff_type: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> Tuple[List[Staff], int]:
        """List staff members with pagination and filters"""
        query = select(Staff).where(
            Staff.school_id == school_id,
            Staff.is_deleted == False,
        )

        if search:
            pattern = f"%{search}%"
            query = query.where(
                (Staff.full_name_en.ilike(pattern)) |
                (Staff.full_name_np.ilike(pattern)) |
                (Staff.employee_id.ilike(pattern)) |
                (Staff.tsc_number.ilike(pattern))
            )

        if department:
            query = query.where(Staff.department == department)

        if designation:
            query = query.where(Staff.designation == designation)

        if staff_type:
            query = query.where(Staff.staff_type == StaffType(staff_type))

        if status_filter:
            query = query.where(Staff.status == StaffStatus(status_filter))

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        query = query.order_by(Staff.full_name_en)

        result = await self.db.execute(query)
        staff_list = result.scalars().all()

        return staff_list, total

    # ============ TSC Validation ============

    async def validate_tsc_number(
        self,
        tsc_number: str,
        school_id: uuid.UUID,
        exclude_staff_id: Optional[uuid.UUID] = None,
    ) -> bool:
        """
        Validate TSC number format and uniqueness within school.

        Format: TSC-XXXXX (TSC- followed by 5 digits)

        Args:
            tsc_number: TSC number to validate
            school_id: School UUID for uniqueness check
            exclude_staff_id: Staff ID to exclude (for updates)

        Returns:
            True if valid

        Raises:
            DuplicateRecordError: If TSC number already exists in school
            ValueError: If format is invalid
        """
        # Validate format
        if not TSC_NUMBER_PATTERN.match(tsc_number):
            raise ValueError(
                f"Invalid TSC number format: {tsc_number}. "
                "Expected format: TSC-XXXXX (e.g., TSC-12345)"
            )

        # Check uniqueness within school
        query = select(Staff).where(
            Staff.school_id == school_id,
            Staff.tsc_number == tsc_number,
            Staff.is_deleted == False,
        )

        if exclude_staff_id:
            query = query.where(Staff.id != exclude_staff_id)

        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            raise DuplicateRecordError(
                f"TSC number {tsc_number} is already assigned to "
                f"staff member: {existing.full_name_en}"
            )

        return True

    # ============ Leave Management ============

    async def request_leave(
        self,
        data: LeaveRequestCreate,
        school_id: uuid.UUID,
    ) -> StaffLeave:
        """
        Create a leave request for a staff member.

        Args:
            data: Leave request data
            school_id: School/tenant UUID

        Returns:
            Created StaffLeave object
        """
        # Verify staff exists
        await self.get_staff(data.staff_id)

        # Calculate days
        days = (data.end_date_ad - data.start_date_ad).days + 1
        if days <= 0:
            raise ValueError("End date must be after or equal to start date")

        leave = StaffLeave(
            id=uuid.uuid4(),
            school_id=school_id,
            staff_id=data.staff_id,
            leave_type=LeaveType(data.leave_type),
            start_date_ad=data.start_date_ad,
            end_date_ad=data.end_date_ad,
            days=days,
            reason=data.reason,
            status=LeaveStatus.PENDING,
        )

        self.db.add(leave)
        await self.db.commit()
        await self.db.refresh(leave)

        logger.info(f"Leave requested: Staff {data.staff_id}, {days} days ({data.leave_type})")
        return leave

    async def approve_leave(
        self,
        leave_id: uuid.UUID,
        approved_by: uuid.UUID,
    ) -> StaffLeave:
        """
        Approve a pending leave request.

        Args:
            leave_id: Leave request ID
            approved_by: User ID of approver

        Returns:
            Updated StaffLeave object
        """
        result = await self.db.execute(
            select(StaffLeave).where(StaffLeave.id == leave_id)
        )
        leave = result.scalar_one_or_none()

        if not leave:
            raise RecordNotFoundError(f"Leave request with ID {leave_id} not found")

        if leave.status != LeaveStatus.PENDING:
            raise ValueError(f"Leave request is already {leave.status.value}")

        leave.status = LeaveStatus.APPROVED
        leave.approved_by = approved_by

        await self.db.commit()
        await self.db.refresh(leave)

        logger.info(f"Leave approved: {leave_id} by {approved_by}")
        return leave

    async def reject_leave(
        self,
        leave_id: uuid.UUID,
        rejected_by: uuid.UUID,
    ) -> StaffLeave:
        """
        Reject a pending leave request.

        Args:
            leave_id: Leave request ID
            rejected_by: User ID of rejector

        Returns:
            Updated StaffLeave object
        """
        result = await self.db.execute(
            select(StaffLeave).where(StaffLeave.id == leave_id)
        )
        leave = result.scalar_one_or_none()

        if not leave:
            raise RecordNotFoundError(f"Leave request with ID {leave_id} not found")

        if leave.status != LeaveStatus.PENDING:
            raise ValueError(f"Leave request is already {leave.status.value}")

        leave.status = LeaveStatus.REJECTED
        leave.approved_by = rejected_by

        await self.db.commit()
        await self.db.refresh(leave)

        logger.info(f"Leave rejected: {leave_id} by {rejected_by}")
        return leave

    # ============ Attendance Management ============

    async def mark_staff_attendance(
        self,
        data: StaffAttendanceMarkRequest,
        school_id: uuid.UUID,
    ) -> List[StaffAttendance]:
        """
        Mark attendance for multiple staff members (batch operation).

        Args:
            data: Batch attendance data
            school_id: School/tenant UUID

        Returns:
            List of created/updated StaffAttendance records
        """
        records = []

        for entry in data.attendances:
            # Check if attendance already exists for this staff on this date
            result = await self.db.execute(
                select(StaffAttendance).where(
                    StaffAttendance.school_id == school_id,
                    StaffAttendance.staff_id == entry.staff_id,
                    StaffAttendance.date_ad == data.date_ad,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing record
                existing.status = AttendanceStatus(entry.status)
                existing.check_in_time = entry.check_in_time
                existing.check_out_time = entry.check_out_time
                existing.date_bs = data.date_bs
                records.append(existing)
            else:
                # Create new record
                attendance = StaffAttendance(
                    id=uuid.uuid4(),
                    school_id=school_id,
                    staff_id=entry.staff_id,
                    date_ad=data.date_ad,
                    date_bs=data.date_bs,
                    status=AttendanceStatus(entry.status),
                    check_in_time=entry.check_in_time,
                    check_out_time=entry.check_out_time,
                )
                self.db.add(attendance)
                records.append(attendance)

        await self.db.commit()

        # Refresh all records
        for record in records:
            await self.db.refresh(record)

        logger.info(
            f"Attendance marked: {len(records)} staff for {data.date_ad}"
        )
        return records

    async def get_staff_attendance(
        self,
        staff_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        limit: int = 30,
    ) -> Tuple[List[StaffAttendance], int]:
        """
        Get attendance records for a staff member.

        Args:
            staff_id: Staff member ID
            start_date: Filter start date (inclusive)
            end_date: Filter end date (inclusive)
            page: Page number
            limit: Records per page

        Returns:
            Tuple of (attendance records, total count)
        """
        # Verify staff exists
        await self.get_staff(staff_id)

        query = select(StaffAttendance).where(
            StaffAttendance.staff_id == staff_id
        )

        if start_date:
            query = query.where(StaffAttendance.date_ad >= start_date)

        if end_date:
            query = query.where(StaffAttendance.date_ad <= end_date)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        query = query.order_by(StaffAttendance.date_ad.desc())

        result = await self.db.execute(query)
        attendances = result.scalars().all()

        return attendances, total

    async def get_staff_attendance_summary(
        self,
        staff_id: uuid.UUID,
        start_date: date,
        end_date: date,
    ) -> dict:
        """
        Get attendance summary for a staff member over a date range.

        Args:
            staff_id: Staff member ID
            start_date: Summary period start date
            end_date: Summary period end date

        Returns:
            Attendance summary dictionary
        """
        staff = await self.get_staff(staff_id)

        # Get all attendance records in range
        result = await self.db.execute(
            select(StaffAttendance).where(
                StaffAttendance.staff_id == staff_id,
                StaffAttendance.date_ad >= start_date,
                StaffAttendance.date_ad <= end_date,
            )
        )
        records = result.scalars().all()

        # Calculate summary
        total_days = len(records)
        present = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        late = sum(1 for r in records if r.status == AttendanceStatus.LATE)
        half_day = sum(1 for r in records if r.status == AttendanceStatus.HALF_DAY)
        on_leave = sum(1 for r in records if r.status == AttendanceStatus.LEAVE)

        attendance_percentage = (
            round(((present + late + half_day * 0.5) / total_days) * 100, 2)
            if total_days > 0
            else 0.0
        )

        return {
            "staff_id": staff_id,
            "staff_name": staff.full_name_en,
            "total_days": total_days,
            "present": present,
            "absent": absent,
            "late": late,
            "half_day": half_day,
            "on_leave": on_leave,
            "attendance_percentage": attendance_percentage,
        }
