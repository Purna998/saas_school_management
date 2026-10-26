"""Hostel request validation and residential-record privacy."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import httpx
import pytest
from pydantic import ValidationError
from main import app
from services.auth.dependencies.auth import get_current_active_user
from services.hostel.schemas.hostel import (
    HostelCreate,
    RoomCreate,
    AddBedsRequest,
    RegisterRequest,
    BillRequest,
)
from shared.database.base import get_db


def test_nepal_room_bed_labels_phone_and_npr_precision():
    hostel = HostelCreate(
        name=" छात्रावास ", hostel_type="mixed", warden_phone="+977 980-000-0000"
    )
    assert hostel.name == "छात्रावास" and hostel.warden_phone == "+9779800000000"
    assert RoomCreate(hostel_id=uuid4(), room_number=" क-१० ").room_number == "क-१०"
    assert AddBedsRequest(count=2, labels=["शय्या-१", "शय्या-२"]).count == 2
    with pytest.raises(ValidationError):
        AddBedsRequest(count=2, labels=["bed-1", "BED-1"])
    with pytest.raises(ValidationError):
        RoomCreate(hostel_id=uuid4(), room_number="101", monthly_fee="100.001")
    with pytest.raises(ValidationError):
        HostelCreate(name="Empty", hostel_type="mixed", capacity=100)


def test_register_does_not_mix_meal_and_rollcall_statuses():
    with pytest.raises(ValidationError, match="does not match"):
        RegisterRequest(
            date_ad="2026-10-26",
            session="evening",
            entries=[{"allocation_id": uuid4(), "status": "taken"}],
        )
    with pytest.raises(ValidationError):
        BillRequest(fee_head_id=uuid4(), month_bs="2083-13")


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["parent", "student"])
async def test_hostel_read_permission_does_not_open_private_resident_registers(role):
    db = AsyncMock()

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(
        school_id=uuid4(),
        has_permission=lambda code: code == "hostel:read",
        has_role=lambda code: code == role,
    )
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for route in [
                "hostels",
                "rooms",
                "students",
                "allocations",
                "leaves",
                "visits",
                "register",
                "history",
                "occupancy",
                "export?report=residents",
            ]:
                assert (
                    await client.get(f"/api/v1/hostel/{route}")
                ).status_code == 403, route
        db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()
