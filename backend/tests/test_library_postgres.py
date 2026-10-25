"""Opt-in inventory/circulation tests using synthetic PostgreSQL records only."""

import asyncio
import os
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.library.models.library import Book, BookCopy, BookIssue, IssuedToType, IssueStatus
from services.library.schemas.library import AddCopiesRequest, BookCreate, BookUpdate, CopyUpdateRequest, IssueBookRequest, LendingPolicyUpdate, LostBookRequest, RenewBookRequest, ReturnBookRequest
from services.library.services.library_service import LibraryConflict, LibraryService, today
from services.student.models.student import Student
from services.staff.models.staff import Staff
from shared.config.settings import settings
from shared.database.base import get_db
from shared.utils.exceptions import RecordNotFoundError

pytestmark = pytest.mark.skipif(os.environ.get("RUN_DATABASE_TESTS") != "1", reason="Opt-in local PostgreSQL tests")
TABLES = ("books", "book_copies", "book_issues", "library_policies", "library_events", "students", "staff")


@pytest_asyncio.fixture
async def library_db():
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


async def seed(db, copies=2):
    school, student, actor = uuid4(), uuid4(), uuid4()
    await db.execute(insert(Student).values(id=student, school_id=school, full_name_en="Synthetic Library Student",
        gender="OTHER", date_of_birth_ad=date(2015,1,1), current_grade=2, current_section="A", status="ACTIVE"))
    service = LibraryService(db)
    book = await service.create_book(school, BookCreate(title="Synthetic Book", author="Test Author", total_copies=copies), actor, "Librarian")
    return service, school, student, actor, book


@pytest.mark.asyncio
async def test_catalog_stock_accessions_and_archive_preserve_history(library_db):
    service, school, student, actor, book = await seed(library_db)
    assert book.total_copies == 2 and book.available_copies == 2
    command = AddCopiesRequest(count=1, accession_numbers=["ACC-001"])
    await service.add_copies(school, book.id, command, actor)
    await service.add_copies(school, book.id, command, actor)
    assert book.total_copies == 3
    inventory = await service.list_copies(school, book.id)
    copy = next(row for row in inventory["copies"] if row["accession_number"] == "ACC-001")
    await service.update_copy(school, copy["id"], CopyUpdateRequest(status="damaged", notes="Torn binding"), actor)
    assert book.available_copies == 2 and book.total_copies == 3
    await service.update_copy(school, copy["id"], CopyUpdateRequest(status="withdrawn", notes="Beyond repair"), actor)
    assert book.total_copies == 2
    await service.update_book(school, book.id, BookUpdate(is_active=False), actor)
    assert (await service.list_books(school))["total"] == 0
    assert (await service.list_books(school, is_active=False))["total"] == 1
    assert (await service.history(school, book_id=book.id))["total"] == 5
    with pytest.raises(RecordNotFoundError):
        await service.list_copies(uuid4(), book.id)


@pytest.mark.asyncio
async def test_issue_return_retries_do_not_corrupt_available_stock(library_db):
    service, school, student, actor, book = await seed(library_db)
    request = IssueBookRequest(book_id=book.id, issued_to_id=student)
    loan = await service.issue_book(school, request, actor)
    assert (await service.issue_book(school, request, actor)).id == loan.id
    assert book.available_copies == 1
    returned = ReturnBookRequest(book_issue_id=loan.id)
    await service.return_book(school, returned, actor)
    await service.return_book(school, returned, actor)
    assert book.available_copies == 2
    with pytest.raises(LibraryConflict, match="already returned"):
        await service.return_book(school, ReturnBookRequest(book_issue_id=loan.id), actor)
    assert book.available_copies == 2
    request.due_days = 2
    with pytest.raises(LibraryConflict, match="different"):
        await service.issue_book(school, request, actor)


@pytest.mark.asyncio
async def test_borrower_eligibility_tenant_scope_and_reference_only_titles(library_db):
    service, school, student, actor, book = await seed(library_db)
    with pytest.raises(RecordNotFoundError):
        await service.issue_book(uuid4(), IssueBookRequest(book_id=book.id, issued_to_id=student), actor)
    with pytest.raises(RecordNotFoundError):
        await service.issue_book(school, IssueBookRequest(book_id=book.id, issued_to_id=uuid4()), actor)
    await service.update_book(school, book.id, BookUpdate(is_lendable=False), actor)
    with pytest.raises(LibraryConflict, match="reference-only"):
        await service.issue_book(school, IssueBookRequest(book_id=book.id, issued_to_id=student), actor)
    assert book.available_copies == 2


@pytest.mark.asyncio
async def test_staff_lookup_lending_limits_and_renewal_policy(library_db):
    service, school, student, actor, book = await seed(library_db)
    staff_id = uuid4()
    await library_db.execute(insert(Staff).values(id=staff_id, school_id=school, full_name_en="Synthetic Librarian Staff",
        gender="OTHER", staff_type="TEACHING", status="ACTIVE", employee_id="EMP-001"))
    borrowers = await service.borrowers(school, IssuedToType.STAFF, "EMP-001")
    assert borrowers["total"] == 1 and borrowers["borrowers"][0]["id"] == str(staff_id)
    await service.update_policy(school, LendingPolicyUpdate(student_limit=1, max_renewals=1), actor)
    loan = await service.issue_book(school, IssueBookRequest(book_id=book.id, issued_to_id=student), actor)
    other = await service.create_book(school, BookCreate(title="Other", author="Author"), actor)
    with pytest.raises(LibraryConflict, match="maximum"):
        await service.issue_book(school, IssueBookRequest(book_id=other.id, issued_to_id=student), actor)
    old_due = loan.due_date_ad
    renewal = RenewBookRequest()
    await service.renew_book(school, loan.id, renewal, actor)
    await service.renew_book(school, loan.id, renewal, actor)
    assert loan.renewal_count == 1 and loan.due_date_ad == old_due + timedelta(days=14)
    with pytest.raises(LibraryConflict, match="renewal limit"):
        await service.renew_book(school, loan.id, RenewBookRequest(), actor)


@pytest.mark.asyncio
async def test_overdue_fine_snapshot_damage_and_lost_recovery(library_db):
    service, school, student, actor, book = await seed(library_db)
    await service.update_policy(school, LendingPolicyUpdate(daily_fine="1.25", fine_cap="5.00"), actor)
    loan = await service.issue_book(school, IssueBookRequest(book_id=book.id, issued_to_id=student), actor)
    loan.issue_date_ad = today() - timedelta(days=20)
    loan.due_date_ad = today() - timedelta(days=4)
    await library_db.flush()
    await service.update_policy(school, LendingPolicyUpdate(daily_fine="2.00", fine_cap="20.00"), actor)
    assert service.loan_response(loan)["estimated_fine"] == "5.00"
    assert (await service.list_loans(school, status="overdue"))["total"] == 1
    assert (await service.get_library_stats(school))["overdue_count"] == 1
    with pytest.raises(LibraryConflict, match="overdue"):
        await service.renew_book(school, loan.id, RenewBookRequest(), actor)
    await service.mark_lost(school, loan.id, LostBookRequest(notes="Reported missing", fine_amount="10.25"), actor)
    assert book.available_copies == 1
    await service.return_book(school, ReturnBookRequest(book_issue_id=loan.id, condition="damaged", fine_amount="0", notes="Found with damaged cover"), actor)
    assert book.available_copies == 1 and book.total_copies == 2
    await service.update_copy(school, loan.copy_id, CopyUpdateRequest(status="available", notes="Binding repaired"), actor)
    assert book.available_copies == 2
    history = await service.history(school, issue_id=loan.id)
    assert {event["action"] for event in history["events"]} == {"issued", "lost", "returned"}


@pytest.mark.asyncio
async def test_overdue_renewal_preserves_accrual_and_return_waiver_needs_reason(library_db):
    service, school, student, actor, book = await seed(library_db)
    await service.update_policy(school, LendingPolicyUpdate(allow_overdue_renewal=True, daily_fine="1.25", fine_cap="5.00"), actor)
    loan = await service.issue_book(school, IssueBookRequest(book_id=book.id, issued_to_id=student), actor)
    loan.issue_date_ad, loan.due_date_ad = today() - timedelta(days=20), today() - timedelta(days=2)
    await library_db.flush()
    await service.renew_book(school, loan.id, RenewBookRequest(), actor)
    assert service.loan_response(loan)["estimated_fine"] == "2.50"
    assert str(loan.fine_amount) == "2.50"
    loan.due_date_ad = today() - timedelta(days=4)
    await library_db.flush()
    assert service.loan_response(loan)["estimated_fine"] == "5.00"
    with pytest.raises(ValueError, match="waiver"):
        await service.return_book(school, ReturnBookRequest(book_issue_id=loan.id, fine_amount="0"), actor)
    await service.update_book(school, book.id, BookUpdate(is_active=False), actor)
    await service.return_book(school, ReturnBookRequest(book_issue_id=loan.id, fine_amount="0", notes="Approved school waiver"), actor)
    assert book.available_copies == 2 and loan.status == IssueStatus.RETURNED


@pytest.mark.asyncio
async def test_http_library_workflow_and_csv_formula_safety(library_db):
    service, school, student, actor, book = await seed(library_db)
    await service.update_book(school, book.id, BookUpdate(title="=UNTRUSTED", language="नेपाली"), actor)
    async def session():
        yield library_db
    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=actor, school_id=school,
        full_name_en="Librarian", has_permission=lambda code: True, has_role=lambda role: False)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            issue = await client.post("/api/v1/library/issue", json={"book_id": str(book.id), "issued_to_id": str(student), "request_id": str(uuid4())})
            assert issue.status_code == 201, issue.text
            loan_id = issue.json()["data"]["id"]
            for path in ["books", f"books/{book.id}/copies", "issued", "borrowers", "policy", "history", "stats"]:
                response = await client.get(f"/api/v1/library/{path}")
                assert response.status_code == 200, (path, response.text)
            report = await client.get("/api/v1/library/export?report=catalog")
            assert report.status_code == 200 and "'=UNTRUSTED" in report.text and "नेपाली" in report.text
            returned = await client.post("/api/v1/library/return", json={"book_issue_id": loan_id, "request_id": str(uuid4())})
            assert returned.status_code == 200 and returned.json()["data"]["status"] == "returned"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("same_request", [False, True])
@pytest.mark.parametrize("operation", ["issue", "return"])
async def test_concurrent_issue_return_of_last_copy_and_retries(same_request, operation):
    schema = f"library_test_{uuid4().hex}"
    admin = create_async_engine(settings.database_url, poolclass=NullPool)
    engine = create_async_engine(settings.database_url, poolclass=NullPool, connect_args={"server_settings": {"search_path": f"{schema},public"}})
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            for table in TABLES:
                await connection.execute(text(f"CREATE TABLE {schema}.{table} (LIKE public.{table} INCLUDING ALL)"))
        async with AsyncSession(engine, expire_on_commit=False) as db:
            _, school, student, actor, book = await seed(db, 1)
            other = uuid4()
            await db.execute(insert(Student).values(id=other, school_id=school, full_name_en="Second Synthetic Student",
                gender="OTHER", date_of_birth_ad=date(2015,1,1), current_grade=2, status="ACTIVE"))
            if operation == "return":
                loan = await LibraryService(db).issue_book(school, IssueBookRequest(book_id=book.id, issued_to_id=student), actor)
                loan_id = loan.id
            await db.commit()
        request_id = uuid4()
        async def issue(borrower):
            async with AsyncSession(engine, expire_on_commit=False) as db:
                try:
                    if operation == "issue":
                        loan = await LibraryService(db).issue_book(school, IssueBookRequest(book_id=book.id,
                            issued_to_id=student if same_request else borrower, request_id=request_id if same_request else uuid4()), actor)
                    else:
                        loan = await LibraryService(db).return_book(school, ReturnBookRequest(book_issue_id=loan_id,
                            request_id=request_id if same_request else uuid4()), actor)
                    await db.commit()
                    return loan.id
                except LibraryConflict:
                    await db.rollback()
                    return None
        outcomes = await asyncio.gather(issue(student), issue(other))
        assert sum(value is not None for value in outcomes) == (2 if same_request else 1)
        if same_request:
            assert outcomes[0] == outcomes[1]
        async with AsyncSession(engine) as db:
            assert len((await db.scalars(select(BookIssue))).all()) == 1
            assert (await db.scalar(select(Book))).available_copies == (0 if operation == "issue" else 1)
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin.dispose()
