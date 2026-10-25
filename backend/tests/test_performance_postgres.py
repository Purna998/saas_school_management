"""Opt-in real PostgreSQL regressions; synthetic rows live only in temp tables.

Run with RUN_DATABASE_TESTS=1 against a migrated local database. No school
records are read or changed; an outer transaction owns all test data.
"""

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, insert, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from services.attendance.models.attendance import Attendance, AttendanceStatus
from services.attendance.services.attendance_service import AttendanceService
from services.exam.models.exam import Exam, ExamSubject, Mark, ResultStatus
from services.exam.services.exam_service import ExamService
from services.student.models.student import Gender, Student, StudentStatus
from services.student.services.student_service import StudentService
from shared.config.settings import settings


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1", reason="Opt-in local PostgreSQL tests",
)


@pytest_asyncio.fixture
async def database():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            for table in ("students", "exams", "exam_subjects", "marks", "results", "attendances"):
                await connection.execute(text(
                    f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP"
                ))
            async with AsyncSession(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint",
            ) as session:
                yield session, engine
            await transaction.rollback()
    finally:
        await engine.dispose()


def student_row(school_id, number, **overrides):
    return {
        "id": uuid4(), "school_id": school_id, "full_name_en": f"Test Student {number}",
        "gender": Gender.OTHER, "date_of_birth_ad": date(2015, 1, 1),
        "current_grade": 2, "current_section": "A", "roll_number": number,
        "status": StudentStatus.ACTIVE, "is_deleted": False, **overrides,
    }


@pytest.mark.asyncio
async def test_roster_excludes_other_schools_inactive_and_deleted_students(database):
    db, _ = database
    school_id = uuid4()
    rows = [student_row(school_id, i) for i in range(1, 126)]
    rows += [
        student_row(uuid4(), 200),
        student_row(school_id, 201, status=StudentStatus.INACTIVE),
        student_row(school_id, 202, deleted_at=datetime.now(timezone.utc)),
        student_row(school_id, 203, current_section="B"),
        student_row(school_id, 204, current_grade=3),
    ]
    # Separate statements preserve the optional deleted_at key in the last rows.
    for row in rows:
        await db.execute(insert(Student).values(**row))
    roster = await StudentService(db).get_roster(school_id, 2, "A")
    assert [row["roll_number"] for row in roster] == list(range(1, 126))
    assert len(await StudentService(db).get_roster(school_id, 2)) == 126


@pytest.mark.asyncio
@pytest.mark.parametrize("student_count", [1, 125])
async def test_result_calculation_has_constant_select_count_and_loaded_timestamps(database, student_count):
    db, engine = database
    school_id, exam_id, subject_id = uuid4(), uuid4(), uuid4()
    await db.execute(insert(Exam).values(
        id=exam_id, school_id=school_id, name="Test Exam", exam_type="TERMINAL",
        academic_year_bs="2083", grade=2, status="COMPLETED", is_locked=False,
    ))
    await db.execute(insert(ExamSubject).values(
        id=subject_id, exam_id=exam_id, subject_id=uuid4(), full_marks=100, pass_marks=40,
    ))
    await db.execute(insert(Mark), [{
        "id": uuid4(), "school_id": school_id, "exam_id": exam_id,
        "exam_subject_id": subject_id, "student_id": uuid4(),
        "marks_obtained": Decimal("85.5"), "grade_point": Decimal("3.6"),
        "is_absent": False, "entered_by": uuid4(),
    } for _ in range(student_count)])
    statements = []

    def track_selects(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", track_selects)
    try:
        results = await ExamService(db).calculate_results(exam_id, school_id)
        assert len(results) == student_count
        assert len(statements) == 4, "Query count must not grow with the student count"
        assert all(result.created_at is not None and result.updated_at is not None for result in results)
        assert all(result.status == ResultStatus.PASS and result.gpa == Decimal("3.60") for result in results)
        assert all(result.rank == 1 for result in results)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", track_selects)


@pytest.mark.asyncio
async def test_bs_report_chaitra_rollover_and_school_class_isolation(database):
    db, _ = database
    school_id = uuid4()
    dates = ["2083-11-30", "2083-12-01", "2083-12-30", "2084-01-01"]
    for i, date_bs in enumerate(dates):
        await db.execute(insert(Attendance).values(
            id=uuid4(), school_id=school_id, student_id=uuid4(), grade="2", section="A",
            date_bs=date_bs, date_ad=date(2027, 3, i + 1), status=AttendanceStatus.present,
            marked_by=uuid4(),
        ))
    for other_school, section in ((uuid4(), "A"), (school_id, "B")):
        await db.execute(insert(Attendance).values(
            id=uuid4(), school_id=other_school, student_id=uuid4(), grade="2", section=section,
            date_bs="2083-12-01", date_ad=date(2027, 3, 2), status=AttendanceStatus.absent,
            marked_by=uuid4(),
        ))
    report = await AttendanceService(db).get_monthly_summary(school_id, "2", "A", 2083, 12)
    assert [row.date_bs for row in report.daily_summaries] == dates[1:3]
    assert report.total_school_days == 2
    assert report.average_attendance_percentage == 100
