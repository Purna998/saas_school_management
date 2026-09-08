"""
Nepal School Management System - Library API Routes
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError
from services.auth.dependencies.auth import get_current_active_user, require_permission
from services.auth.models.user import User
from services.library.schemas.library import *
from services.library.services.library_service import LibraryService

router = APIRouter()


@router.post("/books", response_model=BookResponse, status_code=201)
async def create_book(
    data: BookCreate,
    current_user: User = Depends(require_permission("library:create")),
    db: AsyncSession = Depends(get_db)
):
    service = LibraryService(db)
    book = await service.create_book(current_user.school_id, data.model_dump())
    return BookResponse.model_validate(book)


@router.get("/books", response_model=BookListResponse)
async def list_books(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = None, category: Optional[str] = None,
    current_user: User = Depends(require_permission("library:read")),
    db: AsyncSession = Depends(get_db)
):
    service = LibraryService(db)
    books, total = await service.list_books(current_user.school_id, page, limit, search, category)
    return BookListResponse(
        books=[BookResponse.model_validate(b) for b in books],
        total=total, page=page, limit=limit
    )


@router.get("/books/{book_id}", response_model=BookResponse)
async def get_book(
    book_id: uuid.UUID,
    current_user: User = Depends(require_permission("library:read")),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = LibraryService(db)
        book = await service.get_book(book_id, current_user.school_id)
        return BookResponse.model_validate(book)
    except RecordNotFoundError as e:
        raise HTTPException(status_code=404, detail=error_response(str(e), "NOT_FOUND"))


@router.patch("/books/{book_id}", response_model=BookResponse)
async def update_book(
    book_id: uuid.UUID, data: BookUpdate,
    current_user: User = Depends(require_permission("library:update")),
    db: AsyncSession = Depends(get_db)
):
    service = LibraryService(db)
    book = await service.update_book(book_id, data.model_dump(exclude_unset=True), current_user.school_id)
    return BookResponse.model_validate(book)


@router.post("/issue")
async def issue_book(
    data: IssueBookRequest,
    current_user: User = Depends(require_permission("library:issue")),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = LibraryService(db)
        issue = await service.issue_book(
            current_user.school_id, data.book_id, data.issued_to_id,
            data.issued_to_type, data.due_days, current_user.id
        )
        return success_response(data={"issue_id": str(issue.id), "due_date": issue.due_date_ad.isoformat()})
    except ValueError as e:
        raise HTTPException(status_code=400, detail=error_response(str(e), "BOOK_UNAVAILABLE"))


@router.post("/return")
async def return_book(
    data: ReturnBookRequest,
    current_user: User = Depends(require_permission("library:return")),
    db: AsyncSession = Depends(get_db)
):
    try:
        service = LibraryService(db)
        issue = await service.return_book(data.book_issue_id, current_user.id, current_user.school_id, float(data.fine_amount))
        return success_response(data={"message": "Book returned", "fine_amount": float(issue.fine_amount)})
    except RecordNotFoundError as e:
        raise HTTPException(status_code=404, detail=error_response(str(e), "NOT_FOUND"))


@router.get("/issued", response_model=IssuedBooksListResponse)
async def list_issued_books(
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    student_id: Optional[uuid.UUID] = None, issue_status: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(require_permission("library:read")),
    db: AsyncSession = Depends(get_db)
):
    service = LibraryService(db)
    issues, total = await service.get_issued_books(current_user.school_id, page, limit, student_id, issue_status)
    return IssuedBooksListResponse(
        issues=[BookIssueResponse(
            id=i.id, book_id=i.book_id, book_title=None, issued_to_id=i.issued_to_id,
            issued_to_type=i.issued_to_type.value, issue_date_ad=i.issue_date_ad,
            due_date_ad=i.due_date_ad, return_date_ad=i.return_date_ad,
            status=i.status.value, fine_amount=i.fine_amount, created_at=i.created_at,
        ) for i in issues],
        total=total, page=page, limit=limit
    )


@router.get("/overdue")
async def get_overdue_books(
    current_user: User = Depends(require_permission("library:read")),
    db: AsyncSession = Depends(get_db)
):
    service = LibraryService(db)
    issues = await service.get_overdue_books(current_user.school_id)
    return success_response(data={"overdue_count": len(issues), "issues": [
        {"id": str(i.id), "book_id": str(i.book_id), "issued_to_id": str(i.issued_to_id),
         "due_date": i.due_date_ad.isoformat()} for i in issues
    ]})


@router.get("/stats", response_model=LibraryStatsResponse)
async def get_stats(
    current_user: User = Depends(require_permission("library:read")),
    db: AsyncSession = Depends(get_db)
):
    service = LibraryService(db)
    stats = await service.get_library_stats(current_user.school_id)
    return LibraryStatsResponse(**stats)
