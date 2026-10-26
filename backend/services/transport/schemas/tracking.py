"""Bounded live-tracking inputs. No school or vehicle IDs accepted from senders."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from services.transport.schemas.transport import Command


class FamilyLink(Command):
    student_id: UUID
    parent_email: EmailStr
    notes: str = Field(min_length=3, max_length=1000)


class PhoneIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    label: str = Field(min_length=2, max_length=100)


class LiveFix(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    latitude: Decimal = Field(ge=-90, le=90, max_digits=10, decimal_places=7)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=10, decimal_places=7)
    accuracy_m: Decimal = Field(ge=0, le=10000, max_digits=10, decimal_places=2)
    speed_mps: Decimal | None = Field(None, ge=0, le=60, decimal_places=2)
    heading: Decimal | None = Field(None, ge=0, le=360, decimal_places=2)
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("GPS time must include its time zone")
        return value


class StopProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stop_id: UUID
    stage: Literal["arriving", "at_stop", "departed"]
    version: int = Field(ge=0)
