"""Architecture-level tests for the consolidated FastAPI application."""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from main import app
from services.attendance.models.attendance import Attendance, AttendanceStatus
from services.attendance.schemas.attendance import (
    AttendanceMarkRequest,
    AttendanceUpdateRequest,
)
from services.attendance.services.attendance_service import AttendanceService
from services.exam.models.exam import Division
from services.exam.schemas.exam import ExamCreate, MarkEntry
from services.exam.services.exam_service import calculate_division, calculate_grade_point
from shared.storage import LocalStorage


def test_all_domain_routes_are_registered_on_one_app():
    paths = {route.path for route in app.routes}
    expected_prefixes = {
        "/api/v1/auth",
        "/api/v1/tenants",
        "/api/v1/students",
        "/api/v1/academic",
        "/api/v1/attendance",
        "/api/v1/exams",
        "/api/v1/fees",
        "/api/v1/staff",
        "/api/v1/communication",
        "/api/v1/library",
        "/api/v1/transport",
        "/api/v1/hostel",
        "/api/v1/inventory",
        "/api/v1/reports",
        "/api/v1/notifications",
        "/api/v1/calendar",
    }

    for prefix in expected_prefixes:
        assert any(path == prefix or path.startswith(f"{prefix}/") for path in paths)


def test_system_routes_are_registered():
    paths = {route.path for route in app.routes}
    assert {"/", "/health", "/ready", "/docs", "/openapi.json"} <= paths


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/academic/grades/{grade_id:uuid}", "PATCH"),
        ("/api/v1/academic/grades/{grade_id:uuid}", "DELETE"),
        ("/api/v1/academic/sections/{section_id:uuid}", "PATCH"),
        ("/api/v1/academic/sections/{section_id:uuid}", "DELETE"),
        ("/api/v1/academic/subjects/{subject_id:uuid}", "PATCH"),
        ("/api/v1/academic/subjects/{subject_id:uuid}", "DELETE"),
        ("/api/v1/academic/faculties/{faculty_id:uuid}", "PATCH"),
        ("/api/v1/academic/faculties/{faculty_id:uuid}", "DELETE"),
        ("/api/v1/academic/streams/{stream_id:uuid}", "PATCH"),
        ("/api/v1/academic/streams/{stream_id:uuid}", "DELETE"),
    ],
)
def test_academic_crud_routes_are_registered(path, method):
    assert any(route.path == path and method in route.methods for route in app.routes)


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/attendance/mark", "POST"),
        ("/api/v1/attendance/date", "GET"),
        ("/api/v1/attendance/student/{student_id}", "GET"),
        ("/api/v1/attendance/summary", "GET"),
        ("/api/v1/attendance/{attendance_id}", "PATCH"),
    ],
)
def test_attendance_routes_are_registered(path, method):
    assert any(route.path == path and method in route.methods for route in app.routes)


def test_daily_attendance_has_a_partial_unique_index():
    index = next(
        candidate
        for candidate in Attendance.__table__.indexes
        if candidate.name == "uq_attendance_daily_student_date"
    )
    assert index.unique is True
    assert str(index.dialect_options["postgresql"]["where"]) == "period_number IS NULL"


def test_attendance_batch_rejects_duplicate_students():
    student_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="Each student may appear only once"):
        AttendanceMarkRequest(
            date_bs="2083-05-26",
            date_ad=date(2026, 9, 11),
            grade="11",
            section="A",
            entries=[
                {"student_id": student_id, "status": "present"},
                {"student_id": student_id, "status": "absent"},
            ],
        )


@pytest.mark.asyncio
async def test_attendance_update_refreshes_server_managed_fields():
    school_id = uuid.uuid4()
    record = Attendance(
        id=uuid.uuid4(),
        school_id=school_id,
        student_id=uuid.uuid4(),
        grade="2",
        section="A",
        date_bs="2083-05-26",
        date_ad=date(2026, 9, 11),
        status=AttendanceStatus.present,
        marked_by=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    query_result = MagicMock()
    query_result.scalar_one_or_none.return_value = record
    db = AsyncMock()
    db.execute.return_value = query_result

    response = await AttendanceService(db).update_attendance(
        attendance_id=record.id,
        school_id=school_id,
        data=AttendanceUpdateRequest(status="late", remarks="Arrived late"),
        updated_by=uuid.uuid4(),
    )

    db.refresh.assert_awaited_once_with(record)
    assert response is not None
    assert response.status == "late"


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/exams/", "POST"),
        ("/api/v1/exams/", "GET"),
        ("/api/v1/exams/{exam_id}", "PATCH"),
        ("/api/v1/exams/{exam_id}", "DELETE"),
        ("/api/v1/exams/marks", "POST"),
        ("/api/v1/exams/marks/subject/{exam_subject_id}", "GET"),
        ("/api/v1/exams/{exam_id}/calculate", "POST"),
        ("/api/v1/exams/{exam_id}/publish", "POST"),
        ("/api/v1/exams/report-card/{student_id}", "GET"),
    ],
)
def test_exam_workflow_routes_are_registered(path, method):
    assert any(route.path == path and method in route.methods for route in app.routes)


def test_exam_schema_rejects_duplicate_subjects():
    subject_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="only be selected once"):
        ExamCreate(
            name="First Terminal Exam",
            exam_type="terminal",
            academic_year_bs="2083",
            grade=2,
            subjects=[
                {"subject_id": subject_id, "full_marks": 100, "pass_marks": 40},
                {"subject_id": subject_id, "full_marks": 100, "pass_marks": 40},
            ],
        )


def test_absent_mark_is_recorded_as_zero():
    entry = MarkEntry(student_id=uuid.uuid4(), is_absent=True)
    assert entry.marks_obtained == 0


def test_nepal_exam_grade_and_division_boundaries():
    assert calculate_grade_point(90, 100) == 4
    assert calculate_grade_point(39, 100) == 0
    assert calculate_division(60) == Division.FIRST
    assert calculate_division(45) == Division.SECOND
    assert calculate_division(32) == Division.THIRD
    assert calculate_division(31) == Division.FAIL


@pytest.mark.asyncio
async def test_local_storage_keeps_user_photos_below_private_root(tmp_path):
    storage = LocalStorage(tmp_path)
    user_id = uuid.uuid4()

    filename = await storage.save_user_photo(user_id, b"photo", "image/jpeg")

    assert storage.user_photo_path(user_id, filename).read_bytes() == b"photo"
    with pytest.raises(ValueError):
        storage.user_photo_path(user_id, "../secret.txt")


@pytest.mark.asyncio
async def test_local_storage_keeps_student_photos_below_private_root(tmp_path):
    storage = LocalStorage(tmp_path)
    school_id = uuid.uuid4()
    student_id = uuid.uuid4()

    filename = await storage.save_student_photo(
        school_id,
        student_id,
        b"photo",
        "image/png",
    )

    path = storage.student_photo_path(school_id, student_id, filename)
    assert path.read_bytes() == b"photo"
    assert path.suffix == ".png"
