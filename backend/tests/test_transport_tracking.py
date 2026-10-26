"""Private, phone-first live transport against isolated temporary school records."""

import json
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select, text, update, insert
from main import app
from shared.database.base import get_db
from services.auth.dependencies.auth import get_current_active_user
from services.auth.models.user import User, UserStatus
from services.auth.models.role import Role
from services.student.models.student import Student
from services.transport.models.transport import (
    TransportPassenger,
    TransportLivePosition,
    TransportPhoneSession,
    TransportEvent,
    RouteStop,
)
from services.transport.schemas.transport import (
    StartTrip,
    PassengerUpdate,
    CompleteTrip,
    ReasonCommand,
)
from services.transport.schemas.tracking import FamilyLink, LiveFix, StopProgress
from services.transport.services.tracking_service import TrackingService, distance_m
from services.transport.services.transport_service import TransportConflict, now
from tests.test_transport_postgres import transport_db, seed, assignment, pytestmark  # noqa: F401


@pytest_asyncio.fixture
async def tracking_db(transport_db):  # noqa: F811 - imported pytest fixture
    for table in (
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "transport_family_access",
        "transport_phone_sessions",
        "transport_live_positions",
    ):
        await transport_db.execute(
            text(
                f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP"
            )
        )
    yield transport_db


def member(school, role="parent", *, user_id=None, permissions=()):
    return SimpleNamespace(
        id=user_id or uuid4(),
        school_id=school,
        full_name_en="Synthetic school member",
        has_role=lambda value: value == role,
        has_permission=lambda value: value in permissions,
    )


async def live_seed(db, direction="drop", second=False):
    service, school, student, actor, vehicle, route, stop, pickup, drop = await seed(db)
    await service.command(
        "assign", school, assignment(student, pickup, drop, stop), actor
    )
    if second:
        other = uuid4()
        original = await service.get(Student, school, student)
        await db.execute(
            insert(Student).values(
                id=other,
                school_id=school,
                full_name_en="Other private child",
                gender="OTHER",
                date_of_birth_ad=original.date_of_birth_ad,
                status="ACTIVE",
            )
        )
        await service.command(
            "assign", school, assignment(other, pickup, drop, stop), actor
        )
    trip = await service.command(
        "start_trip",
        school,
        StartTrip(run_id=(drop if direction == "drop" else pickup)["id"]),
        actor,
    )
    service = TrackingService(db)
    admin = member(
        school,
        "school_admin",
        user_id=actor,
        permissions=("transport:create", "transport:read"),
    )
    grant = await service.issue_phone(
        school, UUID(trip["id"]), "Assigned helper", admin
    )
    return service, school, student, admin, trip, grant, stop


def fix(**extra):
    return LiveFix(
        latitude="28.20001",
        longitude="83.98001",
        accuracy_m="8.25",
        recorded_at=now(),
        **extra,
    )


async def linked_parent(db, school, student, service, admin):
    role = Role(id=uuid4(), code="parent", name_en="Parent", permissions=[])
    parent = User(
        id=uuid4(),
        school_id=school,
        email=f"{uuid4().hex}@example.com",
        full_name_en="Synthetic Parent",
        password_hash="synthetic-unused-password-hash",
        status=UserStatus.ACTIVE,
        roles=[role],
    )
    db.add(parent)
    await db.flush()
    request = FamilyLink(
        student_id=student,
        parent_email=parent.email,
        notes="Office verified the guardian record",
    )
    link = await service.command(
        "link_parent", school, request, admin.id, admin.full_name_en
    )
    assert (await service.command("link_parent", school, request, admin.id))[
        "id"
    ] == link["id"]
    return parent, link


@pytest.mark.asyncio
async def test_phone_rotation_expiry_trip_scope_no_secrets_in_audit(tracking_db):
    service, school, student, admin, trip, grant, stop = await live_seed(tracking_db)
    token = grant["token"]
    session, row = await service.phone(token)
    assert session.token_hash != token
    context = service.phone_context(session, row)
    assert context["stops"][0]["name"] == stop["stop_name"]
    assert all(
        key not in json.dumps(context)
        for key in ("Synthetic Rider", "student_id", "parent_email")
    )
    events = (await tracking_db.scalars(select(TransportEvent))).all()
    assert all(
        token not in json.dumps(event.result) + json.dumps(event.payload)
        for event in events
    )
    await tracking_db.execute(
        update(TransportPhoneSession).values(expires_at=now() - timedelta(seconds=1))
    )
    with pytest.raises(HTTPException) as expired:
        await service.ingest(token, fix())
    assert expired.value.status_code == 410


@pytest.mark.asyncio
async def test_phone_latest_fix_throttles_retries_and_rejects_bad_times(tracking_db):
    service, school, student, admin, trip, grant, stop = await live_seed(tracking_db)
    data = fix()
    assert (await service.ingest(grant["token"], data))["accepted"]
    assert not (await service.ingest(grant["token"], data))["accepted"]
    with pytest.raises(HTTPException) as limited:
        await service.ingest(grant["token"], fix())
    assert limited.value.status_code == 429
    for delta in (timedelta(minutes=-3), timedelta(minutes=1)):
        bad = data.model_copy(update={"recorded_at": now() + delta})
        with pytest.raises(ValueError, match="current GPS"):
            await service.ingest(grant["token"], bad)
    await tracking_db.execute(
        update(TransportLivePosition).values(received_at=now() - timedelta(seconds=10))
    )
    assert (await service.ingest(grant["token"], fix()))["accepted"]
    assert (
        await tracking_db.scalar(
            select(func.count()).select_from(TransportLivePosition)
        )
        == 1
    )
    replacement = await service.issue_phone(
        school, UUID(trip["id"]), "Replacement phone", admin
    )
    with pytest.raises(HTTPException) as revoked:
        await service.phone(grant["token"])
    assert revoked.value.status_code == 410
    await service.revoke_phone(school, UUID(trip["id"]), admin)
    with pytest.raises(HTTPException) as revoked:
        await service.ingest(replacement["token"], fix())
    assert revoked.value.status_code == 410


@pytest.mark.asyncio
async def test_family_feed_hides_other_children_and_ends_vehicle_access_after_handover(
    tracking_db,
):
    service, school, student, admin, trip, grant, stop = await live_seed(
        tracking_db, second=True
    )
    parent, link = await linked_parent(tracking_db, school, student, service, admin)
    await service.ingest(grant["token"], fix())
    assert (await service.feed(member(school)))["total"] == 0
    assert (await service.feed(member(uuid4())))["total"] == 0
    feed = await service.feed(parent)
    assert "Other private child" not in json.dumps(feed)
    assert feed["total"] == 1 and feed["audience"] == "family"
    journey = feed["journeys"][0]
    assert (
        journey["child"]["id"] == str(student)
        and journey["stops"] == []
        and journey["progress"] is None
    )
    assert journey["guidance"]["nearby"] is False  # Not yet boarded for the home drop.
    passenger = await tracking_db.scalar(
        select(TransportPassenger).where(
            TransportPassenger.trip_id == UUID(trip["id"]),
            TransportPassenger.student_id == student,
        )
    )
    await service.command(
        "passenger",
        school,
        PassengerUpdate(status="boarded", version=1),
        admin.id,
        resource=passenger.id,
    )
    journey = (await service.feed(parent))["journeys"][0]
    assert journey["guidance"]["nearby"] and journey["guidance"]["distance_m"] < 5
    for private in (
        "driver_phone",
        "received_by",
        "handover_phone",
        "reference",
        "assignment_id",
    ):
        assert private not in json.dumps(journey)
    await service.command(
        "passenger",
        school,
        PassengerUpdate(
            status="alighted", version=2, received_by="Verified receiving adult"
        ),
        admin.id,
        resource=passenger.id,
    )
    journey = (await service.feed(parent))["journeys"][0]
    assert journey["position"] is None and not journey["guidance"]["nearby"]
    other = await tracking_db.scalar(
        select(TransportPassenger).where(
            TransportPassenger.trip_id == UUID(trip["id"]),
            TransportPassenger.student_id != student,
        )
    )
    await service.command(
        "passenger",
        school,
        PassengerUpdate(status="absent", version=1, notes="Absent by school record"),
        admin.id,
        resource=other.id,
    )
    await service.command(
        "complete_trip",
        school,
        CompleteTrip(sweep_confirmed=True, notes="Helper checked empty vehicle"),
        admin.id,
        resource=UUID(trip["id"]),
    )
    with pytest.raises(HTTPException) as ended:
        await service.ingest(grant["token"], fix())
    assert ended.value.status_code == 410
    await service.command(
        "revoke_parent",
        school,
        ReasonCommand(notes="Authorization ended"),
        admin.id,
        resource=UUID(link["id"]),
    )
    assert (await service.feed(parent))["total"] == 0


@pytest.mark.asyncio
async def test_frozen_stops_and_versioned_progress_do_not_leak_another_stop(
    tracking_db,
):
    service, school, student, admin, trip, grant, stop = await live_seed(
        tracking_db, "pickup"
    )
    parent, link = await linked_parent(tracking_db, school, student, service, admin)
    await tracking_db.execute(
        update(RouteStop)
        .where(RouteStop.id == UUID(stop["id"]))
        .values(stop_name="Changed master name", latitude="29.0")
    )
    report = StopProgress(stop_id=stop["id"], stage="at_stop", version=0)
    progress = await service.progress(grant["token"], report)
    assert progress["name"] == stop["stop_name"] and progress["version"] == 1
    assert (await service.progress(grant["token"], report)) == progress
    with pytest.raises(TransportConflict, match="changed"):
        await service.progress(
            grant["token"],
            StopProgress(stop_id=stop["id"], stage="departed", version=0),
        )
    await service.progress(
        grant["token"], StopProgress(stop_id=stop["id"], stage="departed", version=1)
    )
    with pytest.raises(TransportConflict, match="backwards"):
        await service.progress(
            grant["token"],
            StopProgress(stop_id=stop["id"], stage="arriving", version=2),
        )
    with pytest.raises(ValueError, match="this trip"):
        await service.progress(
            grant["token"], StopProgress(stop_id=uuid4(), stage="arriving", version=2)
        )
    journey = (await service.feed(parent))["journeys"][0]
    assert (
        journey["stop"]["name"] == stop["stop_name"]
        and journey["stop"]["latitude"] == "28.2000000"
    )
    assert journey["guidance"]["stop_state"] == "departed"


@pytest.mark.asyncio
async def test_tracking_http_permissions_and_minimal_phone_contract(tracking_db):
    service, school, student, admin, trip, grant, stop = await live_seed(tracking_db)

    async def database():
        yield tracking_db

    app.dependency_overrides[get_db] = database
    current = member(school, "teacher", permissions=("transport:track",))
    app.dependency_overrides[get_current_active_user] = lambda: current
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/transport/live")
            assert response.status_code == 200 and response.json()["data"]["total"] == 1
            assert response.headers["cache-control"] == "no-store, private"
            assert (
                await client.get("/api/v1/transport/family-access")
            ).status_code == 403
            current = member(school, "student", permissions=("transport:track",))
            assert (await client.get("/api/v1/transport/live")).status_code == 403
            assert (
                await client.get("/api/v1/transport/phone/context")
            ).status_code == 401
            response = await client.get(
                "/api/v1/transport/phone/context",
                headers={"X-Transport-Token": grant["token"]},
            )
            assert (
                response.status_code == 200
                and "passengers" not in response.json()["data"]
            )
            payload = fix().model_dump(mode="json")
            payload["vehicle_id"] = str(uuid4())
            assert (
                await client.post(
                    "/api/v1/transport/phone/position",
                    json=payload,
                    headers={"X-Transport-Token": grant["token"]},
                )
            ).status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_active_user, None)


def test_tracking_precision_and_coordinates():
    assert distance_m(28.2, 83.98, 28.2, 83.98) == 0
    for field, value in [
        ("latitude", "91"),
        ("accuracy_m", "-1"),
        ("speed_mps", "NaN"),
    ]:
        data = fix().model_dump() | {field: value}
        with pytest.raises(ValidationError):
            LiveFix(**data)


@pytest.mark.asyncio
async def test_feed_uses_two_queries_and_never_needs_a_per_child_location_query(
    tracking_db,
):
    service, school, student, admin, trip, grant, stop = await live_seed(tracking_db)
    parent, link = await linked_parent(tracking_db, school, student, service, admin)
    count = []
    engine = tracking_db.bind.engine.sync_engine

    def statement(*args):
        count.append(1)

    event.listen(engine, "before_cursor_execute", statement)
    try:
        assert (await service.feed(parent))["total"] == 1
        assert len(count) == 2
        count.clear()
        assert (await service.feed(admin))["total"] == 1
        assert len(count) == 2
    finally:
        event.remove(engine, "before_cursor_execute", statement)
