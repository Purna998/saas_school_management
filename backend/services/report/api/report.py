"""Nepal School Management System - Report API Routes"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError
from services.auth.dependencies.auth import require_permission
from services.auth.models.user import User
from services.report.schemas.report import *
from services.report.services.report_service import ReportService

router = APIRouter()


@router.post("/generate", response_model=ReportResponse, status_code=201)
async def generate_report(data: ReportGenerateRequest, user: User = Depends(require_permission("report:generate")), db: AsyncSession = Depends(get_db)):
    s = ReportService(db)
    report = await s.generate_report(user.school_id, data.model_dump(), user.id)
    return ReportResponse.model_validate(report)


@router.get("/", response_model=ReportListResponse)
async def list_reports(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user: User = Depends(require_permission("report:read")), db: AsyncSession = Depends(get_db)):
    s = ReportService(db)
    reports, total = await s.list_reports(user.school_id, page, limit)
    return ReportListResponse(reports=[ReportResponse.model_validate(r) for r in reports], total=total, page=page, limit=limit)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: uuid.UUID, user: User = Depends(require_permission("report:read")), db: AsyncSession = Depends(get_db)):
    s = ReportService(db)
    return ReportResponse.model_validate(await s.get_report(report_id))


@router.get("/{report_id}/download")
async def download_report(report_id: uuid.UUID, user: User = Depends(require_permission("report:read")), db: AsyncSession = Depends(get_db)):
    s = ReportService(db)
    report = await s.get_report(report_id)
    if not report.file_url:
        raise HTTPException(status_code=404, detail=error_response("Report file not found", "FILE_NOT_FOUND"))
    import os
    if not os.path.exists(report.file_url):
        raise HTTPException(status_code=404, detail=error_response("Report file missing", "FILE_NOT_FOUND"))
    return FileResponse(report.file_url, filename=f"{report.title}.{report.file_format.value}", media_type="application/octet-stream")


@router.delete("/{report_id}")
async def delete_report(report_id: uuid.UUID, user: User = Depends(require_permission("report:delete")), db: AsyncSession = Depends(get_db)):
    s = ReportService(db)
    await s.delete_report(report_id)
    return success_response(data={"message": "Report deleted"})
