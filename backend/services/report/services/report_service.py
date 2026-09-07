"""Nepal School Management System - Report Service"""
import uuid
import os
import csv
import io
import logging
from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from shared.utils.exceptions import RecordNotFoundError
from services.report.models.report import Report, ReportType, ReportFormat, ReportStatus

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_report(self, school_id: uuid.UUID, data: dict, generated_by: uuid.UUID) -> Report:
        report_type = ReportType(data["report_type"])
        title = f"{report_type.value.replace('_', ' ').title()} Report"
        if data.get("grade"):
            title += f" - Grade {data['grade']}"

        report = Report(
            id=uuid.uuid4(), school_id=school_id, report_type=report_type,
            title=title, academic_year_bs=data.get("academic_year_bs"),
            grade=data.get("grade"), section=data.get("section"),
            generated_by=generated_by, file_format=ReportFormat(data.get("file_format", "csv")),
            status=ReportStatus.GENERATING, parameters=data.get("filters", {}),
        )
        self.db.add(report)
        await self.db.flush()

        try:
            content = self._generate_csv_content(report_type, data)
            file_path = self._save_report_file(report.id, content, report.file_format.value)
            report.file_url = file_path
            report.status = ReportStatus.READY
            report.generated_at = datetime.utcnow()
        except Exception as e:
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            logger.error(f"Report generation failed: {e}")

        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_report(self, report_id: uuid.UUID) -> Report:
        result = await self.db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()
        if not report:
            raise RecordNotFoundError("Report", str(report_id))
        return report

    async def list_reports(self, school_id: uuid.UUID, page: int = 1, limit: int = 20) -> Tuple[List[Report], int]:
        query = select(Report).where(Report.school_id == school_id)
        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar()
        query = query.offset((page - 1) * limit).limit(limit).order_by(Report.created_at.desc())
        reports = (await self.db.execute(query)).scalars().all()
        return reports, total

    async def delete_report(self, report_id: uuid.UUID):
        report = await self.get_report(report_id)
        if report.file_url and os.path.exists(report.file_url):
            os.remove(report.file_url)
        await self.db.delete(report)
        await self.db.commit()

    def _generate_csv_content(self, report_type: ReportType, params: dict) -> str:
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == ReportType.STUDENT_LIST:
            writer.writerow(["Name", "Grade", "Section", "Gender", "Status", "Guardian Phone"])
            writer.writerow(["Sample Student", params.get("grade", ""), params.get("section", ""), "male", "active", "+977-9841234567"])
        elif report_type == ReportType.ATTENDANCE_MONTHLY:
            writer.writerow(["Student Name", "Total Days", "Present", "Absent", "Late", "Attendance %"])
            writer.writerow(["Sample Student", "22", "20", "1", "1", "90.9%"])
        elif report_type == ReportType.FEE_COLLECTION:
            writer.writerow(["Student Name", "Total Due", "Total Paid", "Balance", "Status"])
            writer.writerow(["Sample Student", "5000", "5000", "0", "paid"])
        elif report_type == ReportType.EXAM_RESULT:
            writer.writerow(["Student Name", "Total Marks", "Percentage/GPA", "Rank", "Status"])
            writer.writerow(["Sample Student", "450", "90%/3.6", "1", "pass"])
        else:
            writer.writerow(["Report Type", "Status"])
            writer.writerow([report_type.value, "Generated"])

        return output.getvalue()

    def _save_report_file(self, report_id: uuid.UUID, content: str, fmt: str) -> str:
        report_dir = os.path.join("uploads", "reports")
        os.makedirs(report_dir, exist_ok=True)
        filename = f"{report_id}.{fmt}"
        filepath = os.path.join(report_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath
