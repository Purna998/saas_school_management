"""Synthetic PostgreSQL routing/dispatch/fees scenarios; no school records changed."""

import asyncio
import os
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import httpx
import pytest
import pytest_asyncio
from sqlalchemy import insert, select, text, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.transport.models.transport import Vehicle, StudentTransport, TransportTrip
from services.transport.schemas.transport import (
    VehicleCreate,
    RouteCreate,
    StopCreate,
    ReorderStops,
    RunCreate,
    RunUpdate,
    StudentTransportAssign,
    ReasonCommand,
    StartTrip,
    PassengerUpdate,
    CompleteTrip,
    PositionRequest,
    MaintenanceRequest,
    BillRequest,
)
from services.transport.services.transport_service import (
    TransportService,
    TransportConflict,
    today,
    now,
)
from services.student.models.student import Student
from services.fee.models.fee import FeeStructure, FeeHead, FeeLedger, FeeFrequency
from services.fee.services.fee_service import FeeService
from services.fee.schemas.fee import FeePaymentRequest, normalize_academic_year
from shared.database.base import get_db
from shared.config.settings import settings
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NepalCalendar

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1", reason="Opt-in local PostgreSQL tests"
)
TABLES = (
    "vehicles",
    "routes",
    "route_stops",
    "student_transport",
    "transport_runs",
    "transport_trips",
    "transport_passengers",
    "transport_maintenance",
    "transport_positions",
    "transport_charges",
    "transport_events",
    "students",
    "fee_structures",
    "fee_heads",
    "fee_ledger",
    "fee_payments",
)


@pytest_asyncio.fixture
async def transport_db():
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
            full_name_en="Synthetic Rider",
            full_name_np="कृत्रिम विद्यार्थी",
            gender="OTHER",
            date_of_birth_ad=date(2015, 1, 1),
            current_grade=2,
            current_section="A",
            roll_number=1,
            admission_number="ADM-1",
            status="ACTIVE",
        )
    )
    service = TransportService(db)
    vehicle = await service.command(
        "create_vehicle",
        school,
        VehicleCreate(
            vehicle_number="बा २ ख १२३४",
            vehicle_type="bus",
            capacity=capacity,
            driver_name="Synthetic Driver",
            helper_name="Synthetic Helper",
        ),
        actor,
        "Transport office",
    )
    route = await service.command(
        "create_route",
        school,
        RouteCreate(
            name="Synthetic पोखरा Route",
            start_point="टोल",
            end_point="School",
            pickup_fee="1000.25",
            drop_fee="1000.25",
            both_fee="1800.50",
            stops=[
                {
                    "stop_name": "चोक",
                    "pickup_time": "08:10",
                    "drop_time": "15:10",
                    "latitude": "28.20",
                    "longitude": "83.98",
                }
            ],
        ),
        actor,
    )
    stop = (await service.route(school, route["id"]))["stops"][0]
    pickup = await service.command(
        "create_run",
        school,
        RunCreate(
            name="Morning school run",
            route_id=route["id"],
            vehicle_id=vehicle["id"],
            direction="pickup",
            start_time="08:00",
            end_time="09:00",
            weekdays=list(range(7)),
        ),
        actor,
    )
    drop = await service.command(
        "create_run",
        school,
        RunCreate(
            name="Afternoon home run",
            route_id=route["id"],
            vehicle_id=vehicle["id"],
            direction="drop",
            start_time="15:00",
            end_time="16:00",
            weekdays=list(range(7)),
        ),
        actor,
    )
    return service, school, student, actor, vehicle, route, stop, pickup, drop


def assignment(student, pickup, drop, stop, **extra):
    return StudentTransportAssign(
        student_id=student,
        transport_type="both",
        pickup_run_id=pickup["id"],
        drop_run_id=drop["id"],
        pickup_stop_id=stop["id"],
        drop_stop_id=stop["id"],
        **extra,
    )


@pytest.mark.asyncio
async def test_stop_order_prices_assignment_retries_and_reference_checks(transport_db):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db
    )
    second = await service.command(
        "create_stop",
        school,
        StopCreate(stop_name="बजार", both_fee="2000.75"),
        actor,
        resource=route["id"],
    )
    reorder = ReorderStops(
        stop_ids=[second["id"], stop["id"]],
        expected_stop_ids=[stop["id"], second["id"]],
    )
    await service.command("reorder_stops", school, reorder, actor, resource=route["id"])
    assert [
        row["id"] for row in (await service.route(school, route["id"]))["stops"]
    ] == [second["id"], stop["id"]]
    request = assignment(student, pickup, drop, stop)
    assigned = await service.command("assign", school, request, actor)
    assert assigned["monthly_fee"] == "1800.50"
    assert (await service.command("assign", school, request, actor))["id"] == assigned[
        "id"
    ]
    assert (await service.loads(school, [UUID(pickup["id"]), UUID(drop["id"])])) == {
        UUID(pickup["id"]): 1,
        UUID(drop["id"]): 1,
    }
    with pytest.raises(TransportConflict, match="already has active"):
        await service.command(
            "assign", school, assignment(student, pickup, drop, stop), actor
        )
    with pytest.raises(RecordNotFoundError):
        await service.command("assign", uuid4(), request, actor)
    with pytest.raises(RecordNotFoundError):
        await service.command(
            "assign", school, assignment(uuid4(), pickup, drop, stop), actor
        )
    end = ReasonCommand(notes="Service ended at guardian request")
    await service.command("end_assignment", school, end, actor, resource=assigned["id"])
    await service.command("end_assignment", school, end, actor, resource=assigned["id"])
    assert not await service.loads(school, [UUID(pickup["id"])])


@pytest.mark.asyncio
async def test_vehicle_and_driver_overlaps_operating_days_and_capacity(transport_db):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db, 1
    )
    with pytest.raises(TransportConflict, match="overlapping"):
        await service.command(
            "create_run",
            school,
            RunCreate(
                name="Clashing run",
                route_id=route["id"],
                vehicle_id=vehicle["id"],
                direction="pickup",
                start_time="08:30",
                end_time="09:30",
                weekdays=[0],
            ),
            actor,
        )
    await service.command(
        "assign", school, assignment(student, pickup, drop, stop), actor
    )
    other = uuid4()
    await transport_db.execute(
        insert(Student).values(
            id=other,
            school_id=school,
            full_name_en="Second Synthetic Rider",
            gender="OTHER",
            date_of_birth_ad=date(2015, 1, 1),
            current_grade=2,
            status="ACTIVE",
        )
    )
    with pytest.raises(TransportConflict, match="no available seats"):
        await service.command(
            "assign", school, assignment(other, pickup, drop, stop), actor
        )
    details = (await service.runs(school))["runs"]
    assert all(
        row["available_seats"] == 0 and row["assigned_seats"] == 1 for row in details
    )
    with pytest.raises(TransportConflict, match="assignments"):
        await service.command(
            "update_run",
            school,
            RunUpdate(
                **{
                    key: value
                    for key, value in pickup.items()
                    if key not in ("id", "is_active")
                },
                is_active=False,
            ),
            actor,
            resource=pickup["id"],
        )


@pytest.mark.asyncio
async def test_assignment_change_atomicity_and_different_stop_agreed_rate(transport_db):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db
    )
    current = await service.command(
        "assign", school, assignment(student, pickup, drop, stop), actor
    )
    async with transport_db.begin_nested():
        try:
            async with transport_db.begin_nested():
                await service.command(
                    "change_assignment",
                    school,
                    assignment(
                        student,
                        pickup,
                        drop,
                        {"id": str(uuid4())},
                        notes="Wrong stop change",
                    ),
                    actor,
                    resource=current["id"],
                )
        except RecordNotFoundError:
            pass
        assert (await service.get(StudentTransport, school, current["id"])).is_active
    second = await service.command(
        "create_stop",
        school,
        StopCreate(stop_name="Different stop"),
        actor,
        resource=route["id"],
    )
    request = assignment(
        student,
        pickup,
        drop,
        stop,
        notes="Agreed school rate for different stops",
        monthly_fee="1900.01",
    )
    request.drop_stop_id = UUID(second["id"])
    changed = await service.command(
        "change_assignment", school, request, actor, resource=current["id"]
    )
    assert (
        changed["previous_assignment_id"] == current["id"]
        and changed["monthly_fee"] == "1900.01"
    )
    assert not (await service.get(StudentTransport, school, current["id"])).is_active


@pytest.mark.asyncio
async def test_trip_snapshot_boarding_handover_and_sweep_completion(transport_db):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db
    )
    assigned = await service.command(
        "assign", school, assignment(student, pickup, drop, stop), actor
    )
    trip = await service.command(
        "start_trip", school, StartTrip(run_id=drop["id"]), actor
    )
    details = await service.trip(school, trip["id"])
    passenger = details["passengers"][0]
    assert passenger["status"] == "pending" and passenger["requires_handover"]
    with pytest.raises(TransportConflict, match="current trip"):
        await service.command(
            "end_assignment",
            school,
            ReasonCommand(notes="Cannot end while travelling"),
            actor,
            resource=assigned["id"],
        )
    with pytest.raises(TransportConflict, match="pending"):
        await service.command(
            "complete_trip",
            school,
            CompleteTrip(notes="Empty check", sweep_confirmed=True),
            actor,
            resource=trip["id"],
        )
    boarded = PassengerUpdate(status="boarded", version=1)
    await service.command("passenger", school, boarded, actor, resource=passenger["id"])
    await service.command("passenger", school, boarded, actor, resource=passenger["id"])
    with pytest.raises(TransportConflict, match="Another staff"):
        await service.command(
            "passenger",
            school,
            PassengerUpdate(status="alighted", version=1, received_by="Guardian"),
            actor,
            resource=passenger["id"],
        )
    with pytest.raises(ValueError, match="responsible adult"):
        await service.command(
            "passenger",
            school,
            PassengerUpdate(status="alighted", version=2),
            actor,
            resource=passenger["id"],
        )
    with pytest.raises(TransportConflict, match="boarded passengers"):
        await service.command(
            "cancel_trip",
            school,
            ReasonCommand(notes="Cannot cancel boarded trip"),
            actor,
            resource=trip["id"],
        )
    await service.command(
        "passenger",
        school,
        PassengerUpdate(status="alighted", version=2, received_by="Synthetic guardian"),
        actor,
        resource=passenger["id"],
    )
    complete = CompleteTrip(
        notes="Driver and helper checked empty vehicle", sweep_confirmed=True
    )
    await service.command("complete_trip", school, complete, actor, resource=trip["id"])
    assert (
        await service.command(
            "complete_trip", school, complete, actor, resource=trip["id"]
        )
    )["status"] == "completed"
    assert (await service.trip(school, trip["id"]))["counts"] == {"alighted": 1}


@pytest.mark.asyncio
async def test_expired_documents_maintenance_cancelled_restart_and_locations(
    transport_db,
):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db
    )
    await service.command(
        "assign", school, assignment(student, pickup, drop, stop), actor
    )
    record = await service.get(Vehicle, school, vehicle["id"])
    record.insurance_expiry_ad = today() - timedelta(days=1)
    await transport_db.flush()
    summary = await service.stats(school)
    assert summary["total_vehicles"] == 1
    assert summary["expired_document_vehicles"] == 1
    assert (await service.stats(uuid4()))["total_vehicles"] == 0
    with pytest.raises(TransportConflict, match="expired"):
        await service.command(
            "start_trip", school, StartTrip(run_id=pickup["id"]), actor
        )
    record.insurance_expiry_ad = today() + timedelta(days=100)
    record.condition = "maintenance"
    await transport_db.flush()
    summary = await service.stats(school)
    assert summary["maintenance_vehicles"] == 1
    assert summary["available_vehicles"] == 0
    assert summary["expired_document_vehicles"] == 0
    with pytest.raises(TransportConflict, match="available"):
        await service.command(
            "start_trip", school, StartTrip(run_id=pickup["id"]), actor
        )
    record.condition = "available"
    await transport_db.flush()
    trip = await service.command(
        "start_trip", school, StartTrip(run_id=pickup["id"]), actor
    )
    await service.command(
        "cancel_trip",
        school,
        ReasonCommand(notes="Cancelled before any boarding"),
        actor,
        resource=trip["id"],
    )
    replacement = await service.command(
        "start_trip", school, StartTrip(run_id=pickup["id"]), actor
    )
    assert replacement["id"] != trip["id"]
    request = PositionRequest(
        latitude="28.20", longitude="83.98", recorded_at=now(), source="device"
    )
    await service.command("position", school, request, actor, resource=vehicle["id"])
    await service.command("position", school, request, actor, resource=vehicle["id"])
    location = await service.location(school, vehicle["id"])
    assert (
        location["position"]["source"] == "device" and not location["position"]["stale"]
    )
    with pytest.raises(ValueError, match="current position"):
        await service.command(
            "position",
            school,
            PositionRequest(
                latitude="28.20",
                longitude="83.98",
                recorded_at=now() - timedelta(hours=1),
            ),
            actor,
            resource=vehicle["id"],
        )
    with pytest.raises(RecordNotFoundError):
        await service.location(uuid4(), vehicle["id"])
    await service.command(
        "maintenance",
        school,
        MaintenanceRequest(
            service_date_ad=today(),
            kind="inspection",
            cost="25.25",
            notes="Synthetic inspection record",
        ),
        actor,
        resource=vehicle["id"],
    )
    assert (await service.maintenance(school, vehicle["id"]))["records"][0][
        "cost"
    ] == "25.25"


@pytest.mark.asyncio
async def test_transport_bills_use_fee_ledger_and_reassignment_cannot_duplicate_month(
    transport_db,
):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db
    )
    assigned = await service.command(
        "assign", school, assignment(student, pickup, drop, stop), actor
    )
    month = NepalCalendar.ad_to_bs(today())[:7]
    structure = FeeStructure(
        id=uuid4(),
        school_id=school,
        grade="2",
        academic_year_bs=normalize_academic_year(month[:4]),
        name="Synthetic grade fees",
        is_active=True,
    )
    transport_db.add(structure)
    await transport_db.flush()
    head = FeeHead(
        id=uuid4(),
        fee_structure_id=structure.id,
        name="School transport",
        amount="1800.50",
        frequency=FeeFrequency.monthly,
        is_optional=True,
    )
    transport_db.add(head)
    await transport_db.flush()
    assert (await service.fee_options(school, assigned["id"], month))["options"][0][
        "id"
    ] == str(head.id)
    request = BillRequest(fee_head_id=head.id, month_bs=month)
    bill = await service.command(
        "bill", school, request, actor, resource=assigned["id"]
    )
    assert (
        await service.command("bill", school, request, actor, resource=assigned["id"])
    )["ledger_id"] == bill["ledger_id"]
    payment = await FeeService(transport_db).collect_fee(
        school,
        FeePaymentRequest(
            student_id=student, ledger_id=bill["ledger_id"], amount="100.01"
        ),
        actor,
    )
    assert (
        payment.receipt_number.startswith("RCP-")
        and str((await service.get(FeeLedger, school, bill["ledger_id"])).balance)
        == "1700.49"
    )
    changed = await service.command(
        "change_assignment",
        school,
        assignment(student, pickup, drop, stop, notes="Adjusted boarding stop"),
        actor,
        resource=assigned["id"],
    )
    assert (
        await service.command(
            "bill",
            school,
            BillRequest(fee_head_id=head.id, month_bs=month),
            actor,
            resource=changed["id"],
        )
    )["already_billed"]
    assert await transport_db.scalar(select(func.count()).select_from(FeeLedger)) == 1


@pytest.mark.asyncio
async def test_recorded_driver_cannot_dispatch_another_vehicle_while_trip_is_open(
    transport_db,
):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db
    )
    original = await service.get(Vehicle, school, vehicle["id"])
    original.driver_license = "LIC-SHARED"
    await transport_db.flush()
    second_vehicle = await service.command(
        "create_vehicle",
        school,
        VehicleCreate(
            vehicle_number="बागमती 1 क 9999",
            vehicle_type="van",
            capacity=10,
            driver_name="Synthetic shared driver",
            driver_license="LIC-SHARED",
        ),
        actor,
    )
    second_run = await service.command(
        "create_run",
        school,
        RunCreate(
            name="Later pickup",
            route_id=route["id"],
            vehicle_id=second_vehicle["id"],
            direction="pickup",
            start_time="10:00",
            end_time="11:00",
            weekdays=list(range(7)),
        ),
        actor,
    )
    second_student = uuid4()
    await transport_db.execute(
        insert(Student).values(
            id=second_student,
            school_id=school,
            full_name_en="Second rider",
            gender="OTHER",
            date_of_birth_ad=date(2015, 1, 1),
            current_grade=2,
            status="ACTIVE",
        )
    )
    for person, run in [(student, pickup), (second_student, second_run)]:
        await service.command(
            "assign",
            school,
            StudentTransportAssign(
                student_id=person,
                transport_type="pickup",
                pickup_run_id=run["id"],
                pickup_stop_id=stop["id"],
            ),
            actor,
        )
    await service.command("start_trip", school, StartTrip(run_id=pickup["id"]), actor)
    with pytest.raises(TransportConflict, match="driver is still on another trip"):
        await service.command(
            "start_trip", school, StartTrip(run_id=second_run["id"]), actor
        )


@pytest.mark.asyncio
async def test_full_trip_manifest_and_csv_include_125_riders(transport_db):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db, 200
    )
    people = [uuid4() for _ in range(125)]
    await transport_db.execute(
        insert(Student),
        [
            {
                "id": person,
                "school_id": school,
                "full_name_en": f"Synthetic rider {number}",
                "gender": "OTHER",
                "date_of_birth_ad": date(2015, 1, 1),
                "current_grade": 2,
                "status": "ACTIVE",
            }
            for number, person in enumerate(people)
        ],
    )
    await transport_db.execute(
        insert(StudentTransport),
        [
            {
                "id": uuid4(),
                "school_id": school,
                "student_id": person,
                "route_id": UUID(route["id"]),
                "stop_id": UUID(stop["id"]),
                "vehicle_id": UUID(vehicle["id"]),
                "transport_type": "BOTH",
                "monthly_fee": "1800.50",
                "is_active": True,
                "needs_setup": False,
                "pickup_run_id": UUID(pickup["id"]),
                "pickup_stop_id": UUID(stop["id"]),
                "drop_run_id": UUID(drop["id"]),
                "drop_stop_id": UUID(stop["id"]),
                "start_date_ad": today(),
                "snapshot": {"student_name": f"Synthetic rider {number}"},
                "requires_handover": True,
            }
            for number, person in enumerate(people)
        ],
    )
    trip = await service.command(
        "start_trip", school, StartTrip(run_id=pickup["id"]), actor
    )
    page = await service.trip(school, trip["id"])
    full = await service.trip(school, trip["id"], limit=200)
    assert page["total"] == 125 and len(page["passengers"]) == 20
    assert len(full["passengers"]) == 125 and full["counts"] == {"pending": 125}
    content = (await service.export(school, "trip", trip_id=trip["id"])).decode(
        "utf-8-sig"
    )
    import csv, io

    assert len(list(csv.reader(io.StringIO(content)))) == 126


@pytest.mark.asyncio
async def test_http_transport_workflow_csv_safety_and_readonly_permissions(
    transport_db,
):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(
        transport_db
    )
    person = await service.get(Student, school, student)
    person.full_name_en = "=UNTRUSTED"
    await transport_db.flush()

    async def session():
        yield transport_db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        id=actor,
        school_id=school,
        full_name_en="Transport office",
        has_permission=lambda code: True,
        has_role=lambda code: False,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/transport/assign",
                json=assignment(student, pickup, drop, stop).model_dump(mode="json"),
            )
            assert response.status_code == 201, response.text
            for path in [
                "vehicles",
                "routes",
                f"routes/{route['id']}",
                "runs",
                "students",
                "assignments",
                "trips",
                "stats",
                "history",
                f"vehicles/{vehicle['id']}/location",
            ]:
                response = await client.get(f"/api/v1/transport/{path}")
                assert response.status_code == 200, (path, response.text)
            export = await client.get("/api/v1/transport/export?report=assignments")
            assert "'=UNTRUSTED" in export.text
            app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
                id=actor,
                school_id=school,
                full_name_en="Read only",
                has_permission=lambda code: code == "transport:read",
                has_role=lambda code: False,
            )
            assert (
                await client.post(
                    "/api/v1/transport/trips", json={"run_id": pickup["id"]}
                )
            ).status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("same_request", [False, True])
@pytest.mark.parametrize("action", ["assign", "start_trip", "end_assignment"])
async def test_concurrent_last_seat_dispatch_and_repeated_end(action, same_request):
    schema = f"transport_test_{uuid4().hex}"
    admin = create_async_engine(settings.database_url, poolclass=NullPool)
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": f"{schema},public"}},
    )
    try:
        async with admin.begin() as db:
            await db.execute(text(f"CREATE SCHEMA {schema}"))
            for table in TABLES:
                await db.execute(
                    text(
                        f"CREATE TABLE {schema}.{table} (LIKE public.{table} INCLUDING ALL)"
                    )
                )
        async with AsyncSession(engine, expire_on_commit=False) as db:
            (
                service,
                school,
                student,
                actor,
                vehicle,
                route,
                stop,
                pickup,
                drop,
            ) = await seed(db, 1)
            second = uuid4()
            await db.execute(
                insert(Student).values(
                    id=second,
                    school_id=school,
                    full_name_en="Second Synthetic Rider",
                    gender="OTHER",
                    date_of_birth_ad=date(2015, 1, 1),
                    current_grade=2,
                    status="ACTIVE",
                )
            )
            if action != "assign":
                assigned = await service.command(
                    "assign", school, assignment(student, pickup, drop, stop), actor
                )
            await db.commit()
        key = uuid4()

        async def operation(person):
            async with AsyncSession(engine, expire_on_commit=False) as db:
                try:
                    request_key = key if same_request else uuid4()
                    data = (
                        assignment(
                            student if same_request else person,
                            pickup,
                            drop,
                            stop,
                            request_id=request_key,
                        )
                        if action == "assign"
                        else StartTrip(run_id=pickup["id"], request_id=request_key)
                        if action == "start_trip"
                        else ReasonCommand(
                            notes="Service ended", request_id=request_key
                        )
                    )
                    value = await TransportService(db).command(
                        action,
                        school,
                        data,
                        actor,
                        resource=assigned["id"] if action == "end_assignment" else None,
                    )
                    await db.commit()
                    return value["id"]
                except TransportConflict:
                    await db.rollback()
                    return None

        results = await asyncio.gather(operation(student), operation(second))
        assert sum(value is not None for value in results) == (2 if same_request else 1)
        if same_request:
            assert results[0] == results[1]
        async with AsyncSession(engine) as db:
            active = await db.scalar(
                select(func.count())
                .select_from(StudentTransport)
                .where(StudentTransport.is_active.is_(True))
            )
            assert active == (0 if action == "end_assignment" else 1)
            if action == "start_trip":
                assert (
                    await db.scalar(select(func.count()).select_from(TransportTrip))
                    == 1
                )
    finally:
        await engine.dispose()
        async with admin.begin() as db:
            await db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await admin.dispose()
