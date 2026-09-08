"""
Nepal School Management System - Library Service
Book catalog and issue/return management
"""

import uuid
import logging
from typing import Optional, List, Tuple
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from shared.utils.exceptions import RecordNotFoundError
from services.library.models.library import Book, BookIssue, BookCategory, IssueStatus, IssuedToType

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_book(self, school_id: uuid.UUID, data: dict) -> Book:
        book = Book(
            id=uuid.uuid4(),
            school_id=school_id,
            isbn=data.get("isbn"),
            title=data["title"],
            author=data["author"],
            publisher=data.get("publisher"),
            edition=data.get("edition"),
            category=BookCategory(data.get("category", "textbook")),
            total_copies=data.get("total_copies", 1),
            available_copies=data.get("total_copies", 1),
            shelf_location=data.get("shelf_location"),
            is_active=True,
        )
        self.db.add(book)
        await self.db.commit()
        await self.db.refresh(book)
        return book

    async def get_book(self, book_id: uuid.UUID, school_id: uuid.UUID) -> Book:
        result = await self.db.execute(select(Book).where(Book.id == book_id, Book.school_id == school_id))
        book = result.scalar_one_or_none()
        if not book:
            raise RecordNotFoundError("Book", str(book_id))
        return book

    async def update_book(self, book_id: uuid.UUID, data: dict, school_id: uuid.UUID) -> Book:
        book = await self.get_book(book_id, school_id)
        for key, value in data.items():
            if value is not None and hasattr(book, key):
                if key == "category":
                    setattr(book, key, BookCategory(value))
                elif key == "total_copies":
                    diff = value - book.total_copies
                    book.total_copies = value
                    book.available_copies = max(0, book.available_copies + diff)
                else:
                    setattr(book, key, value)
        await self.db.commit()
        await self.db.refresh(book)
        return book

    async def list_books(
        self, school_id: uuid.UUID, page: int = 1, limit: int = 20,
        search: Optional[str] = None, category: Optional[str] = None
    ) -> Tuple[List[Book], int]:
        query = select(Book).where(Book.school_id == school_id, Book.is_active == True)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                (Book.title.ilike(pattern)) | (Book.author.ilike(pattern)) | (Book.isbn.ilike(pattern))
            )
        if category:
            query = query.where(Book.category == BookCategory(category))

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar()

        query = query.offset((page - 1) * limit).limit(limit).order_by(Book.title)
        books = (await self.db.execute(query)).scalars().all()
        return books, total

    async def issue_book(
        self, school_id: uuid.UUID, book_id: uuid.UUID, issued_to_id: uuid.UUID,
        issued_to_type: str, due_days: int, issued_by: uuid.UUID
    ) -> BookIssue:
        book = await self.get_book(book_id, school_id)
        if book.available_copies <= 0:
            raise ValueError("No copies available for issue")

        issue = BookIssue(
            id=uuid.uuid4(),
            school_id=school_id,
            book_id=book_id,
            issued_to_id=issued_to_id,
            issued_to_type=IssuedToType(issued_to_type),
            issue_date_ad=date.today(),
            due_date_ad=date.today() + timedelta(days=due_days),
            status=IssueStatus.ISSUED,
            issued_by=issued_by,
        )
        book.available_copies -= 1
        self.db.add(issue)
        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def return_book(
        self, book_issue_id: uuid.UUID, returned_to: uuid.UUID, school_id: uuid.UUID, fine_amount: float = 0
    ) -> BookIssue:
        result = await self.db.execute(select(BookIssue).where(BookIssue.id == book_issue_id, BookIssue.school_id == school_id))
        issue = result.scalar_one_or_none()
        if not issue:
            raise RecordNotFoundError("BookIssue", str(book_issue_id))

        issue.return_date_ad = date.today()
        issue.status = IssueStatus.RETURNED
        issue.returned_to = returned_to
        issue.fine_amount = fine_amount

        book = await self.get_book(issue.book_id, school_id)
        book.available_copies += 1

        await self.db.commit()
        await self.db.refresh(issue)
        return issue

    async def get_issued_books(
        self, school_id: uuid.UUID, page: int = 1, limit: int = 20,
        student_id: Optional[uuid.UUID] = None, status_filter: Optional[str] = None
    ) -> Tuple[List[BookIssue], int]:
        query = select(BookIssue).where(BookIssue.school_id == school_id)
        if student_id:
            query = query.where(BookIssue.issued_to_id == student_id)
        if status_filter:
            query = query.where(BookIssue.status == IssueStatus(status_filter))

        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar()

        query = query.offset((page - 1) * limit).limit(limit).order_by(BookIssue.issue_date_ad.desc())
        issues = (await self.db.execute(query)).scalars().all()
        return issues, total

    async def get_overdue_books(self, school_id: uuid.UUID) -> List[BookIssue]:
        result = await self.db.execute(
            select(BookIssue).where(
                BookIssue.school_id == school_id,
                BookIssue.status == IssueStatus.ISSUED,
                BookIssue.due_date_ad < date.today()
            ).order_by(BookIssue.due_date_ad)
        )
        return result.scalars().all()

    async def get_library_stats(self, school_id: uuid.UUID) -> dict:
        books_q = select(func.count(), func.sum(Book.total_copies)).where(
            Book.school_id == school_id, Book.is_active == True
        )
        books_result = await self.db.execute(books_q)
        row = books_result.one()
        total_books = row[0] or 0
        total_copies = row[1] or 0

        issue_counts = (
            await self.db.execute(
                select(
                    func.count(BookIssue.id).label("issued"),
                    func.count(BookIssue.id).filter(
                        BookIssue.due_date_ad < date.today()
                    ).label("overdue"),
                ).where(
                    BookIssue.school_id == school_id,
                    BookIssue.status == IssueStatus.ISSUED,
                )
            )
        ).one()
        total_issued = issue_counts.issued or 0
        overdue_count = issue_counts.overdue or 0

        cat_q = select(Book.category, func.count()).where(
            Book.school_id == school_id, Book.is_active == True
        ).group_by(Book.category)
        cat_result = await self.db.execute(cat_q)
        categories = {row[0].value: row[1] for row in cat_result.all()}

        return {
            "total_books": total_books,
            "total_copies": total_copies,
            "total_issued": total_issued,
            "overdue_count": overdue_count,
            "categories": categories,
        }
