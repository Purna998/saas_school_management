"""Fee request validation and staff/tenant access boundaries."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import httpx
import pytest
from pydantic import ValidationError
from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.fee.schemas.fee import FeePaymentRequest, GenerateLedgerRequest, ScholarshipCreate, normalize_academic_year
from shared.database.base import get_db


@pytest.mark.parametrize("value,expected", [("2083", "2083/084"), ("2083/084", "2083/084"), ("2083/2084", "2083/084")])
def test_fee_year_normalization(value, expected):
    assert normalize_academic_year(value) == expected


def test_fee_year_rejects_nonconsecutive_year():
    with pytest.raises(ValueError, match="follow"):
        normalize_academic_year("2083/085")


@pytest.mark.parametrize("amount", ["0", "-1", "1.001", "NaN", "Infinity"])
def test_payment_rejects_invalid_money(amount):
    with pytest.raises(ValidationError):
        FeePaymentRequest(student_id=uuid4(), ledger_id=uuid4(), amount=amount)


def test_bank_payment_requires_reference():
    with pytest.raises(ValidationError, match="reference"):
        FeePaymentRequest(student_id=uuid4(), ledger_id=uuid4(), amount="10", payment_method="bank_transfer")


def test_billing_rejects_duplicate_students():
    student_id = uuid4()
    with pytest.raises(ValidationError, match="student only once"):
        GenerateLedgerRequest(academic_year_bs="2083", grade="2", student_ids=[student_id, student_id])


def test_scholarship_percentage_is_bounded():
    with pytest.raises(ValidationError, match="100"):
        ScholarshipCreate(student_id=uuid4(), academic_year_bs="2083", name="Award", discount_type="percentage", discount_value="100.01")


@pytest.mark.asyncio
@pytest.mark.parametrize("parent", [True, False])
async def test_financial_read_routes_deny_guardians_and_users_without_permission(parent):
    db = AsyncMock()
    async def session():
        yield db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=uuid4(), school_id=uuid4(), has_role=lambda role: parent and role == "parent",
        has_permission=lambda code: parent and code == "fee:read",
    )
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for path in ["structures", "students", "payments", "scholarships", f"student/{uuid4()}", f"payments/{uuid4()}/receipt"]:
                response = await client.get(f"/api/v1/fees/{path}")
                assert response.status_code == 403, path
        db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
