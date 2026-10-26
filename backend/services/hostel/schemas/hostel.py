"""School boarding commands; BS periods and exact NPR amounts."""

import re
import unicodedata
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from services.hostel.models.hostel import HostelType, RoomType
from services.fee.schemas.fee import AcademicYear
from shared.utils.nepali_calendar import NepalCalendar

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Session = Literal["morning", "evening", "breakfast", "lunch", "snacks", "dinner"]


def identifier(value):
    value = unicodedata.normalize("NFC", value.strip().upper())
    if (
        not value
        or not value[0].isalnum()
        or any(
            not c.isalnum()
            and not unicodedata.category(c).startswith("M")
            and c not in "-_./"
            for c in value
        )
    ):
        raise ValueError("Use letters, numbers, -, _, ., or / for room and bed labels")
    return value


def phone(value):
    if value is None or not value.strip():
        return None
    value = re.sub(r"[\s()-]", "", value)
    if not re.fullmatch(r"\+?[0-9]{7,15}", value):
        raise ValueError(
            "Enter a phone number, for example +9779800000000 or a landline with area code"
        )
    return value


class Command(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    request_id: UUID = Field(default_factory=uuid4)


class HostelCreate(Command):
    name: str = Field(min_length=1, max_length=200)
    hostel_type: HostelType
    warden_name: Optional[str] = Field(default=None, max_length=200)
    warden_phone: Optional[str] = Field(default=None, max_length=20)
    address: Optional[str] = Field(default=None, max_length=300)
    notes: Optional[str] = Field(default=None, max_length=1000)
    _phone = field_validator("warden_phone", mode="before")(phone)


class HostelUpdate(HostelCreate):
    is_active: bool = True


class RoomCreate(Command):
    hostel_id: UUID
    room_number: str = Field(min_length=1, max_length=20)
    floor: int = Field(default=0, ge=-5, le=100)
    capacity: int = Field(default=2, ge=1, le=100)
    room_type: RoomType = RoomType.DOUBLE
    monthly_fee: Money = Decimal("0.00")
    notes: Optional[str] = Field(default=None, max_length=1000)
    _number = field_validator("room_number", mode="before")(identifier)


class RoomUpdate(Command):
    room_number: str = Field(min_length=1, max_length=20)
    floor: int = Field(ge=-5, le=100)
    room_type: RoomType
    monthly_fee: Money
    is_active: bool
    notes: Optional[str] = Field(default=None, max_length=1000)
    _number = field_validator("room_number", mode="before")(identifier)


class AddBedsRequest(Command):
    count: int = Field(default=1, ge=1, le=100)
    labels: Optional[list[str]] = Field(default=None, min_length=1, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def labels_match(self):
        if self.labels is not None:
            self.labels = [identifier(value) for value in self.labels]
            if (
                len(self.labels) != self.count
                or len(set(self.labels)) != self.count
                or any(len(value) > 30 for value in self.labels)
            ):
                raise ValueError(
                    "Provide one distinct bed label per new bed, up to 30 characters each"
                )
        return self


class BedUpdate(Command):
    status: Literal["active", "maintenance", "retired"]
    notes: str = Field(min_length=3, max_length=1000)


class AllocateRequest(Command):
    room_id: UUID
    bed_id: Optional[UUID] = None
    student_id: UUID
    academic_year_bs: Optional[AcademicYear] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class TransferRequest(Command):
    room_id: UUID
    bed_id: Optional[UUID] = None
    notes: str = Field(min_length=3, max_length=1000)


class ReasonCommand(Command):
    notes: str = Field(min_length=3, max_length=1000)


class LeaveRequest(Command):
    expected_return_ad: date
    destination: str = Field(min_length=1, max_length=200)
    responsible_person: str = Field(min_length=2, max_length=200)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    reason: str = Field(min_length=3, max_length=1000)
    _phone = field_validator("contact_phone", mode="before")(phone)


class VisitRequest(Command):
    allocation_id: UUID
    visitor_name: str = Field(min_length=2, max_length=200)
    relation: str = Field(min_length=2, max_length=50)
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    purpose: str = Field(min_length=3, max_length=500)
    _phone = field_validator("contact_phone", mode="before")(phone)


class RegisterEntry(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    allocation_id: UUID
    status: Literal["present", "absent", "on_leave", "excused", "taken", "skipped"]
    notes: Optional[str] = Field(default=None, max_length=500)
    version: int = Field(default=0, ge=0)


class RegisterRequest(Command):
    date_ad: date
    session: Session
    entries: list[RegisterEntry] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def valid_entries(self):
        if len({entry.allocation_id for entry in self.entries}) != len(self.entries):
            raise ValueError("Each resident can appear only once in this batch")
        choices = (
            ("present", "absent", "on_leave", "excused")
            if self.session in ("morning", "evening")
            else ("taken", "skipped")
        )
        if any(entry.status not in choices for entry in self.entries):
            raise ValueError(
                "The selected status does not match attendance or meal tracking"
            )
        return self


class BillRequest(Command):
    fee_head_id: UUID
    month_bs: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    due_day_bs: int = Field(default=10, ge=1, le=28)

    @field_validator("month_bs")
    @classmethod
    def supported_month(cls, value):
        NepalCalendar.bs_to_ad(f"{value}-01")
        return value
