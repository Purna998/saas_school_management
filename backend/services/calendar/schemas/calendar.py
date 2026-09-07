"""
Nepal School Management System - Calendar Schemas
Pydantic models for calendar/date conversion endpoints
"""

from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field


class BSDate(BaseModel):
    """Bikram Sambat date"""

    year: int = Field(..., ge=2000, le=2100, description="BS year")
    month: int = Field(..., ge=1, le=12, description="BS month (1-12)")
    day: int = Field(..., ge=1, le=32, description="BS day")
    month_name: Optional[str] = Field(None, description="Month name in Nepali")
    day_of_week: Optional[str] = Field(None, description="Day of week")

    class Config:
        json_schema_extra = {
            "example": {
                "year": 2083,
                "month": 3,
                "day": 14,
                "month_name": "जेठ",
                "day_of_week": "शनिवार",
            }
        }


class ADDate(BaseModel):
    """Gregorian (AD) date"""

    year: int = Field(..., description="AD year")
    month: int = Field(..., ge=1, le=12, description="AD month")
    day: int = Field(..., ge=1, le=31, description="AD day")
    iso_date: str = Field(..., description="ISO format date string")

    class Config:
        json_schema_extra = {
            "example": {
                "year": 2026,
                "month": 6,
                "day": 28,
                "iso_date": "2026-06-28",
            }
        }


class ConversionResponse(BaseModel):
    """Date conversion response"""

    bs_date: BSDate
    ad_date: ADDate

    class Config:
        json_schema_extra = {
            "example": {
                "bs_date": {"year": 2083, "month": 3, "day": 14, "month_name": "जेठ"},
                "ad_date": {"year": 2026, "month": 6, "day": 28, "iso_date": "2026-06-28"},
            }
        }


class AcademicYearResponse(BaseModel):
    """Academic year information"""

    academic_year_bs: str = Field(..., description="Academic year in BS (e.g., '2083')")
    start_date_bs: BSDate
    end_date_bs: BSDate
    start_date_ad: ADDate
    end_date_ad: ADDate
    is_current: bool = Field(..., description="Whether this is the current academic year")

    class Config:
        json_schema_extra = {
            "example": {
                "academic_year_bs": "2083",
                "start_date_bs": {"year": 2083, "month": 1, "day": 1},
                "end_date_bs": {"year": 2083, "month": 12, "day": 30},
                "is_current": True,
            }
        }


class BSMonthInfo(BaseModel):
    """BS month information"""

    month_number: int
    name_np: str
    name_en: str
    days_in_month: int


class BSMonthsResponse(BaseModel):
    """List of BS months"""

    year: int
    months: List[BSMonthInfo]


class Holiday(BaseModel):
    """Holiday entry"""

    name_en: str = Field(..., description="Holiday name in English")
    name_np: Optional[str] = Field(None, description="Holiday name in Nepali")
    date_bs: BSDate
    date_ad: ADDate
    holiday_type: str = Field(..., description="Type: national, religious, educational")
    is_school_holiday: bool = Field(default=True)


class HolidayListResponse(BaseModel):
    """Holiday list response"""

    year_bs: int
    holidays: List[Holiday]
    total: int
