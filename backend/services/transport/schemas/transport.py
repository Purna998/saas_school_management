"""Validated transport commands; local schedules, BS billing and exact NPR."""

import re
import unicodedata
from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from services.transport.models.transport import VehicleType, TransportType
from shared.utils.nepali_calendar import NepalCalendar

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Latitude = Annotated[Decimal, Field(ge=-90, le=90, max_digits=10, decimal_places=7)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, max_digits=10, decimal_places=7)]
Direction = Literal["pickup", "drop"]


def phone(value):
    if value is not None and not isinstance(value, str):
        raise ValueError("Phone numbers must be text")
    if not value:
        return None
    value = re.sub(r"[\s()-]", "", value)
    value = value.translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    if not re.fullmatch(r"\+?[0-9]{7,15}", value):
        raise ValueError(
            "Enter a phone number with area/country code, such as +9779800000000"
        )
    return value


def plate(value):
    if not isinstance(value, str):
        raise ValueError("Vehicle registration must be text")
    value = unicodedata.normalize(
        "NFC", " ".join(value.strip().upper().split())
    ).translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    if (
        not value
        or not value[0].isalnum()
        or any(
            not c.isalnum()
            and not unicodedata.category(c).startswith("M")
            and c not in " -./"
            for c in value
        )
    ):
        raise ValueError(
            "Enter the vehicle registration in Nepali or English letters and digits"
        )
    return value


class Command(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: UUID = Field(default_factory=uuid4)


class ReasonCommand(Command):
    notes: str = Field(min_length=3, max_length=1000)


class VehicleCreate(Command):
    vehicle_number: str = Field(min_length=1, max_length=30)
    vehicle_type: VehicleType
    capacity: int = Field(ge=1, le=200)
    driver_name: Optional[str] = Field(default=None, max_length=200)
    driver_phone: Optional[str] = Field(default=None, max_length=20)
    driver_license: Optional[str] = Field(default=None, max_length=50)
    helper_name: Optional[str] = Field(default=None, max_length=200)
    helper_phone: Optional[str] = Field(default=None, max_length=20)
    gps_device_id: Optional[str] = Field(default=None, max_length=50)
    condition: Literal["available", "maintenance"] = "available"
    insurance_expiry_ad: Optional[date] = None
    tax_expiry_ad: Optional[date] = None
    fitness_expiry_ad: Optional[date] = None
    permit_expiry_ad: Optional[date] = None
    driver_license_expiry_ad: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    _plate = field_validator("vehicle_number", mode="before")(plate)
    _phones = field_validator("driver_phone", "helper_phone", mode="before")(phone)

    @field_validator(
        "insurance_expiry_ad",
        "tax_expiry_ad",
        "fitness_expiry_ad",
        "permit_expiry_ad",
        "driver_license_expiry_ad",
    )
    @classmethod
    def supported_date(cls, value):
        if value:
            NepalCalendar.ad_to_bs(value)
        return value

    @model_validator(mode="after")
    def maintenance_reason(self):
        if self.condition == "maintenance" and (not self.notes or len(self.notes) < 3):
            raise ValueError("Record the reason for putting a vehicle in maintenance")
        return self


class VehicleUpdate(VehicleCreate):
    is_active: bool = True


class StopDetails(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    stop_name: str = Field(min_length=1, max_length=200)
    pickup_time: Optional[time] = None
    drop_time: Optional[time] = None
    latitude: Optional[Latitude] = None
    longitude: Optional[Longitude] = None
    pickup_fee: Optional[Money] = None
    drop_fee: Optional[Money] = None
    both_fee: Optional[Money] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("pickup_time", "drop_time")
    @classmethod
    def local_time(cls, value):
        if value and value.tzinfo:
            raise ValueError("Enter local Nepal time without a UTC offset")
        return value

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both latitude and longitude, or leave both blank")
        return self


class RouteDetails(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    start_point: str = Field(min_length=1, max_length=200)
    end_point: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=500)
    distance_km: Optional[
        Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2)]
    ] = None
    estimated_time_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    pickup_fee: Money = Decimal("0.00")
    drop_fee: Money = Decimal("0.00")
    both_fee: Money = Decimal("0.00")


class RouteCreate(Command, RouteDetails):
    stops: list[StopDetails] = Field(default_factory=list, max_length=100)


class RouteUpdate(Command, RouteDetails):
    is_active: bool = True


class StopCreate(Command, StopDetails):
    pass


class StopUpdate(Command, StopDetails):
    is_active: bool = True


class ReorderStops(Command):
    stop_ids: list[UUID] = Field(min_length=1, max_length=200)
    expected_stop_ids: list[UUID] = Field(min_length=1, max_length=200)

    @field_validator("stop_ids")
    @classmethod
    def distinct(cls, value):
        if len(value) != len(set(value)):
            raise ValueError("List every active stop exactly once")
        return value


class RunCreate(Command):
    name: str = Field(min_length=1, max_length=200)
    route_id: UUID
    vehicle_id: UUID
    direction: Direction
    start_time: time
    end_time: time
    weekdays: list[int] = Field(
        default_factory=lambda: list(range(6)), min_length=1, max_length=7
    )
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def valid_schedule(self):
        if (
            self.start_time.tzinfo
            or self.end_time.tzinfo
            or self.end_time <= self.start_time
        ):
            raise ValueError("Enter a same-day Nepal time window with end after start")
        if len(set(self.weekdays)) != len(self.weekdays) or any(
            day < 0 or day > 6 for day in self.weekdays
        ):
            raise ValueError(
                "Select distinct operating days from Sunday (0) through Saturday (6)"
            )
        self.weekdays.sort()
        return self


class RunUpdate(RunCreate):
    is_active: bool = True


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transport_type: TransportType = TransportType.BOTH
    pickup_run_id: Optional[UUID] = None
    drop_run_id: Optional[UUID] = None
    pickup_stop_id: Optional[UUID] = None
    drop_stop_id: Optional[UUID] = None

    @model_validator(mode="after")
    def valid_legs(self):
        pickup = self.transport_type in (TransportType.PICKUP, TransportType.BOTH)
        drop = self.transport_type in (TransportType.DROP, TransportType.BOTH)
        if (
            pickup != (self.pickup_run_id is not None)
            or pickup != (self.pickup_stop_id is not None)
            or drop != (self.drop_run_id is not None)
            or drop != (self.drop_stop_id is not None)
        ):
            raise ValueError(
                "Choose a run and stop for each requested direction, and clear unused directions"
            )
        return self


class StudentTransportAssign(Command, QuoteRequest):
    student_id: UUID
    monthly_fee: Optional[Money] = None
    requires_handover: bool = True
    handover_contact: Optional[str] = Field(default=None, max_length=200)
    handover_phone: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=1000)
    _phone = field_validator("handover_phone", mode="before")(phone)


class StartTrip(Command):
    run_id: UUID
    notes: Optional[str] = Field(default=None, max_length=1000)


class PassengerUpdate(Command):
    status: Literal["boarded", "alighted", "absent"]
    version: int = Field(ge=1)
    received_by: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=1000)


class CompleteTrip(ReasonCommand):
    sweep_confirmed: bool

    @field_validator("sweep_confirmed")
    @classmethod
    def confirmation(cls, value):
        if not value:
            raise ValueError(
                "Confirm the driver/helper has checked the vehicle is empty"
            )
        return value


class MaintenanceRequest(ReasonCommand):
    service_date_ad: date
    kind: Literal["service", "repair", "inspection", "insurance", "tax", "permit"]
    odometer_km: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    cost: Money = Decimal("0.00")
    next_due_ad: Optional[date] = None
    vendor: Optional[str] = Field(default=None, max_length=200)


class PositionRequest(Command):
    latitude: Latitude
    longitude: Longitude
    accuracy_m: Optional[
        Annotated[Decimal, Field(ge=0, le=10_000, max_digits=10, decimal_places=2)]
    ] = None
    recorded_at: datetime
    source: Literal["manual", "device"] = "manual"

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Location timestamps must include a timezone")
        return value


class BillRequest(Command):
    fee_head_id: UUID
    month_bs: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    due_day_bs: int = Field(default=10, ge=1, le=28)

    @field_validator("month_bs")
    @classmethod
    def supported_month(cls, value):
        NepalCalendar.bs_to_ad(f"{value}-01")
        return value
