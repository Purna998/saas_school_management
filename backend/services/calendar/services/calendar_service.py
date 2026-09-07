"""
Nepal School Management System - Calendar Service
BS/AD date conversion and academic year calculation using nepali_datetime
"""

import logging
from typing import Optional, List
from datetime import date, timedelta

from shared.utils.nepali_calendar import (
    NepalCalendar,
    bs_to_ad,
    ad_to_bs,
    current_bs_date,
    validate_bs_date,
    current_academic_year,
)

logger = logging.getLogger(__name__)

BS_MONTHS_NP = [
    "बैशाख", "जेठ", "असार", "श्रावण",
    "भाद्र", "आश्विन", "कार्तिक", "मंसिर",
    "पौष", "माघ", "फाल्गुन", "चैत्र"
]

BS_MONTHS_EN = [
    "Baisakh", "Jestha", "Ashadh", "Shrawan",
    "Bhadra", "Ashwin", "Kartik", "Mangsir",
    "Poush", "Magh", "Falgun", "Chaitra"
]

BS_DAYS_OF_WEEK_NP = ["आइतवार", "सोमवार", "मंगलवार", "बुधवार", "बिहिवार", "शुक्रवार", "शनिवार"]

NEPAL_HOLIDAYS = {
    2083: [
        {"name_en": "Prithvi Jayanti", "name_np": "पृथ्वी जयन्ती", "month": 9, "day": 27, "type": "national"},
        {"name_en": "Martyrs Day", "name_np": "शहीद दिवस", "month": 10, "day": 16, "type": "national"},
        {"name_en": "Maha Shivaratri", "name_np": "महाशिवरात्रि", "month": 11, "day": 17, "type": "religious"},
        {"name_en": "Fagu Purnima", "name_np": "फागु पूर्णिमा", "month": 11, "day": 27, "type": "religious"},
        {"name_en": "Women's Day", "name_np": "महिला दिवस", "month": 11, "day": 24, "type": "national"},
        {"name_en": "Nepali New Year", "name_np": "नयाँ वर्ष", "month": 1, "day": 1, "type": "national"},
        {"name_en": "Labour Day", "name_np": "श्रमिक दिवस", "month": 1, "day": 18, "type": "national"},
        {"name_en": "Republic Day", "name_np": "गणतन्त्र दिवस", "month": 2, "day": 15, "type": "national"},
        {"name_en": "Buddha Jayanti", "name_np": "बुद्ध जयन्ती", "month": 2, "day": 8, "type": "religious"},
        {"name_en": "Janai Purnima", "name_np": "जनै पूर्णिमा", "month": 4, "day": 27, "type": "religious"},
        {"name_en": "Gai Jatra", "name_np": "गाईजात्रा", "month": 4, "day": 28, "type": "religious"},
        {"name_en": "Krishna Janmashtami", "name_np": "कृष्ण जन्माष्टमी", "month": 5, "day": 5, "type": "religious"},
        {"name_en": "Teej", "name_np": "तीज", "month": 5, "day": 10, "type": "religious"},
        {"name_en": "Constitution Day", "name_np": "संविधान दिवस", "month": 5, "day": 17, "type": "national"},
        {"name_en": "Dashain (Ghatasthapana)", "name_np": "दशैं (घटस्थापना)", "month": 6, "day": 16, "type": "religious"},
        {"name_en": "Dashain (Vijaya Dashami)", "name_np": "विजया दशमी", "month": 6, "day": 25, "type": "religious"},
        {"name_en": "Tihar (Laxmi Puja)", "name_np": "तिहार (लक्ष्मी पूजा)", "month": 7, "day": 11, "type": "religious"},
        {"name_en": "Tihar (Bhai Tika)", "name_np": "भाइटिका", "month": 7, "day": 13, "type": "religious"},
        {"name_en": "Chhath Parva", "name_np": "छठ पर्व", "month": 7, "day": 17, "type": "religious"},
    ],
}


class CalendarService:
    """Calendar conversion and utility service"""

    def convert_bs_to_ad(self, year: int, month: int, day: int) -> dict:
        """Convert BS date to AD date"""
        bs_date_str = NepalCalendar.format_bs_date(year, month, day)
        ad_date = bs_to_ad(bs_date_str)
        weekday = ad_date.weekday()

        return {
            "bs_date": {
                "year": year,
                "month": month,
                "day": day,
                "month_name": BS_MONTHS_NP[month - 1] if 1 <= month <= 12 else None,
                "day_of_week": BS_DAYS_OF_WEEK_NP[(weekday + 1) % 7],
            },
            "ad_date": {
                "year": ad_date.year,
                "month": ad_date.month,
                "day": ad_date.day,
                "iso_date": ad_date.isoformat(),
            },
        }

    def convert_ad_to_bs(self, year: int, month: int, day: int) -> dict:
        """Convert AD date to BS date"""
        ad_date_obj = date(year, month, day)
        bs_date_str = ad_to_bs(ad_date_obj)
        bs_year, bs_month, bs_day = NepalCalendar.parse_bs_date(bs_date_str)
        weekday = ad_date_obj.weekday()

        return {
            "bs_date": {
                "year": bs_year,
                "month": bs_month,
                "day": bs_day,
                "month_name": BS_MONTHS_NP[bs_month - 1] if 1 <= bs_month <= 12 else None,
                "day_of_week": BS_DAYS_OF_WEEK_NP[(weekday + 1) % 7],
            },
            "ad_date": {
                "year": year,
                "month": month,
                "day": day,
                "iso_date": ad_date_obj.isoformat(),
            },
        }

    def get_current_bs_date(self) -> dict:
        """Get current BS date"""
        today = date.today()
        return self.convert_ad_to_bs(today.year, today.month, today.day)

    def get_current_academic_year(self) -> dict:
        """Get current academic year based on BS calendar"""
        current = self.get_current_bs_date()
        bs_year = current["bs_date"]["year"]

        # Academic year string (e.g., "2083-2084")
        academic_year_str = current_academic_year()

        # Start: 1st Baisakh
        start_bs_str = NepalCalendar.format_bs_date(bs_year, 1, 1)
        start_ad = bs_to_ad(start_bs_str)

        # End: Last day of Chaitra - use nepali_datetime to get days in month
        from nepali_datetime import date as nepali_date_cls
        try:
            # Try getting last day by testing day 30 then 29
            for last_day in range(32, 28, -1):
                try:
                    nepali_date_cls(bs_year, 12, last_day)
                    break
                except ValueError:
                    continue
            else:
                last_day = 30
        except Exception:
            last_day = 30

        end_bs_str = NepalCalendar.format_bs_date(bs_year, 12, last_day)
        end_ad = bs_to_ad(end_bs_str)

        today = date.today()
        is_current = start_ad <= today <= end_ad

        return {
            "academic_year_bs": str(bs_year),
            "start_date_bs": {
                "year": bs_year,
                "month": 1,
                "day": 1,
                "month_name": BS_MONTHS_NP[0],
            },
            "end_date_bs": {
                "year": bs_year,
                "month": 12,
                "day": last_day,
                "month_name": BS_MONTHS_NP[11],
            },
            "start_date_ad": {
                "year": start_ad.year,
                "month": start_ad.month,
                "day": start_ad.day,
                "iso_date": start_ad.isoformat(),
            },
            "end_date_ad": {
                "year": end_ad.year,
                "month": end_ad.month,
                "day": end_ad.day,
                "iso_date": end_ad.isoformat(),
            },
            "is_current": is_current,
        }

    def get_bs_months(self, year: int) -> dict:
        """Get all BS months for a year with days count"""
        from nepali_datetime import date as nepali_date_cls

        months = []
        for i in range(1, 13):
            # Determine days in this month
            for last_day in range(32, 28, -1):
                try:
                    nepali_date_cls(year, i, last_day)
                    break
                except (ValueError, Exception):
                    continue
            else:
                last_day = 30

            months.append({
                "month_number": i,
                "name_np": BS_MONTHS_NP[i - 1],
                "name_en": BS_MONTHS_EN[i - 1],
                "days_in_month": last_day,
            })

        return {"year": year, "months": months}

    def get_holidays(self, year_bs: int) -> dict:
        """Get holidays for a BS year"""
        holidays_data = NEPAL_HOLIDAYS.get(year_bs, [])
        holidays = []

        for h in holidays_data:
            try:
                bs_date_str = NepalCalendar.format_bs_date(year_bs, h["month"], h["day"])
                ad_date = bs_to_ad(bs_date_str)
                holidays.append({
                    "name_en": h["name_en"],
                    "name_np": h.get("name_np"),
                    "date_bs": {
                        "year": year_bs,
                        "month": h["month"],
                        "day": h["day"],
                        "month_name": BS_MONTHS_NP[h["month"] - 1],
                    },
                    "date_ad": {
                        "year": ad_date.year,
                        "month": ad_date.month,
                        "day": ad_date.day,
                        "iso_date": ad_date.isoformat(),
                    },
                    "holiday_type": h["type"],
                    "is_school_holiday": True,
                })
            except Exception:
                continue

        return {
            "year_bs": year_bs,
            "holidays": holidays,
            "total": len(holidays),
        }
