"""
Nepal School Management System - Library Schemas
"""

from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class BookCreate(BaseModel):
    isbn: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=300)
    author: str = Field(..., min_length=1)
    publisher: Optional[str] = None
    edition: Optional[str] = None
    category: str = Field(default="textbook")
    total_copies: int = Field(default=1, ge=1)
    shelf_location: Optional[str] = None


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    edition: Optional[str] = None
    category: Optional[str] = None
    total_copies: Optional[int] = Field(None, ge=1)
    shelf_location: Optional[str] = None
    is_active: Optional[bool] = None


class BookResponse(BaseModel):
    id: UUID
    isbn: Optional[str] = None
    title: str
    author: str
    publisher: Optional[str] = None
    edition: Optional[str] = None
    category: str
    total_copies: int
    available_copies: int
    shelf_location: Optional[str] = None
    cover_image_url: Optional[str] = None
    added_date_ad: date
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    books: List[BookResponse]
    total: int
    page: int
    limit: int


class IssueBookRequest(BaseModel):
    book_id: UUID
    issued_to_id: UUID
    issued_to_type: str = Field(default="student")
    due_days: int = Field(default=14, ge=1, le=90)


class ReturnBookRequest(BaseModel):
    book_issue_id: UUID
    condition: str = Field(default="good")
    fine_amount: Decimal = Field(default=0, ge=0)


class BookIssueResponse(BaseModel):
    id: UUID
    book_id: UUID
    book_title: Optional[str] = None
    issued_to_id: UUID
    issued_to_type: str
    issue_date_ad: date
    due_date_ad: date
    return_date_ad: Optional[date] = None
    status: str
    fine_amount: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class IssuedBooksListResponse(BaseModel):
    issues: List[BookIssueResponse]
    total: int
    page: int
    limit: int


class LibraryStatsResponse(BaseModel):
    total_books: int
    total_copies: int
    total_issued: int
    overdue_count: int
    categories: dict
