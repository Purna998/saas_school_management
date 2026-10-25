"""Regressions for complete rosters, BS report bounds and fractional grades."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.dialects import postgresql

from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.attendance.services.attendance_service import AttendanceService
from services.exam.services.exam_service import calculate_grade_point
from shared.database.base import get_db


@pytest.mark.parametrize("percentage,expected", [
    ("89.99", "3.6"), ("79.5", "3.2"), ("69.99", "2.8"),
    ("59.99", "2.4"), ("49.99", "2.0"), ("39.99", "0.0"),
])
def test_fractional_scores_stay_in_the_existing_grading_bands(percentage, expected):
    assert calculate_grade_point(Decimal(percentage), Decimal("100")) == Decimal(expected)


@pytest.mark.asyncio
@pytest.mark.parametrize("month,start,end", [
    (1, "2083-01-01", "2083-02-01"),
    (12, "2083-12-01", "2084-01-01"),
])
async def test_bs_month_report_uses_indexable_bounds(month, start, end):
    result = MagicMock()
    result.all.return_value = []
    db = AsyncMock()
    db.execute.return_value = result
    report = await AttendanceService(db).get_monthly_summary(uuid4(), "2", "A", 2083, month)
    statement = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert start in statement.params.values()
    assert end in statement.params.values()
    assert " LIKE " not in str(statement)
    assert report.total_school_days == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("allowed", [True, False])
async def test_roster_keeps_school_scope_permissions_and_complete_results(allowed):
    school_id = uuid4()
    students = [{
        "id": uuid4(), "full_name_en": f"Student {i}", "roll_number": i,
        "admission_number": None, "emis_student_id": None,
    } for i in range(1, 126)]
    rows = MagicMock()
    rows.mappings.return_value.all.return_value = students
    db = AsyncMock()
    db.execute.return_value = rows

    async def session_override():
        yield db

    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        school_id=school_id, has_permission=lambda permission: allowed,
    )
    app.dependency_overrides[get_db] = session_override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/students/roster", params={
                "grade": 2, "section": "A", "school_id": str(uuid4()),
            })
        assert response.status_code == (200 if allowed else 403)
        if allowed:
            assert response.json()["total"] == 125
            assert len(response.json()["students"]) == 125
            assert set(response.json()["students"][0]) == {
                "id", "full_name_en", "roll_number", "admission_number", "emis_student_id",
            }
            compiled = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
            assert school_id in compiled.params.values()
            assert " LIMIT " not in str(compiled)
        else:
            db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
