"""Real report sources and immutable exports use synthetic temporary tables only."""

import asyncio
import csv
import io
import os
import zipfile
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from main import app
from shared.config.settings import settings
from shared.database.base import get_db
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NepalCalendar, NPT
from services.auth.dependencies.auth import get_current_active_user
from services.tenant.models.tenant import Tenant
from services.student.models.student import Student, StudentEnrollment
from services.attendance.models.attendance import Attendance
from services.exam.models.exam import Exam, Result
from services.fee.models.fee import FeeLedger, FeePayment, FeeRefund
from services.staff.models.staff import Staff
from services.library.models.library import BookIssue
from services.hostel.models.hostel import RoomAllocation
from services.transport.models.transport import StudentTransport, TransportTrip
from services.report.models.report import Report, ReportRow
from services.report.schemas.report import (
    ReportRequest,
    ReportGenerateRequest,
    ReportArchiveRequest,
)
from services.report.services.catalog import DEFINITIONS
from services.report.services.report_service import ReportService, ReportConflict

DB_TEST = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="Opt-in local PostgreSQL report tests",
)
TABLES = (
    "reports",
    "report_rows",
    "report_events",
    "tenants",
    "students",
    "student_enrollments",
    "attendances",
    "exams",
    "results",
    "fee_ledger",
    "fee_payments",
    "fee_refunds",
    "staff",
    "book_issues",
    "room_allocations",
    "student_transport",
    "transport_trips",
    "transport_passengers",
)


@pytest_asyncio.fixture
async def report_db():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            for table in TABLES:
                await connection.execute(
                    text(
                        f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP"
                    )
                )
            async with AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as db:
                yield db
            await transaction.rollback()
    finally:
        await engine.dispose()


def user(school=None, role="school_admin", permissions=None):
    permissions = {"*:*"} if permissions is None else set(permissions)
    return SimpleNamespace(
        id=uuid4(),
        school_id=school or uuid4(),
        full_name_en="Synthetic office user",
        has_role=lambda value: value == role,
        has_permission=lambda value: "*:*" in permissions or value in permissions,
    )


async def seed(db):
    school, student, exam, ledger, payment = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    current = NepalCalendar.current_bs_date()
    year = current[:4]
    start = NepalCalendar.bs_to_ad(current[:7] + "-01")
    stamp = datetime.now(NPT)
    await db.execute(
        insert(Tenant).values(
            id=school,
            name_en="Synthetic Nepal School",
            name_np="कृत्रिम विद्यालय",
            emis_code="SYNTH-1",
            municipality="Synthetic municipality",
        )
    )
    await db.execute(
        insert(Student).values(
            id=student,
            school_id=school,
            full_name_en='=HYPERLINK("unsafe")',
            full_name_np="कृत्रिम विद्यार्थी",
            admission_number="00001",
            gender="FEMALE",
            date_of_birth_ad=date(2015, 1, 1),
            current_grade=2,
            current_section="A",
            status="ACTIVE",
        )
    )
    await db.execute(
        insert(StudentEnrollment).values(
            id=uuid4(),
            school_id=school,
            student_id=student,
            academic_year_bs=year,
            grade=2,
            section="A",
            status="ENROLLED",
            enrolled_at=stamp,
        )
    )
    for offset, status in enumerate(("present", "late", "absent", "leave", "holiday")):
        day = start + timedelta(days=offset)
        await db.execute(
            insert(Attendance).values(
                id=uuid4(),
                school_id=school,
                student_id=student,
                grade="2",
                section="A",
                date_ad=day,
                date_bs=NepalCalendar.ad_to_bs(day),
                status=status,
                marked_by=uuid4(),
            )
        )
    await db.execute(
        insert(Attendance).values(
            id=uuid4(),
            school_id=school,
            student_id=student,
            grade="2",
            section="A",
            date_ad=start,
            date_bs=NepalCalendar.ad_to_bs(start),
            status="absent",
            marked_by=uuid4(),
            period_number=1,
        )
    )
    await db.execute(
        insert(Exam).values(
            id=exam,
            school_id=school,
            name="Synthetic term",
            exam_type="TERMINAL",
            academic_year_bs=year,
            grade=2,
            status="PUBLISHED",
            is_locked=True,
        )
    )
    await db.execute(
        insert(Result).values(
            id=uuid4(),
            school_id=school,
            exam_id=exam,
            student_id=student,
            total_marks="85.00",
            gpa="3.60",
            rank=1,
            status="PASS",
        )
    )
    await db.execute(
        insert(FeeLedger).values(
            id=ledger,
            school_id=school,
            student_id=student,
            fee_head_id=uuid4(),
            fee_head_name="Synthetic monthly fee",
            academic_year_bs=f"{year}/{(int(year)+1)%1000:03d}",
            month_bs=current[:7],
            original_amount="1000.25",
            discount_amount="0.00",
            amount_due="1000.25",
            amount_paid="75.10",
            balance="925.15",
            due_date_ad=start,
            status="partial",
        )
    )
    await db.execute(
        insert(FeePayment).values(
            id=payment,
            school_id=school,
            student_id=student,
            ledger_id=ledger,
            amount="100.10",
            refunded_amount="25.00",
            payment_method="cash",
            receipt_number="SYNTH-R1",
            paid_date_ad=start,
            paid_date_bs=NepalCalendar.ad_to_bs(start),
            received_by=uuid4(),
        )
    )
    await db.execute(
        insert(FeeRefund).values(
            id=uuid4(),
            school_id=school,
            payment_id=payment,
            student_id=student,
            request_id=uuid4(),
            amount="25.00",
            payment_method="cash",
            reason="Synthetic refund",
            refund_number="SYNTH-F1",
            refunded_date_ad=start,
            refunded_date_bs=NepalCalendar.ad_to_bs(start),
            refunded_by=uuid4(),
        )
    )
    await db.execute(
        insert(Staff).values(
            id=uuid4(),
            school_id=school,
            full_name_en="Synthetic Teacher",
            gender="OTHER",
            staff_type="TEACHING",
            status="ACTIVE",
            salary="90000.00",
        )
    )
    await db.execute(
        insert(BookIssue).values(
            id=uuid4(),
            school_id=school,
            book_id=uuid4(),
            copy_id=uuid4(),
            book_title="गणित",
            borrower_name="Synthetic borrower",
            issued_to_id=student,
            issued_to_type="STUDENT",
            issue_date_ad=start,
            due_date_ad=start + timedelta(days=14),
            status="ISSUED",
            fine_amount="0.00",
        )
    )
    await db.execute(
        insert(RoomAllocation).values(
            id=uuid4(),
            school_id=school,
            room_id=uuid4(),
            bed_id=uuid4(),
            student_id=student,
            student_name="Synthetic resident",
            hostel_name="School hostel",
            room_number="101",
            allocated_date_ad=start,
            status="ACTIVE",
            monthly_fee="500.50",
        )
    )
    await db.execute(
        insert(StudentTransport).values(
            id=uuid4(),
            school_id=school,
            student_id=student,
            route_id=uuid4(),
            transport_type="BOTH",
            monthly_fee="100.25",
            is_active=True,
            needs_setup=True,
            snapshot={"student_name": "Synthetic rider"},
        )
    )
    await db.execute(
        insert(TransportTrip).values(
            id=uuid4(),
            school_id=school,
            run_id=uuid4(),
            vehicle_id=uuid4(),
            date_ad=start,
            direction="drop",
            status="in_progress",
            snapshot={
                "run_name": "Synthetic run",
                "vehicle_number": "बा 2 ख 1234",
                "driver_name": "Synthetic Driver",
            },
            started_at=stamp,
            sweep_confirmed=False,
            tracking_progress={},
        )
    )
    await db.flush()
    return user(school), student, exam, current


def request(kind, student, exam, current):
    values = {
        "academic_year_bs": current[:4],
        "month_bs": current[:7],
        "date_from_bs": current[:7] + "-01",
        "date_to_bs": current,
        "exam_id": exam,
        "student_id": student,
    }
    definition = next(item for item in DEFINITIONS if item.key == kind)
    return ReportRequest(
        report_type=kind,
        **{key: value for key, value in values.items() if key in definition.filters},
    )


@DB_TEST
@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [item.key for item in DEFINITIONS])
async def test_all_report_sources_read_actual_school_records(report_db, kind):
    actor, student, exam, current = await seed(report_db)
    service = ReportService(report_db)
    data = request(kind, student, exam, current)
    result = await service.preview(actor, data)
    assert result["total"] == (
        0 if kind == "dropout" else 2 if kind == "fee_collection" else 1
    )
    assert all("Sample Student" not in str(row) for row in result["rows"])
    if kind == "attendance_monthly":
        row = result["rows"][0]
        assert (
            row["present"] == "1"
            and row["late"] == "1"
            and row["holiday"] == "1"
            and row["marked"] == "4"
            and row["rate"] == "50.00"
        )
        period = await service.preview(
            actor, data.model_copy(update={"period_number": 1})
        )
        assert period["rows"][0]["absent"] == "1" and period["rows"][0]["marked"] == "1"
    if kind == "fee_collection":
        totals = {item["key"]: item["value"] for item in result["summary"]}
        assert (
            totals["gross"] == "100.10"
            and totals["refunded"] == "25.00"
            and totals["net"] == "75.10"
        )
    if kind == "staff_summary":
        assert "salary" not in str(result["columns"]) and "90000" not in str(
            result["rows"]
        )
    if kind == "emis_annual":
        assert "EMIS ID missing" in result["rows"][0]["review"]


@DB_TEST
@pytest.mark.asyncio
async def test_snapshot_retry_exports_archive_and_integrity(report_db):
    actor, student, exam, current = await seed(report_db)
    service = ReportService(report_db)
    data = ReportGenerateRequest(
        report_type="student_list", request_id=uuid4(), file_format="excel"
    )
    saved = await service.generate_report(actor, data)
    assert saved["row_count"] == 1
    assert (await service.generate_report(actor, data))["id"] == saved["id"]
    with pytest.raises(ReportConflict):
        await service.generate_report(
            actor, data.model_copy(update={"title": "Different intent"})
        )
    await report_db.execute(
        update(Student)
        .where(Student.id == student)
        .values(full_name_en="Changed after report")
    )
    detail = await service.detail(actor, UUID(saved["id"]))
    assert detail["rows"][0]["name"].startswith("=HYPERLINK")
    content, ext = await service.download(actor, UUID(saved["id"]), "csv")
    assert ext == "csv" and content.startswith(b"\xef\xbb\xbf")
    assert list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))[1][0].startswith(
        "'=HYPERLINK"
    )
    content, ext = await service.download(actor, UUID(saved["id"]), "excel")
    assert ext == "xlsx"
    with zipfile.ZipFile(io.BytesIO(content)) as book:
        assert b"<f>" not in book.read("xl/worksheets/sheet1.xml")
        assert "कृत्रिम विद्यार्थी" in book.read("xl/sharedStrings.xml").decode()
    archive = ReportArchiveRequest(
        request_id=uuid4(), notes="Synthetic report retention"
    )
    await service.archive(actor, UUID(saved["id"]), archive)
    await service.archive(actor, UUID(saved["id"]), archive)
    assert (await service.list_reports(actor))["total"] == 0 and (
        await service.list_reports(actor, archived=True)
    )["total"] == 1
    await report_db.execute(
        update(ReportRow)
        .where(ReportRow.report_id == UUID(saved["id"]))
        .values(values={"name": "tampered"})
    )
    with pytest.raises(ReportConflict, match="integrity"):
        await service.download(actor, UUID(saved["id"]))


@DB_TEST
@pytest.mark.asyncio
async def test_report_permissions_and_school_scope_are_rechecked_on_saved_download(
    report_db,
):
    actor, student, exam, current = await seed(report_db)
    service = ReportService(report_db)
    saved = await service.generate_report(
        actor,
        ReportGenerateRequest(
            **request("fee_collection", student, exam, current).model_dump(),
            request_id=uuid4(),
        ),
    )
    restricted = user(
        actor.school_id,
        permissions={"report:read", "report:generate", "report:export", "student:read"},
    )
    assert (await service.list_reports(restricted))["total"] == 0
    with pytest.raises(HTTPException) as denied:
        await service.download(restricted, UUID(saved["id"]))
    assert denied.value.status_code == 403
    with pytest.raises(RecordNotFoundError):
        await service.get_report(user(), UUID(saved["id"]))
    assert (await service.preview(user(), ReportRequest(report_type="student_list")))[
        "total"
    ] == 0
    current_user = restricted

    async def database():
        yield report_db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_active_user] = lambda: current_user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            catalog = await client.get("/api/v1/reports/catalog")
            assert catalog.status_code == 200
            assert (
                next(
                    item
                    for item in catalog.json()["data"]["reports"]
                    if item["key"] == "fee_collection"
                )["available"]
                is False
            )
            assert (
                await client.get(f"/api/v1/reports/{saved['id']}/download")
            ).status_code == 403
            current_user = user(actor.school_id, "parent")
            assert (await client.get("/api/v1/reports/catalog")).status_code == 403
            current_user = actor
            response = await client.get(f"/api/v1/reports/{saved['id']}")
            assert (
                response.status_code == 200
                and response.headers["cache-control"] == "no-store, private"
            )
            assert "file_url" not in response.json()["data"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_active_user, None)


@DB_TEST
@pytest.mark.asyncio
async def test_unverified_legacy_files_and_oversized_reports_are_never_exported(
    report_db, monkeypatch
):
    import services.report.services.report_service as module

    actor, student, exam, current = await seed(report_db)
    service = ReportService(report_db)
    legacy = Report(
        id=uuid4(),
        school_id=actor.school_id,
        report_type="student_list",
        title="Legacy sample",
        file_url="C:/private/never-open-this.txt",
        snapshot_version=0,
        status=module.ReportStatus.READY,
        file_format=module.ReportFormat.CSV,
    )
    report_db.add(legacy)
    await report_db.flush()
    with pytest.raises(ReportConflict, match="unverified"):
        await service.download(actor, legacy.id)
    monkeypatch.setattr(module, "MAX_ROWS", 0)
    with pytest.raises(ValueError, match="no partial"):
        await service.generate_report(
            actor, ReportGenerateRequest(report_type="student_list", request_id=uuid4())
        )
    assert (await service.list_reports(actor))["total"] == 1


def test_report_inputs_validate_bs_dates_and_do_not_offer_fake_pdf_files():
    assert (
        ReportRequest(report_type="attendance_monthly", month_bs="२०८३-०७").month_bs
        == "2083-07"
    )
    for data in (
        {"month_bs": "2083-13"},
        {"date_from_bs": "2083-01-99"},
        {"grade": 13},
        {"filters": {"unknown": True}},
    ):
        with pytest.raises(ValidationError):
            ReportRequest(report_type="student_list", **data)
    with pytest.raises(ValidationError, match="Save PDF"):
        ReportGenerateRequest(
            report_type="student_list", request_id=uuid4(), file_format="pdf"
        )


@DB_TEST
@pytest.mark.asyncio
async def test_latest_yearly_enrollment_and_refund_movement_dates(report_db):
    actor, student, exam, current = await seed(report_db)
    service = ReportService(report_db)
    stamp = datetime.now(NPT)
    await report_db.execute(
        insert(StudentEnrollment).values(
            id=uuid4(),
            school_id=actor.school_id,
            student_id=student,
            academic_year_bs=current[:4],
            grade=3,
            section="B",
            status="DROPPED",
            enrolled_at=stamp + timedelta(seconds=1),
        )
    )
    result = await service.preview(actor, request("enrollment", student, exam, current))
    assert result["total"] == 1 and result["rows"][0]["grade"] == "3"
    assert (await service.preview(actor, request("dropout", student, exam, current)))[
        "total"
    ] == 1
    first = NepalCalendar.bs_to_ad(current[:7] + "-01")
    await report_db.execute(
        update(FeePayment).values(paid_date_ad=first - timedelta(days=1))
    )
    movements = await service.preview(
        actor, request("fee_collection", student, exam, current)
    )
    values = {item["key"]: item["value"] for item in movements["summary"]}
    assert (
        movements["total"] == 1
        and values["gross"] == "0.00"
        and values["refunded"] == "25.00"
        and values["net"] == "-25.00"
    )


@DB_TEST
@pytest.mark.asyncio
async def test_concurrent_generation_retries_create_one_complete_snapshot():
    schema = f"report_test_{uuid4().hex}"
    admin = create_async_engine(settings.database_url, poolclass=NullPool)
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f"CREATE SCHEMA {schema}"))
            for table in TABLES:
                await connection.execute(
                    text(
                        f"CREATE TABLE {schema}.{table} (LIKE public.{table} INCLUDING ALL)"
                    )
                )
        async with AsyncSession(engine, expire_on_commit=False) as db:
            actor, student, exam, current = await seed(db)
            await db.commit()
        data = ReportGenerateRequest(report_type="student_list", request_id=uuid4())

        async def operation():
            async with AsyncSession(engine, expire_on_commit=False) as db:
                report = await ReportService(db).generate_report(actor, data)
                await db.commit()
                return report["id"]

        values = await asyncio.gather(operation(), operation())
        assert values[0] == values[1]
        async with AsyncSession(engine) as db:
            assert await db.scalar(select(func.count()).select_from(Report)) == 1
            assert await db.scalar(select(func.count()).select_from(ReportRow)) == 1
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin.dispose()
