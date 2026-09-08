"""
Nepal School Management System - Bikram Sambat (BS) Calendar Utilities
Handles BS <-> AD date conversion and Nepal timezone (NPT UTC+5:45)
"""

from datetime import datetime, date
from typing import Tuple
import pytz
from nepali_datetime import datetime as nepali_datetime, date as nepali_date


# Nepal Timezone
NPT = pytz.timezone("Asia/Kathmandu")


class NepalCalendar:
    """Utilities for Bikram Sambat calendar and Nepal timezone"""

    @staticmethod
    def bs_to_ad(bs_date_str: str) -> date:
        """
        Convert Bikram Sambat date to Gregorian (AD) date.

        Args:
            bs_date_str: BS date in format 'YYYY-MM-DD' (e.g., '2081-04-15')

        Returns:
            Gregorian date object

        Raises:
            ValueError: If BS date is invalid
        """
        try:
            # Parse BS date
            year, month, day = map(int, bs_date_str.split('-'))
            bs_date = nepali_date(year, month, day)

            # Convert to AD
            ad_date = bs_date.to_datetime_date()
            return ad_date

        except Exception as e:
            raise ValueError(f"Invalid BS date '{bs_date_str}': {str(e)}")

    @staticmethod
    def ad_to_bs(ad_date: date | datetime) -> str:
        """
        Convert Gregorian (AD) date to Bikram Sambat date string.

        Args:
            ad_date: Gregorian date or datetime object

        Returns:
            BS date string in format 'YYYY-MM-DD'
        """
        try:
            # Handle datetime objects
            if isinstance(ad_date, datetime):
                ad_date = ad_date.date()

            # Convert to BS
            bs_date = nepali_date.from_datetime_date(ad_date)
            return f"{bs_date.year:04d}-{bs_date.month:02d}-{bs_date.day:02d}"

        except Exception as e:
            raise ValueError(f"Invalid AD date '{ad_date}': {str(e)}")

    @staticmethod
    def validate_bs_date(bs_date_str: str) -> bool:
        """
        Validate if BS date string is valid.

        Args:
            bs_date_str: BS date in format 'YYYY-MM-DD'

        Returns:
            True if valid, False otherwise
        """
        try:
            year, month, day = map(int, bs_date_str.split('-'))
            nepali_date(year, month, day)
            return True
        except Exception:
            return False

    @staticmethod
    def current_bs_date() -> str:
        """
        Get current date in BS format (based on NPT timezone).

        Returns:
            Current BS date string in format 'YYYY-MM-DD'
        """
        now_npt = datetime.now(NPT)
        bs_date = nepali_datetime.from_datetime_datetime(now_npt)
        return f"{bs_date.year:04d}-{bs_date.month:02d}-{bs_date.day:02d}"

    @staticmethod
    def current_bs_datetime() -> nepali_datetime:
        """
        Get current datetime in BS (based on NPT timezone).

        Returns:
            nepali_datetime object
        """
        now_npt = datetime.now(NPT)
        return nepali_datetime.from_datetime_datetime(now_npt)

    @staticmethod
    def utc_to_npt(utc_dt: datetime) -> datetime:
        """
        Convert UTC datetime to NPT (Asia/Kathmandu).

        Args:
            utc_dt: UTC datetime object

        Returns:
            NPT datetime object
        """
        if utc_dt.tzinfo is None:
            utc_dt = pytz.utc.localize(utc_dt)
        return utc_dt.astimezone(NPT)

    @staticmethod
    def npt_to_utc(npt_dt: datetime) -> datetime:
        """
        Convert NPT datetime to UTC.

        Args:
            npt_dt: NPT datetime object

        Returns:
            UTC datetime object
        """
        if npt_dt.tzinfo is None:
            npt_dt = NPT.localize(npt_dt)
        return npt_dt.astimezone(pytz.utc)

    @staticmethod
    def get_current_academic_year_bs() -> str:
        """
        Get current academic year in BS format (e.g., '2081-2082').
        Academic year starts from Baisakh 1 (mid-April).

        Returns:
            Academic year string (e.g., '2081-2082')
        """
        current_bs = NepalCalendar.current_bs_datetime()

        # If before Baisakh (month 1), use previous year
        if current_bs.month < 1:
            start_year = current_bs.year - 1
        else:
            start_year = current_bs.year

        return f"{start_year:04d}-{(start_year + 1):04d}"

    @staticmethod
    def get_bs_month_name(month: int, language: str = "en") -> str:
        """
        Get Nepali month name.

        Args:
            month: Month number (1-12)
            language: 'en' for English, 'np' for Nepali

        Returns:
            Month name string
        """
        months_en = [
            "Baisakh", "Jestha", "Ashadh", "Shrawan",
            "Bhadra", "Ashwin", "Kartik", "Mangsir",
            "Poush", "Magh", "Falgun", "Chaitra"
        ]

        months_np = [
            "बैशाख", "जेठ", "असार", "श्रावण",
            "भाद्र", "आश्विन", "कार्तिक", "मंसिर",
            "पौष", "माघ", "फाल्गुन", "चैत्र"
        ]

        if month < 1 or month > 12:
            raise ValueError(f"Invalid month: {month}")

        return months_np[month - 1] if language == "np" else months_en[month - 1]

    @staticmethod
    def parse_bs_date(bs_date_str: str) -> Tuple[int, int, int]:
        """
        Parse BS date string into year, month, day.

        Args:
            bs_date_str: BS date in format 'YYYY-MM-DD'

        Returns:
            Tuple of (year, month, day)

        Raises:
            ValueError: If format is invalid
        """
        try:
            parts = bs_date_str.split('-')
            if len(parts) != 3:
                raise ValueError("Date must be in YYYY-MM-DD format")

            year, month, day = map(int, parts)

            if year < 2000 or year > 2200:
                raise ValueError(f"Invalid year: {year}")
            if month < 1 or month > 12:
                raise ValueError(f"Invalid month: {month}")
            if day < 1 or day > 32:
                raise ValueError(f"Invalid day: {day}")

            return year, month, day

        except Exception as e:
            raise ValueError(f"Invalid BS date format '{bs_date_str}': {str(e)}")

    @staticmethod
    def format_bs_date(year: int, month: int, day: int) -> str:
        """
        Format BS date components into string.

        Args:
            year: BS year
            month: BS month (1-12)
            day: BS day (1-32)

        Returns:
            Formatted BS date string 'YYYY-MM-DD'
        """
        return f"{year:04d}-{month:02d}-{day:02d}"

    @staticmethod
    def get_bs_date_range(start_bs: str, end_bs: str) -> list[str]:
        """
        Get list of BS dates between start and end dates (inclusive).

        Args:
            start_bs: Start BS date 'YYYY-MM-DD'
            end_bs: End BS date 'YYYY-MM-DD'

        Returns:
            List of BS date strings
        """
        start_ad = NepalCalendar.bs_to_ad(start_bs)
        end_ad = NepalCalendar.bs_to_ad(end_bs)

        dates = []
        current_ad = start_ad

        while current_ad <= end_ad:
            bs_date = NepalCalendar.ad_to_bs(current_ad)
            dates.append(bs_date)
            current_ad = date.fromordinal(current_ad.toordinal() + 1)

        return dates


# Convenience functions
def bs_to_ad(bs_date_str: str) -> date:
    """Convert BS to AD date"""
    return NepalCalendar.bs_to_ad(bs_date_str)


def ad_to_bs(ad_date: date | datetime) -> str:
    """Convert AD to BS date string"""
    return NepalCalendar.ad_to_bs(ad_date)


def current_bs_date() -> str:
    """Get current BS date"""
    return NepalCalendar.current_bs_date()


def validate_bs_date(bs_date_str: str) -> bool:
    """Validate BS date"""
    return NepalCalendar.validate_bs_date(bs_date_str)


def current_academic_year() -> str:
    """Get current academic year in BS"""
    return NepalCalendar.get_current_academic_year_bs()
