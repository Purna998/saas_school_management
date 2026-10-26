"""Transport validation and school residential/location privacy."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import httpx
import pytest
from pydantic import ValidationError
from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.transport.schemas.transport import (
    VehicleCreate,
    RunCreate,
    QuoteRequest,
    StopCreate,
    PositionRequest,
    CompleteTrip,
)
from shared.database.base import get_db


def test_nepal_plate_and_phone_normalization():
    value = VehicleCreate(
        vehicle_number=" बा २ ख-१२३४ ",
        vehicle_type="bus",
        capacity=30,
        driver_phone="+९७७ ९८०-०००-००००",
    )
    assert (
        value.vehicle_number == "बा 2 ख-1234" and value.driver_phone == "+9779800000000"
    )


def test_transport_coordinates_schedules_and_explicit_trip_sweep():
    with pytest.raises(ValidationError):
        StopCreate(stop_name="Test", latitude="27.7")
    with pytest.raises(ValidationError):
        RunCreate(
            name="Test",
            route_id=uuid4(),
            vehicle_id=uuid4(),
            direction="pickup",
            start_time="08:00",
            end_time="07:00",
        )
    with pytest.raises(ValidationError):
        RunCreate(
            name="Test",
            route_id=uuid4(),
            vehicle_id=uuid4(),
            direction="pickup",
            start_time="08:00",
            end_time="09:00",
            weekdays=[0, 0],
        )
    with pytest.raises(ValidationError):
        QuoteRequest(
            transport_type="both", pickup_run_id=uuid4(), pickup_stop_id=uuid4()
        )
    with pytest.raises(ValidationError):
        PositionRequest(
            latitude="27.7", longitude="85.3", recorded_at=datetime(2026, 10, 26)
        )
    with pytest.raises(ValidationError):
        CompleteTrip(notes="Vehicle checked", sweep_confirmed=False)


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["parent", "student"])
async def test_catalog_permission_does_not_expose_transport_or_child_locations(role):
    db = AsyncMock()

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        school_id=uuid4(),
        has_permission=lambda code: code == "transport:read",
        has_role=lambda code: code == role,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for path in [
                "vehicles",
                "routes",
                "runs",
                "students",
                "assignments",
                "trips",
                "stats",
                "history",
                f"vehicles/{uuid4()}/location",
                "export?report=assignments",
            ]:
                assert (
                    await client.get(f"/api/v1/transport/{path}")
                ).status_code == 403, path
        db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
