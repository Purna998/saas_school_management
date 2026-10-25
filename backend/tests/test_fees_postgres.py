"""Opt-in accounting integration tests using isolated, synthetic PostgreSQL data."""

import asyncio
import os
from datetime import date
from decimal import Decimal
from uuid import uuid4
import pytest
import pytest_asyncio
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from services.fee.models.fee import FeeDiscountAllocation, FeeLedger, FeePayment, FeeRefund
from services.fee.schemas.fee import FeeHeadCreate, FeePaymentRequest, FeeRefundRequest, FeeStructureCreate, GenerateLedgerRequest, ScholarshipCreate
from services.fee.services.fee_service import FeeConflictError, FeeService
from services.student.models.student import Student
from shared.config.settings import settings
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NepalCalendar

pytestmark = pytest.mark.skipif(os.environ.get("RUN_DATABASE_TESTS") != "1", reason="Opt-in local PostgreSQL tests")
TABLES = ("students", "fee_structures", "fee_heads", "fee_ledger", "fee_payments", "scholarships", "fee_refunds", "fee_discount_allocations", "users", "tenants")


@pytest_asyncio.fixture
async def accounting():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            for table in TABLES:
                await connection.execute(text(f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP"))
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as session:
                yield session
            await transaction.rollback()
    finally:
        await engine.dispose()


async def seed(db, *, months=None, heads=None):
    school_id, student_id, actor = uuid4(), uuid4(), uuid4()
    await db.execute(insert(Student).values(id=student_id, school_id=school_id, full_name_en="Synthetic Fee Student",
        gender="OTHER", date_of_birth_ad=date(2015, 1, 1), current_grade=2, current_section="A", status="ACTIVE"))
    service = FeeService(db)
    structure = await service.create_fee_structure(school_id, FeeStructureCreate(
        academic_year_bs="2083", grade="2", name="Grade 2 Fees",
        fee_heads=heads or [FeeHeadCreate(name="Tuition", amount="100.00")],
    ))
    request = GenerateLedgerRequest(academic_year_bs="2083", grade="2", student_ids=[student_id], months=months or [1], fee_structure_id=structure.id)
    result = await service.generate_ledger_entries(school_id, request)
    return service, school_id, student_id, actor, structure, request, result


@pytest.mark.asyncio
async def test_billing_is_idempotent_exact_bs_and_optional_by_choice(accounting):
    service, school, student, _, structure, request, result = await seed(accounting, months=[1, 2], heads=[
        FeeHeadCreate(name="Tuition", amount="100.01"),
        FeeHeadCreate(name="Admission", amount="50", frequency="one_time"),
        FeeHeadCreate(name="Transport", amount="20", is_optional=True),
    ])
    assert result["entries_created"] == 3
    assert result["total_assessed"] == "250.02"
    repeat = await service.generate_ledger_entries(school, request)
    assert repeat["entries_created"] == 0 and repeat["entries_skipped"] == 3
    statement = await service.get_student_fee_status(school, student, "2083")
    assert statement.total_due == Decimal("250.02")
    assert all(entry.due_date_ad == NepalCalendar.bs_to_ad(entry.due_date_bs) for entry in statement.ledger_entries)
    optional = next(head for head in structure.fee_heads if head.is_optional)
    request.optional_head_ids = [optional.id]
    assert (await service.generate_ledger_entries(school, request))["entries_created"] == 2
    assert (await service.get_student_fee_status(school, student, "2083")).total_due == Decimal("290.02")


@pytest.mark.asyncio
async def test_partial_payments_receipt_refund_and_summary_reconcile(accounting):
    service, school, student, actor, _, _, _ = await seed(accounting)
    ledger = (await service.get_student_fee_status(school, student, "2083")).ledger_entries[0]
    request = FeePaymentRequest(student_id=student, ledger_id=ledger.id, amount="60")
    payment = await service.collect_fee(school, request, actor)
    assert (await service.collect_fee(school, request, actor)).id == payment.id
    assert payment.balance_after == Decimal("40.00") and payment.paid_date_bs
    refund_request = FeeRefundRequest(amount="10", reason="Duplicate cash received")
    refund = await service.refund_payment(school, payment.id, refund_request, actor)
    assert (await service.refund_payment(school, payment.id, refund_request, actor)).id == refund.id
    summary = await service.get_fee_collection_summary(school, "2083")
    assert (summary.gross_collected, summary.total_refunded, summary.total_collected, summary.total_pending) == (
        Decimal("60"), Decimal("10"), Decimal("50"), Decimal("50"))
    receipt = await service.get_receipt(school, payment.id)
    assert receipt["payment"]["balance_after"] == "40.00"
    assert receipt["payment"]["amount"] == "60.00"
    assert receipt["refunds"][0]["reason"] == "Duplicate cash received"
    report = await service.get_outstanding_fees(school, section="B", academic_year_bs="2083")
    assert report.student_count == 0 and report.total_outstanding == 0
    report = await service.get_outstanding_fees(school, section="A", academic_year_bs="2083")
    assert report.student_count == 1 and report.total_outstanding == Decimal("50")
    assert (await service.list_payments(school, "2083"))["total"] == 1
    assert (await service.list_payments(school, "2083", grade="3"))["total"] == 0


@pytest.mark.asyncio
async def test_scholarship_is_one_pool_reversible_and_never_discounts_paid_money(accounting):
    service, school, student, actor, _, _, _ = await seed(accounting, months=[1, 2])
    ledger = (await service.get_student_fee_status(school, student, "2083")).ledger_entries[0]
    await service.collect_fee(school, FeePaymentRequest(student_id=student, ledger_id=ledger.id, amount="90"), actor)
    request = ScholarshipCreate(student_id=student, name="Concession", discount_type="fixed", discount_value="50", academic_year_bs="2083")
    award = await service.apply_scholarship(school, request, actor)
    assert (await service.apply_scholarship(school, request, actor)).id == award.id
    assert (await service.list_scholarships(school, "2083", grade="2"))["total"] == 1
    assert (await service.list_scholarships(school, "2083", grade="3"))["total"] == 0
    statement = await service.get_student_fee_status(school, student, "2083")
    assert (statement.total_discount, statement.total_due, statement.total_paid, statement.total_balance) == (Decimal("50"), Decimal("150"), Decimal("90"), Decimal("60"))
    allocations = (await accounting.scalars(select(FeeDiscountAllocation))).all()
    assert sum(row.amount for row in allocations) == Decimal("50")
    reversed_award = await service.reverse_scholarship(school, award.id, "Concession entered for wrong year", actor)
    assert reversed_award.is_active is False and reversed_award.reversed_by == actor
    assert (await service.get_student_fee_status(school, student, "2083")).total_balance == Decimal("110")
    await service.reverse_scholarship(school, award.id, "Retry", actor)
    assert (await service.get_student_fee_status(school, student, "2083")).total_balance == Decimal("110")


@pytest.mark.asyncio
async def test_percentage_rounding_preserves_paise(accounting):
    service, school, student, actor, _, _, _ = await seed(accounting, heads=[
        FeeHeadCreate(name="First", amount="0.01"), FeeHeadCreate(name="Second", amount="0.01"),
    ])
    award = await service.apply_scholarship(school, ScholarshipCreate(student_id=student, name="25 percent",
        discount_type="percentage", discount_value="25", academic_year_bs="2083"), actor)
    assert award.applied_amount == Decimal("0.01")
    assert (await service.get_student_fee_status(school, student, "2083")).total_balance == Decimal("0.01")


@pytest.mark.asyncio
async def test_cross_school_access_and_changed_retry_details_are_rejected(accounting):
    service, school, student, actor, structure, request, _ = await seed(accounting)
    with pytest.raises(RecordNotFoundError):
        await service.get_student_fee_status(uuid4(), student)
    request.student_ids = [uuid4()]
    with pytest.raises(ValueError, match="Every selected"):
        await service.generate_ledger_entries(school, request)
    ledger = (await service.get_student_fee_status(school, student, "2083")).ledger_entries[0]
    payment_request = FeePaymentRequest(student_id=student, ledger_id=ledger.id, amount="40")
    payment = await service.collect_fee(school, payment_request, actor)
    payment_request.amount = Decimal("41")
    with pytest.raises(FeeConflictError):
        await service.collect_fee(school, payment_request, actor)
    with pytest.raises(RecordNotFoundError):
        await service.get_receipt(uuid4(), payment.id)
    with pytest.raises(ValueError, match="exceeds"):
        await service.collect_fee(school, FeePaymentRequest(student_id=student, ledger_id=ledger.id, amount="100"), actor)
    with pytest.raises(FeeConflictError, match="locked"):
        await service.change_fee_head(school, structure.id, structure.fee_heads[0].id, FeeHeadCreate(name="Changed", amount="50"))


@pytest.mark.asyncio
async def test_archived_billed_plan_cannot_be_replaced_and_double_charge_same_year(accounting):
    from services.fee.schemas.fee import FeeStructureUpdate
    service, school, _, _, structure, _, _ = await seed(accounting)
    await service.update_fee_structure(school, structure.id, FeeStructureUpdate(is_active=False))
    with pytest.raises(FeeConflictError, match="already have a billed"):
        await service.create_fee_structure(school, FeeStructureCreate(academic_year_bs="2083", grade="2", name="Replacement fees"))


@pytest.mark.asyncio
async def test_http_accounting_workflow_serializes_statements_receipts_and_reports(accounting):
    from types import SimpleNamespace
    import httpx
    from main import app
    from services.auth.dependencies.auth import get_current_active_user
    from shared.database.base import get_db
    _, school, student, actor, _, _, _ = await seed(accounting)
    async def session_override():
        yield accounting
    app.dependency_overrides[get_db] = session_override
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=actor, school_id=school, has_permission=lambda code: True, has_role=lambda role: False,
    )
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            statement = await client.get(f"/api/v1/fees/student/{student}", params={"academic_year_bs": "2083"})
            assert statement.status_code == 200
            ledger_id = statement.json()["data"]["ledger_entries"][0]["id"]
            payment = await client.post("/api/v1/fees/collect", json={"student_id": str(student), "ledger_id": ledger_id, "amount": "50.25", "request_id": str(uuid4())})
            assert payment.status_code == 201, payment.text
            payment_id = payment.json()["data"]["id"]
            receipt = await client.get(f"/api/v1/fees/payments/{payment_id}/receipt")
            assert receipt.status_code == 200 and receipt.json()["data"]["student_name"] == "Synthetic Fee Student"
            refund = await client.post(f"/api/v1/fees/payments/{payment_id}/refunds", json={"amount": "0.25", "reason": "Excess paise received", "request_id": str(uuid4())})
            assert refund.status_code == 201, refund.text
            summary = await client.get("/api/v1/fees/collection-summary", params={"academic_year_bs": "2083"})
            assert summary.status_code == 200 and summary.json()["data"]["total_collected"] == "50.00"
            for path in ("structures", "students", "scholarships", "payments", "outstanding", "roster?grade=2"):
                response = await client.get(f"/api/v1/fees/{path}")
                assert response.status_code == 200, (path, response.text)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("same_request", [False, True])
async def test_concurrent_cashiers_cannot_overpay_or_duplicate_retries(same_request):
    # Unlike per-connection temp tables, a unique disposable schema is visible
    # to both connections. No existing school table or record is modified.
    schema = f"fee_test_{uuid4().hex}"
    admin = create_async_engine(settings.database_url, poolclass=NullPool)
    engine = create_async_engine(settings.database_url, poolclass=NullPool, connect_args={"server_settings": {"search_path": f"{schema},public"}})
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            for table in TABLES:
                await connection.execute(text(f"CREATE TABLE {schema}.{table} (LIKE public.{table} INCLUDING ALL)"))
        async with AsyncSession(engine, expire_on_commit=False) as db:
            service, school, student, actor, _, _, _ = await seed(db)
            ledger = (await service.get_student_fee_status(school, student, "2083")).ledger_entries[0]
            await db.commit()
        request_id = uuid4()
        async def collect():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                try:
                    payment = await FeeService(db).collect_fee(school, FeePaymentRequest(student_id=student,
                        ledger_id=ledger.id, amount="70", request_id=request_id if same_request else uuid4()), actor)
                    await db.commit()
                    return payment.id
                except ValueError:
                    await db.rollback()
                    return None
        outcomes = await asyncio.gather(collect(), collect())
        assert sum(value is not None for value in outcomes) == (2 if same_request else 1)
        if same_request:
            assert outcomes[0] == outcomes[1]
        async with AsyncSession(engine) as db:
            entries = (await db.scalars(select(FeeLedger))).all()
            payments = (await db.scalars(select(FeePayment))).all()
            assert len(payments) == 1
            assert entries[0].amount_paid == Decimal("70") and entries[0].balance == Decimal("30")
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin.dispose()
