"""School-scoped catalog, circulation, policy, history and report routes."""

from datetime import date
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from services.auth.dependencies.auth import require_permission
from services.library.models.library import BookCategory, CopyStatus, IssuedToType
from services.library.schemas.library import AddCopiesRequest, BookCreate, BookResponse, BookUpdate, CopyUpdateRequest, IssueBookRequest, LendingPolicyUpdate, LostBookRequest, RenewBookRequest, ReturnBookRequest
from services.library.services.library_service import LibraryConflict, LibraryService, today
from shared.database.base import get_db
from shared.schemas.responses import error_response, success_response
from shared.utils.exceptions import RecordNotFoundError

router = APIRouter()


def access(permission, private=False):
    async def check(user=Depends(require_permission(permission))):
        if not user.school_id:
            raise HTTPException(403, detail=error_response("A school context is required", "SCHOOL_REQUIRED"))
        if private and (user.has_role("parent") or user.has_role("student")) and not any(
            user.has_permission(code) for code in ("library:create", "library:update", "library:issue", "library:return")
        ):
            raise HTTPException(403, detail=error_response("Borrower records require an authorized library staff account", "LIBRARY_STAFF_REQUIRED"))
        return user
    return check


async def run(operation):
    try:
        return await operation
    except RecordNotFoundError as exc:
        raise HTTPException(404, detail=error_response(str(exc), "LIBRARY_NOT_FOUND")) from exc
    except LibraryConflict as exc:
        raise HTTPException(409, detail=error_response(str(exc), "LIBRARY_CONFLICT")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=error_response(str(exc), "INVALID_LIBRARY_REQUEST")) from exc
    except IntegrityError as exc:
        raise HTTPException(409, detail=error_response("This ISBN, accession, or circulation request conflicts with an existing record. Refresh and review the selection.", "LIBRARY_CONFLICT")) from exc


def result(data):
    return success_response(data=data)


def actor(user):
    return {"actor_id": user.id, "actor_name": user.full_name_en}


@router.get("/books")
async def books(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), search: Optional[str] = Query(None, max_length=300),
    category: Optional[BookCategory] = None, is_active: Optional[bool] = True, available_only: bool = False,
    user=Depends(access("library:read")), db: AsyncSession = Depends(get_db)):
    return result(await run(LibraryService(db).list_books(user.school_id, page, limit, search=search, category=category, is_active=is_active, available_only=available_only)))


@router.post("/books", status_code=201)
async def create_book(data: BookCreate, user=Depends(access("library:create", True)), db: AsyncSession = Depends(get_db)):
    book = await run(LibraryService(db).create_book(user.school_id, data, **actor(user)))
    return result(BookResponse.model_validate(book).model_dump(mode="json"))


@router.get("/books/{book_id}")
async def book_details(book_id: UUID, user=Depends(access("library:read")), db: AsyncSession = Depends(get_db)):
    book = await run(LibraryService(db)._book(user.school_id, book_id))
    return result(BookResponse.model_validate(book).model_dump(mode="json"))


@router.patch("/books/{book_id}")
async def update_book(book_id: UUID, data: BookUpdate, user=Depends(access("library:update", True)), db: AsyncSession = Depends(get_db)):
    book = await run(LibraryService(db).update_book(user.school_id, book_id, data, **actor(user)))
    return result(BookResponse.model_validate(book).model_dump(mode="json"))


@router.get("/books/{book_id}/copies")
async def copies(book_id: UUID, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    status: Optional[CopyStatus] = None, search: Optional[str] = Query(None, max_length=50),
    user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    return result(await run(LibraryService(db).list_copies(user.school_id, book_id, page, limit, status, search)))


@router.post("/books/{book_id}/copies", status_code=201)
async def add_copies(book_id: UUID, data: AddCopiesRequest, user=Depends(access("library:update", True)), db: AsyncSession = Depends(get_db)):
    book = await run(LibraryService(db).add_copies(user.school_id, book_id, data, **actor(user)))
    return result(BookResponse.model_validate(book).model_dump(mode="json"))


@router.patch("/copies/{copy_id}")
async def change_copy(copy_id: UUID, data: CopyUpdateRequest, user=Depends(access("library:update", True)), db: AsyncSession = Depends(get_db)):
    service = LibraryService(db)
    copy = await run(service.update_copy(user.school_id, copy_id, data, **actor(user)))
    return result(service.copy_response(copy))


@router.get("/borrowers")
async def borrowers(borrower_type: IssuedToType = IssuedToType.STUDENT, search: Optional[str] = Query(None, max_length=200),
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    return result(await run(LibraryService(db).borrowers(user.school_id, borrower_type, search, page, limit)))


@router.post("/issue", status_code=201)
async def issue(data: IssueBookRequest, user=Depends(access("library:issue", True)), db: AsyncSession = Depends(get_db)):
    service = LibraryService(db)
    loan = await run(service.issue_book(user.school_id, data, **actor(user)))
    return result(service.loan_response(loan))


@router.post("/return")
async def return_book(data: ReturnBookRequest, user=Depends(access("library:return", True)), db: AsyncSession = Depends(get_db)):
    service = LibraryService(db)
    return result(service.loan_response(await run(service.return_book(user.school_id, data, **actor(user)))))


@router.post("/issued/{issue_id}/renew")
async def renew(issue_id: UUID, data: RenewBookRequest, user=Depends(access("library:issue", True)), db: AsyncSession = Depends(get_db)):
    service = LibraryService(db)
    return result(service.loan_response(await run(service.renew_book(user.school_id, issue_id, data, **actor(user)))))


@router.post("/issued/{issue_id}/lost")
async def lost(issue_id: UUID, data: LostBookRequest, user=Depends(access("library:return", True)), db: AsyncSession = Depends(get_db)):
    service = LibraryService(db)
    return result(service.loan_response(await run(service.mark_lost(user.school_id, issue_id, data, **actor(user)))))


@router.get("/issued")
async def loans(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    status: Optional[Literal["active", "issued", "overdue", "returned", "lost"]] = None,
    borrower_type: Optional[IssuedToType] = None, borrower_id: Optional[UUID] = None, student_id: Optional[UUID] = None,
    book_id: Optional[UUID] = None, search: Optional[str] = Query(None, max_length=300), start_date: Optional[date] = None, end_date: Optional[date] = None,
    user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    if student_id:
        borrower_id, borrower_type = student_id, IssuedToType.STUDENT
    return result(await run(LibraryService(db).list_loans(user.school_id, page, limit, status=status,
        borrower_type=borrower_type, borrower_id=borrower_id, book_id=book_id, search=search, start_date=start_date, end_date=end_date)))


@router.get("/issued/{issue_id}")
async def loan_details(issue_id: UUID, user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    service = LibraryService(db)
    return result(service.loan_response(await run(service._loan(user.school_id, issue_id))))


@router.get("/overdue")
async def overdue(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    return result(await run(LibraryService(db).list_loans(user.school_id, page, limit, status="overdue")))


@router.get("/stats")
async def stats(user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    return result(await run(LibraryService(db).get_library_stats(user.school_id)))


@router.get("/policy")
async def policy(user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    service = LibraryService(db)
    return result(service.policy_response(await run(service.policy(user.school_id))))


@router.put("/policy")
async def update_policy(data: LendingPolicyUpdate, user=Depends(access("library:update", True)), db: AsyncSession = Depends(get_db)):
    return result(await run(LibraryService(db).update_policy(user.school_id, data, **actor(user))))


@router.get("/history")
async def history(book_id: Optional[UUID] = None, issue_id: Optional[UUID] = None, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    return result(await run(LibraryService(db).history(user.school_id, book_id, issue_id, page, limit)))


@router.get("/export")
async def export(report: Literal["catalog", "loans"], search: Optional[str] = Query(None, max_length=300),
    category: Optional[BookCategory] = None, is_active: Optional[bool] = True, available_only: bool = False,
    status: Optional[Literal["active", "issued", "overdue", "returned", "lost"]] = None,
    borrower_type: Optional[IssuedToType] = None, book_id: Optional[UUID] = None, start_date: Optional[date] = None, end_date: Optional[date] = None,
    user=Depends(access("library:read", True)), db: AsyncSession = Depends(get_db)):
    filters = {"search": search, "category": category, "is_active": is_active, "available_only": available_only} if report == "catalog" else {
        "search": search, "status": status, "borrower_type": borrower_type, "book_id": book_id, "start_date": start_date, "end_date": end_date}
    content = await run(LibraryService(db).export_report(user.school_id, report, **filters))
    return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="library-{report}-{today().isoformat()}.csv"'})
