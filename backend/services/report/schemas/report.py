"""Nepal School Management System - Report Schemas"""
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class ReportGenerateRequest(BaseModel):
    report_type: str
    academic_year_bs: Optional[str] = None
    grade: Optional[int] = Field(None, ge=1, le=12)
    section: Optional[str] = None
    file_format: str = "csv"
    filters: Dict = Field(default_factory=dict)


class ReportResponse(BaseModel):
    id: UUID
    report_type: str
    title: str
    academic_year_bs: Optional[str] = None
    grade: Optional[int] = None
    file_url: Optional[str] = None
    file_format: str
    status: str
    generated_at: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    reports: List[ReportResponse]
    total: int
    page: int
    limit: int
