"""Attendance schemas"""
from services.attendance.schemas.attendance import (
    AttendanceEntryRequest,
    AttendanceMarkRequest,
    AttendanceUpdateRequest,
    AttendanceResponse,
    AttendanceListResponse,
    AttendanceSummaryResponse,
    MonthlyReportResponse,
    StudentAttendanceResponse,
)

__all__ = [
    "AttendanceEntryRequest",
    "AttendanceMarkRequest",
    "AttendanceUpdateRequest",
    "AttendanceResponse",
    "AttendanceListResponse",
    "AttendanceSummaryResponse",
    "MonthlyReportResponse",
    "StudentAttendanceResponse",
]
