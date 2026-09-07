"""
Nepal School Management System - Calendar API Routes
BS/AD date conversion and academic year endpoints
"""

from fastapi import APIRouter, HTTPException, status, Query

from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import InvalidBSDateError
from services.calendar.services.calendar_service import CalendarService

router = APIRouter()


@router.get("/convert/bs-to-ad")
async def convert_bs_to_ad(
    year: int = Query(..., ge=2000, le=2100, description="BS year"),
    month: int = Query(..., ge=1, le=12, description="BS month"),
    day: int = Query(..., ge=1, le=32, description="BS day"),
):
    """
    Convert Bikram Sambat (BS) date to Gregorian (AD) date.

    Status Codes:
        - 200: Conversion successful
        - 400: Invalid BS date
    """
    try:
        service = CalendarService()
        result = service.convert_bs_to_ad(year, month, day)
        return success_response(data=result)

    except (ValueError, IndexError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(f"Invalid BS date: {year}-{month:02d}-{day:02d}", "INVALID_BS_DATE"),
        )


@router.get("/convert/ad-to-bs")
async def convert_ad_to_bs(
    year: int = Query(..., ge=1944, le=2043, description="AD year"),
    month: int = Query(..., ge=1, le=12, description="AD month"),
    day: int = Query(..., ge=1, le=31, description="AD day"),
):
    """
    Convert Gregorian (AD) date to Bikram Sambat (BS) date.

    Status Codes:
        - 200: Conversion successful
        - 400: Invalid AD date
    """
    try:
        service = CalendarService()
        result = service.convert_ad_to_bs(year, month, day)
        return success_response(data=result)

    except (ValueError, IndexError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(f"Invalid AD date: {year}-{month:02d}-{day:02d}", "INVALID_AD_DATE"),
        )


@router.get("/current-bs")
async def get_current_bs_date():
    """
    Get current date in Bikram Sambat.

    Status Codes:
        - 200: Success
    """
    service = CalendarService()
    result = service.get_current_bs_date()
    return success_response(data=result)


@router.get("/current-academic-year")
async def get_current_academic_year():
    """
    Get current academic year in BS.

    Academic year runs from 1 Baisakh to end of Chaitra.

    Status Codes:
        - 200: Success
    """
    service = CalendarService()
    result = service.get_current_academic_year()
    return success_response(data=result)


@router.get("/months")
async def get_bs_months(
    year: int = Query(..., ge=2000, le=2100, description="BS year")
):
    """
    Get all BS months for a year with days count.

    Status Codes:
        - 200: Success
        - 400: Invalid year
    """
    try:
        service = CalendarService()
        result = service.get_bs_months(year)
        return success_response(data=result)

    except (ValueError, IndexError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(f"Invalid BS year: {year}", "INVALID_BS_YEAR"),
        )


@router.get("/holidays")
async def get_holidays(
    year: int = Query(..., ge=2070, le=2100, description="BS year")
):
    """
    Get national holidays for a BS year.

    Status Codes:
        - 200: Success
    """
    service = CalendarService()
    result = service.get_holidays(year)
    return success_response(data=result)
