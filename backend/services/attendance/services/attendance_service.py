"""
Nepal School Management System - Attendance Service
Business logic for attendance management
"""

import logging
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.attendance.models.attendance import Attendance, AttendanceStatus
from services.attendance.schemas.attendance import (
    AttendanceMarkRequest,
    AttendanceUpdateRequest,
    AttendanceResponse,
    AttendanceListResponse,
    AttendanceSummaryResponse,
    MonthlyReportResponse,
    DailySummary,
    StudentAttendanceResponse,
    StudentAttendanceRecord,
)

logger = logging.getLogger(__name__)


class AttendanceService:
    """Service class for attendance business logic"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def mark_attendance(
        self,
        school_id: UUID,
        data: AttendanceMarkRequest,
        marked_by: UUID,
    ) -> AttendanceListResponse:
        """
        Batch mark attendance for a class on a given date.

        Uses PostgreSQL upsert (INSERT ... ON CONFLICT UPDATE) to handle
        re-marking attendance for the same date (updating existing records).

        Args:
            school_id: School/tenant UUID
            data: Batch attendance request with entries
            marked_by: UUID of the user marking attendance

        Returns:
            AttendanceListResponse with all records for that class/date
        """
        records = []

        for entry in data.entries:
            # Use upsert pattern: insert or update on conflict
            stmt = pg_insert(Attendance).values(
                school_id=school_id,
                student_id=entry.student_id,
                grade=data.grade,
                section=data.section,
                date_bs=data.date_bs,
                date_ad=data.date_ad,
                status=AttendanceStatus(entry.status),
                marked_by=marked_by,
                remarks=entry.remarks,
                period_number=data.period_number,
            )

            # On conflict (same student + date + period), update the status
            stmt = stmt.on_conflict_do_update(
                constraint="uq_attendance_student_date_period",
                set_={
                    "status": stmt.excluded.status,
                    "marked_by": stmt.excluded.marked_by,
                    "remarks": stmt.excluded.remarks,
                },
            )

            await self.db.execute(stmt)

        # Flush to ensure all records are written
        await self.db.flush()

        # Fetch the complete attendance list for this class/date
        return await self.get_attendance_by_date(
            school_id=school_id,
            date_ad=data.date_ad,
            grade=data.grade,
            section=data.section,
            period_number=data.period_number,
        )

    async def get_attendance_by_date(
        self,
        school_id: UUID,
        date_ad: date,
        grade: str,
        section: str,
        period_number: Optional[int] = None,
    ) -> AttendanceListResponse:
        """
        Get attendance records for a specific class on a specific date.

        Args:
            school_id: School/tenant UUID
            date_ad: Gregorian date
            grade: Grade level
            section: Section name
            period_number: Optional period number for HS

        Returns:
            AttendanceListResponse with all records
        """
        conditions = [
            Attendance.school_id == school_id,
            Attendance.date_ad == date_ad,
            Attendance.grade == grade,
            Attendance.section == section,
        ]

        if period_number is not None:
            conditions.append(Attendance.period_number == period_number)
        else:
            conditions.append(Attendance.period_number.is_(None))

        query = (
            select(Attendance)
            .where(and_(*conditions))
            .order_by(Attendance.student_id)
        )

        result = await self.db.execute(query)
        attendance_records = result.scalars().all()

        records = [
            AttendanceResponse.model_validate(record)
            for record in attendance_records
        ]

        # Get date_bs from first record or default
        date_bs = records[0].date_bs if records else ""

        return AttendanceListResponse(
            date_bs=date_bs,
            date_ad=date_ad,
            grade=grade,
            section=section,
            period_number=period_number,
            total_students=len(records),
            records=records,
        )

    async def get_student_attendance(
        self,
        student_id: UUID,
        start_date: date,
        end_date: date,
        school_id: Optional[UUID] = None,
    ) -> StudentAttendanceResponse:
        """
        Get attendance history for a specific student within a date range.

        Args:
            student_id: Student UUID
            start_date: Start date (AD)
            end_date: End date (AD)
            school_id: Optional school filter for tenant isolation

        Returns:
            StudentAttendanceResponse with history and statistics
        """
        conditions = [
            Attendance.student_id == student_id,
            Attendance.date_ad >= start_date,
            Attendance.date_ad <= end_date,
        ]

        if school_id is not None:
            conditions.append(Attendance.school_id == school_id)

        query = (
            select(Attendance)
            .where(and_(*conditions))
            .order_by(Attendance.date_ad.desc())
        )

        result = await self.db.execute(query)
        attendance_records = result.scalars().all()

        # Build response records
        records = [
            StudentAttendanceRecord(
                id=record.id,
                date_bs=record.date_bs,
                date_ad=record.date_ad,
                status=record.status.value if isinstance(record.status, AttendanceStatus) else record.status,
                remarks=record.remarks,
                period_number=record.period_number,
            )
            for record in attendance_records
        ]

        # Calculate statistics
        total_days = len(records)
        present_count = sum(1 for r in records if r.status == "present")
        absent_count = sum(1 for r in records if r.status == "absent")
        late_count = sum(1 for r in records if r.status == "late")
        leave_count = sum(1 for r in records if r.status == "leave")

        # Attendance percentage: (present + late) / total * 100
        attendance_percentage = 0.0
        if total_days > 0:
            attended = present_count + late_count
            attendance_percentage = round((attended / total_days) * 100, 2)

        return StudentAttendanceResponse(
            student_id=student_id,
            start_date=start_date,
            end_date=end_date,
            total_days=total_days,
            present_count=present_count,
            absent_count=absent_count,
            late_count=late_count,
            leave_count=leave_count,
            attendance_percentage=attendance_percentage,
            records=records,
        )

    async def get_monthly_summary(
        self,
        school_id: UUID,
        grade: str,
        section: str,
        year_bs: int,
        month_bs: int,
    ) -> MonthlyReportResponse:
        """
        Get monthly attendance summary for a class.

        Aggregates daily attendance counts for each day of the specified
        BS month. Uses the date_bs field prefix to filter by BS year/month.

        Args:
            school_id: School/tenant UUID
            grade: Grade level
            section: Section name
            year_bs: Bikram Sambat year (e.g., 2081)
            month_bs: Bikram Sambat month (1-12)

        Returns:
            MonthlyReportResponse with daily summaries
        """
        # Build BS date prefix for the month (e.g., "2081-03")
        month_prefix = f"{year_bs}-{month_bs:02d}"

        # Query all attendance records for this class in the given BS month
        query = (
            select(Attendance)
            .where(
                and_(
                    Attendance.school_id == school_id,
                    Attendance.grade == grade,
                    Attendance.section == section,
                    Attendance.date_bs.like(f"{month_prefix}%"),
                )
            )
            .order_by(Attendance.date_ad)
        )

        result = await self.db.execute(query)
        all_records = result.scalars().all()

        # Group by date
        daily_data: dict[date, dict] = {}
        for record in all_records:
            record_date = record.date_ad
            if record_date not in daily_data:
                daily_data[record_date] = {
                    "date_bs": record.date_bs,
                    "date_ad": record_date,
                    "present_count": 0,
                    "absent_count": 0,
                    "late_count": 0,
                    "leave_count": 0,
                    "holiday_count": 0,
                    "total": 0,
                }

            status_value = (
                record.status.value
                if isinstance(record.status, AttendanceStatus)
                else record.status
            )
            daily_data[record_date][f"{status_value}_count"] += 1
            daily_data[record_date]["total"] += 1

        # Build daily summaries
        daily_summaries = [
            DailySummary(**day_info)
            for day_info in sorted(daily_data.values(), key=lambda x: x["date_ad"])
        ]

        # Calculate aggregate statistics
        total_school_days = len(daily_summaries)
        total_attendance_pct = 0.0

        if total_school_days > 0:
            total_present = sum(d.present_count for d in daily_summaries)
            total_late = sum(d.late_count for d in daily_summaries)
            total_students_all_days = sum(d.total for d in daily_summaries)

            if total_students_all_days > 0:
                total_attendance_pct = round(
                    ((total_present + total_late) / total_students_all_days) * 100, 2
                )

        return MonthlyReportResponse(
            school_id=school_id,
            grade=grade,
            section=section,
            year_bs=year_bs,
            month_bs=month_bs,
            total_school_days=total_school_days,
            average_attendance_percentage=total_attendance_pct,
            daily_summaries=daily_summaries,
        )

    async def get_attendance_summary_by_date(
        self,
        school_id: UUID,
        date_ad: date,
        grade: str,
        section: str,
    ) -> AttendanceSummaryResponse:
        """
        Get attendance summary (counts) for a specific class on a specific date.

        Args:
            school_id: School/tenant UUID
            date_ad: Gregorian date
            grade: Grade level
            section: Section name

        Returns:
            AttendanceSummaryResponse with status counts
        """
        # Use aggregate query for efficiency
        query = (
            select(
                Attendance.status,
                func.count(Attendance.id).label("count"),
            )
            .where(
                and_(
                    Attendance.school_id == school_id,
                    Attendance.date_ad == date_ad,
                    Attendance.grade == grade,
                    Attendance.section == section,
                )
            )
            .group_by(Attendance.status)
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Initialize counts
        counts = {
            "present_count": 0,
            "absent_count": 0,
            "late_count": 0,
            "leave_count": 0,
            "holiday_count": 0,
        }

        total = 0
        for row in rows:
            status_value = (
                row.status.value
                if isinstance(row.status, AttendanceStatus)
                else row.status
            )
            counts[f"{status_value}_count"] = row.count
            total += row.count

        # Get date_bs from a record
        date_bs_query = (
            select(Attendance.date_bs)
            .where(
                and_(
                    Attendance.school_id == school_id,
                    Attendance.date_ad == date_ad,
                    Attendance.grade == grade,
                    Attendance.section == section,
                )
            )
            .limit(1)
        )
        date_bs_result = await self.db.execute(date_bs_query)
        date_bs_value = date_bs_result.scalar_one_or_none()

        return AttendanceSummaryResponse(
            date_bs=date_bs_value,
            date_ad=date_ad,
            grade=grade,
            section=section,
            total=total,
            **counts,
        )

    async def update_attendance(
        self,
        attendance_id: UUID,
        school_id: UUID,
        data: AttendanceUpdateRequest,
        updated_by: UUID,
    ) -> Optional[AttendanceResponse]:
        """
        Update a single attendance record.

        Args:
            attendance_id: Attendance record UUID
            school_id: School/tenant UUID for isolation
            data: Update data
            updated_by: UUID of the user making the update

        Returns:
            Updated AttendanceResponse or None if not found
        """
        query = select(Attendance).where(
            and_(
                Attendance.id == attendance_id,
                Attendance.school_id == school_id,
            )
        )

        result = await self.db.execute(query)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        # Update fields if provided
        if data.status is not None:
            record.status = AttendanceStatus(data.status)
        if data.remarks is not None:
            record.remarks = data.remarks

        # Track who updated (uses the marked_by field)
        record.marked_by = updated_by

        await self.db.flush()

        return AttendanceResponse.model_validate(record)
