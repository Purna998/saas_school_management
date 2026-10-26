"""Typed report inputs; BS civil dates are validated before query construction."""

import re
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from services.fee.schemas.fee import normalize_academic_year
from shared.utils.nepali_calendar import NepalCalendar


def nepali_digits(value):
    return (
        value.translate(str.maketrans("०१२३४५६७८९", "0123456789")).strip()
        if isinstance(value, str)
        else value
    )


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    report_type: str = Field(min_length=2, max_length=40)
    academic_year_bs: str | None = None
    month_bs: str | None = None
    date_from_bs: str | None = None
    date_to_bs: str | None = None
    grade: int | None = Field(None, ge=1, le=12)
    section: str | None = Field(None, min_length=1, max_length=10)
    status: str | None = Field(None, min_length=1, max_length=30)
    period_number: int | None = Field(None, ge=1, le=8)
    exam_id: UUID | None = None
    student_id: UUID | None = None

    @field_validator(
        "academic_year_bs", "month_bs", "date_from_bs", "date_to_bs", mode="before"
    )
    @classmethod
    def digits(cls, value):
        return nepali_digits(value)

    @field_validator("academic_year_bs")
    @classmethod
    def year(cls, value):
        return normalize_academic_year(value) if value else value

    @field_validator("month_bs")
    @classmethod
    def month(cls, value):
        if value:
            if not re.fullmatch(r"\d{4}-\d{2}", value):
                raise ValueError("Use a BS month such as 2083-07")
            NepalCalendar.bs_to_ad(value + "-01")
        return value

    @field_validator("date_from_bs", "date_to_bs")
    @classmethod
    def bs_date(cls, value):
        if value:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Use a BS date in YYYY-MM-DD format")
            NepalCalendar.bs_to_ad(value)
        return value


class ReportGenerateRequest(ReportRequest):
    request_id: UUID
    title: str | None = Field(None, min_length=3, max_length=180)
    file_format: str = "csv"

    @field_validator("file_format")
    @classmethod
    def format(cls, value):
        if value not in ("csv", "excel"):
            raise ValueError(
                "Save CSV or Excel; use Print / Save PDF from a saved report for PDF"
            )
        return value


class ReportArchiveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: UUID
    notes: str = Field(min_length=3, max_length=1000)
