"""Synthetic PostgreSQL hostel scenarios; no real resident data is changed."""

import asyncio
import os
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
import pytest_asyncio
from sqlalchemy import insert, select, text, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.hostel.models.hostel import Hostel, Room, RoomAllocation, AllocationStatus
from services.hostel.schemas.hostel import (
    HostelCreate,
    HostelUpdate,
    RoomCreate,
    AddBedsRequest,
    BedUpdate,
    AllocateRequest,
    TransferRequest,
    ReasonCommand,
    LeaveRequest,
    VisitRequest,
    Command,
    RegisterRequest,
    BillRequest,
)
from services.hostel.services.hostel_service import HostelService, HostelConflict, today
from services.student.models.student import Student
from services.fee.models.fee import FeeStructure, FeeHead, FeeLedger, FeeFrequency
from services.fee.services.fee_service import FeeService
from services.fee.schemas.fee import FeePaymentRequest
from shared.database.base import get_db
from shared.config.settings import settings
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NepalCalendar

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1", reason="Opt-in local PostgreSQL tests"
)
TABLES = (
    "hostels",
    "hostel_rooms",
    "hostel_beds",
    "room_allocations",
    "hostel_leaves",
    "hostel_visits",
    "hostel_register",
    "hostel_charges",
    "hostel_events",
    "students",
    "fee_structures",
    "fee_heads",
    "fee_ledger",
    "fee_payments",
)


@pytest_asyncio.fixture
async def hostel_db():
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


async def seed(db, capacity=2):
    school, student, actor = uuid4(), uuid4(), uuid4()
    await db.execute(
        insert(Student).values(
            id=student,
            school_id=school,
            full_name_en="Synthetic Hostel Student",
            gender="OTHER",
            date_of_birth_ad=date(2015, 1, 1),
            current_grade=2,
            current_section="A",
            status="ACTIVE",
            admission_number="ADM-1",
        )
    )
    service = HostelService(db)
    hostel = await service.command(
        "create_hostel",
        school,
        HostelCreate(name="Synthetic छात्रावास", hostel_type="mixed"),
        actor,
        "Warden",
    )
    room = await service.command(
        "create_room",
        school,
        RoomCreate(
            hostel_id=hostel["id"],
            room_number="क-१०",
            capacity=capacity,
            monthly_fee="2500.25",
        ),
        actor,
        "Warden",
    )
    return service, school, student, actor, hostel, room


@pytest.mark.asyncio
async def test_derived_bed_capacity_maintenance_and_archive(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)
    inventory = await service.beds(school, room["id"])
    assert len(inventory["beds"]) == 2
    bed = inventory["beds"][0]
    await service.command(
        "update_bed",
        school,
        BedUpdate(status="maintenance", notes="Repairing bed frame"),
        actor,
        resource_id=bed["id"],
    )
    assert (await service.occupancy(school))["available_beds"] == 1
    assert (await service.occupancy(school))["maintenance_beds"] == 1
    await service.command(
        "update_bed",
        school,
        BedUpdate(status="retired", notes="Frame beyond repair"),
        actor,
        resource_id=bed["id"],
    )
    assert (await service.get(Room, school, room["id"])).capacity == 1
    add = AddBedsRequest(count=2, labels=["शय्या-१", "शय्या-२"])
    await service.command("add_beds", school, add, actor, resource_id=room["id"])
    await service.command("add_beds", school, add, actor, resource_id=room["id"])
    assert (await service.get(Room, school, room["id"])).capacity == 3
    assert (await service.get(Hostel, school, hostel["id"])).capacity == 3
    with pytest.raises(RecordNotFoundError):
        await service.beds(uuid4(), room["id"])


@pytest.mark.asyncio
async def test_allocation_checkout_retry_and_single_active_student(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)
    request = AllocateRequest(room_id=room["id"], student_id=student)
    stay = await service.command("allocate", school, request, actor)
    assert (await service.command("allocate", school, request, actor))["id"] == stay[
        "id"
    ]
    assert (await service.occupancy(school))["total_occupied"] == 1
    with pytest.raises(HostelConflict, match="active hostel stay"):
        await service.command(
            "allocate",
            school,
            AllocateRequest(room_id=room["id"], student_id=student),
            actor,
        )
    with pytest.raises(HostelConflict, match="resident"):
        await service.command(
            "update_bed",
            school,
            BedUpdate(status="maintenance", notes="Cannot change occupied"),
            actor,
            resource_id=stay["bed_id"],
        )
    with pytest.raises(HostelConflict, match="all residents"):
        await service.command(
            "update_hostel",
            school,
            HostelUpdate(name=hostel["name"], hostel_type="mixed", is_active=False),
            actor,
            resource_id=hostel["id"],
        )
    checkout = ReasonCommand(notes="Guardian collected student")
    await service.command("vacate", school, checkout, actor, resource_id=stay["id"])
    await service.command("vacate", school, checkout, actor, resource_id=stay["id"])
    assert (await service.occupancy(school))["available_beds"] == 2
    with pytest.raises(HostelConflict, match="already"):
        await service.command(
            "vacate",
            school,
            ReasonCommand(notes="Repeated checkout"),
            actor,
            resource_id=stay["id"],
        )
    assert (await service.occupancy(school))["total_occupied"] == 0
    readmitted = await service.command(
        "allocate",
        school,
        AllocateRequest(room_id=room["id"], student_id=student),
        actor,
    )
    roster = await service.register(school, today(), "evening")
    assert roster["total"] == 1 and roster["entries"][0]["id"] == readmitted["id"]


@pytest.mark.asyncio
async def test_same_school_eligibility_gender_and_disabled_rooms(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)
    with pytest.raises(RecordNotFoundError):
        await service.command(
            "allocate",
            school,
            AllocateRequest(room_id=room["id"], student_id=uuid4()),
            actor,
        )
    with pytest.raises(RecordNotFoundError):
        await service.command(
            "allocate",
            uuid4(),
            AllocateRequest(room_id=room["id"], student_id=student),
            actor,
        )
    await service.command(
        "update_hostel",
        school,
        HostelUpdate(name=hostel["name"], hostel_type="boys"),
        actor,
        resource_id=hostel["id"],
    )
    with pytest.raises(HostelConflict, match="hostel type"):
        await service.command(
            "allocate",
            school,
            AllocateRequest(room_id=room["id"], student_id=student),
            actor,
        )
    await service.command(
        "update_hostel",
        school,
        HostelUpdate(name=hostel["name"], hostel_type="mixed"),
        actor,
        resource_id=hostel["id"],
    )
    entry = await service.get(Student, school, student)
    entry.is_deleted = True
    await hostel_db.flush()
    assert (await service.students(school))["total"] == 0
    with pytest.raises(HostelConflict, match="active student"):
        await service.command(
            "allocate",
            school,
            AllocateRequest(room_id=room["id"], student_id=student),
            actor,
        )


@pytest.mark.asyncio
async def test_transfer_is_atomic_and_preserves_stay_and_price_snapshots(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)
    stay = await service.command(
        "allocate",
        school,
        AllocateRequest(room_id=room["id"], student_id=student),
        actor,
    )
    other = await service.command(
        "create_room",
        school,
        RoomCreate(
            hostel_id=hostel["id"], room_number="102", capacity=1, monthly_fee="3000"
        ),
        actor,
    )
    async with hostel_db.begin_nested():
        try:
            async with hostel_db.begin_nested():
                await service.command(
                    "transfer",
                    school,
                    TransferRequest(room_id=uuid4(), notes="Wrong destination test"),
                    actor,
                    resource_id=stay["id"],
                )
        except RecordNotFoundError:
            pass
        original = await service.get(RoomAllocation, school, stay["id"])
        assert original.status == AllocationStatus.ACTIVE
    transfer = TransferRequest(room_id=other["id"], notes="Moved for study group")
    new_stay = await service.command(
        "transfer", school, transfer, actor, resource_id=stay["id"]
    )
    assert (
        new_stay["previous_allocation_id"] == stay["id"]
        and new_stay["monthly_fee"] == "3000.00"
    )
    assert (
        await service.command(
            "transfer", school, transfer, actor, resource_id=stay["id"]
        )
    )["id"] == new_stay["id"]
    previous = await service.get(RoomAllocation, school, stay["id"])
    assert (
        previous.status == AllocationStatus.VACATED
        and str(previous.monthly_fee) == "2500.25"
    )
    assert (await service.occupancy(school))["total_occupied"] == 1
    roster = await service.register(school, today(), "evening")
    assert roster["total"] == 1 and roster["entries"][0]["id"] == new_stay["id"]
    for stay_id in (stay["id"], new_stay["id"]):
        assert any(
            event["action"] == "transfer"
            for event in (await service.history(school, allocation_id=stay_id))[
                "events"
            ]
        )


@pytest.mark.asyncio
async def test_leave_reserves_bed_and_visitor_checkout_blocks_transfer(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)
    stay = await service.command(
        "allocate",
        school,
        AllocateRequest(room_id=room["id"], student_id=student),
        actor,
    )
    leave = await service.command(
        "leave",
        school,
        LeaveRequest(
            expected_return_ad=today() + timedelta(days=1),
            destination="पोखरा",
            responsible_person="Synthetic guardian",
            contact_phone="+9779800000000",
            reason="Family visit approved by warden",
        ),
        actor,
        resource_id=stay["id"],
    )
    assert (await service.occupancy(school))["on_leave"] == 1
    assert (await service.occupancy(school))["available_beds"] == 1
    with pytest.raises(HostelConflict, match="return from leave"):
        await service.command(
            "vacate",
            school,
            ReasonCommand(notes="Cannot check out while away"),
            actor,
            resource_id=stay["id"],
        )
    await service.command(
        "return_leave",
        school,
        ReasonCommand(notes="Returned with guardian"),
        actor,
        resource_id=leave["id"],
    )
    visit = await service.command(
        "visit",
        school,
        VisitRequest(
            allocation_id=stay["id"],
            visitor_name="Synthetic guardian",
            relation="Guardian",
            purpose="Meet resident",
        ),
        actor,
    )
    with pytest.raises(HostelConflict, match="open visitors"):
        await service.command(
            "vacate",
            school,
            ReasonCommand(notes="Cannot leave with open visitor"),
            actor,
            resource_id=stay["id"],
        )
    await service.command(
        "depart_visit", school, Command(), actor, resource_id=visit["id"]
    )
    await service.command(
        "vacate",
        school,
        ReasonCommand(notes="Final checkout approved"),
        actor,
        resource_id=stay["id"],
    )
    assert (await service.movements(school, "leaves", status="closed"))["total"] == 1
    assert (await service.movements(school, "visits", status="closed"))["total"] == 1


@pytest.mark.asyncio
async def test_attendance_meal_register_versions_retry_and_csv_safety(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)
    person = await service.get(Student, school, student)
    person.full_name_en = "=UNTRUSTED"
    await hostel_db.flush()
    stay = await service.command(
        "allocate",
        school,
        AllocateRequest(room_id=room["id"], student_id=student),
        actor,
    )
    request = RegisterRequest(
        date_ad=today(),
        session="evening",
        entries=[{"allocation_id": stay["id"], "status": "present"}],
    )
    await service.command("save_register", school, request, actor)
    await service.command("save_register", school, request, actor)
    assert (await service.register(school, today(), "evening"))["entries"][0][
        "version"
    ] == 1
    with pytest.raises(HostelConflict, match="Another staff"):
        await service.command(
            "save_register",
            school,
            RegisterRequest(
                date_ad=today(),
                session="evening",
                entries=[
                    {
                        "allocation_id": stay["id"],
                        "status": "absent",
                        "notes": "Warden following up",
                    }
                ],
            ),
            actor,
        )
    await service.command(
        "save_register",
        school,
        RegisterRequest(
            date_ad=today(),
            session="dinner",
            entries=[{"allocation_id": stay["id"], "status": "taken"}],
        ),
        actor,
    )
    history = await service.history(school, allocation_id=stay["id"])
    assert any(
        event["register_changes"] and event["register_changes"][0]["status"] == "taken"
        for event in history["events"]
    )
    exported = await service.export(school, "register", day=today(), session="dinner")
    assert "'=UNTRUSTED" in exported.decode("utf-8-sig") and "taken" in exported.decode(
        "utf-8-sig"
    )
    with pytest.raises(ValueError, match="future"):
        await service.register(school, today() + timedelta(days=1), "evening")


@pytest.mark.asyncio
async def test_hostel_billing_posts_once_to_existing_fee_ledger(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)
    stay = await service.command(
        "allocate",
        school,
        AllocateRequest(room_id=room["id"], student_id=student),
        actor,
    )
    month = NepalCalendar.ad_to_bs(today())[:7]
    structure = FeeStructure(
        id=uuid4(),
        school_id=school,
        grade="2",
        academic_year_bs=stay["academic_year_bs"],
        name="Synthetic grade fee",
        is_active=True,
    )
    hostel_db.add(structure)
    await hostel_db.flush()
    head = FeeHead(
        id=uuid4(),
        fee_structure_id=structure.id,
        name="Hostel accommodation",
        amount="2500.25",
        frequency=FeeFrequency.monthly,
        is_optional=True,
    )
    hostel_db.add(head)
    await hostel_db.flush()
    options = await service.fee_options(school, stay["id"], month)
    assert options["options"][0]["id"] == str(head.id)
    request = BillRequest(fee_head_id=head.id, month_bs=month)
    billed = await service.command(
        "bill", school, request, actor, resource_id=stay["id"]
    )
    assert billed["amount"] == "2500.25" and not billed["already_billed"]
    assert (
        await service.command("bill", school, request, actor, resource_id=stay["id"])
    )["ledger_id"] == billed["ledger_id"]
    assert (
        await service.command(
            "bill",
            school,
            BillRequest(fee_head_id=head.id, month_bs=month),
            actor,
            resource_id=stay["id"],
        )
    )["already_billed"]
    assert await hostel_db.scalar(select(func.count()).select_from(FeeLedger)) == 1
    ledger = await service.get(FeeLedger, school, billed["ledger_id"])
    assert str(ledger.balance) == "2500.25" and ledger.month_bs == month
    payment = await FeeService(hostel_db).collect_fee(
        school,
        FeePaymentRequest(student_id=student, ledger_id=ledger.id, amount="100.01"),
        actor,
    )
    assert (
        payment.receipt_number.startswith("RCP-") and str(ledger.balance) == "2400.24"
    )
    other = await service.command(
        "create_room",
        school,
        RoomCreate(
            hostel_id=hostel["id"], room_number="102", capacity=1, monthly_fee="3000"
        ),
        actor,
    )
    transferred = await service.command(
        "transfer",
        school,
        TransferRequest(room_id=other["id"], notes="Mid-month room transfer"),
        actor,
        resource_id=stay["id"],
    )
    new_head = FeeHead(
        id=uuid4(),
        fee_structure_id=structure.id,
        name="Different hostel rate",
        amount="3000",
        frequency=FeeFrequency.monthly,
        is_optional=True,
    )
    hostel_db.add(new_head)
    await hostel_db.flush()
    with pytest.raises(HostelConflict, match="already has a hostel bill"):
        await service.command(
            "bill",
            school,
            BillRequest(fee_head_id=new_head.id, month_bs=month),
            actor,
            resource_id=transferred["id"],
        )
    assert await hostel_db.scalar(select(func.count()).select_from(FeeLedger)) == 1


@pytest.mark.asyncio
async def test_http_hostel_routes_and_read_only_mutation_permissions(hostel_db):
    service, school, student, actor, hostel, room = await seed(hostel_db)

    async def session():
        yield hostel_db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=actor,
        school_id=school,
        full_name_en="Warden",
        has_permission=lambda code: True,
        has_role=lambda role: False,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/hostel/allocate",
                json={
                    "room_id": room["id"],
                    "student_id": str(student),
                    "request_id": str(uuid4()),
                },
            )
            assert response.status_code == 201, response.text
            for path in [
                "hostels",
                "rooms",
                f"rooms/{room['id']}/beds",
                "allocations",
                "students",
                "leaves",
                "visits",
                "register",
                "history",
                "occupancy",
                "export?report=residents",
            ]:
                response = await client.get(f"/api/v1/hostel/{path}")
                assert response.status_code == 200, (path, response.text)
            app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
                id=actor,
                school_id=school,
                full_name_en="Read only",
                has_permission=lambda code: code == "hostel:read",
                has_role=lambda role: False,
            )
            forbidden = await client.post(
                "/api/v1/hostel/allocate",
                json={"room_id": room["id"], "student_id": str(student)},
            )
            assert forbidden.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("same_request", [False, True])
@pytest.mark.parametrize("action", ["allocate", "vacate"])
async def test_concurrent_last_bed_allocation_and_checkout(action, same_request):
    schema = f"hostel_test_{uuid4().hex}"
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
            service, school, student, actor, hostel, room = await seed(db, 1)
            second = uuid4()
            await db.execute(
                insert(Student).values(
                    id=second,
                    school_id=school,
                    full_name_en="Second synthetic boarder",
                    gender="OTHER",
                    date_of_birth_ad=date(2015, 1, 1),
                    current_grade=2,
                    status="ACTIVE",
                )
            )
            if action == "vacate":
                stay = await service.command(
                    "allocate",
                    school,
                    AllocateRequest(room_id=room["id"], student_id=student),
                    actor,
                )
            await db.commit()
        key = uuid4()

        async def operation(person):
            async with AsyncSession(engine, expire_on_commit=False) as db:
                try:
                    data = (
                        AllocateRequest(
                            room_id=room["id"],
                            student_id=student if same_request else person,
                            request_id=key if same_request else uuid4(),
                        )
                        if action == "allocate"
                        else ReasonCommand(
                            notes="Final checkout",
                            request_id=key if same_request else uuid4(),
                        )
                    )
                    value = await HostelService(db).command(
                        action,
                        school,
                        data,
                        actor,
                        resource_id=None if action == "allocate" else stay["id"],
                    )
                    await db.commit()
                    return value["id"]
                except HostelConflict:
                    await db.rollback()
                    return None

        results = await asyncio.gather(operation(student), operation(second))
        assert sum(value is not None for value in results) == (2 if same_request else 1)
        if same_request:
            assert results[0] == results[1]
        async with AsyncSession(engine) as db:
            stats = await HostelService(db).occupancy(school)
            assert stats["total_occupied"] == (1 if action == "allocate" else 0)
            assert stats["available_beds"] == (0 if action == "allocate" else 1)
    finally:
        await engine.dispose()
        async with admin.begin() as db:
            await db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin.dispose()
