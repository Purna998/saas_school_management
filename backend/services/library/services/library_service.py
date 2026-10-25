"""Accession-level library inventory and transaction-safe circulation."""

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from services.library.models.library import Book, BookCopy, BookIssue, CopyStatus, IssuedToType, IssueStatus, LibraryEvent, LibraryPolicy
from services.library.schemas.library import AddCopiesRequest, BookCreate, BookResponse, BookUpdate, CopyUpdateRequest, IssueBookRequest, LendingPolicyUpdate, LostBookRequest, RenewBookRequest, ReturnBookRequest
from services.staff.models.staff import Staff, StaffStatus
from services.student.models.student import Student, StudentStatus
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NPT, NepalCalendar

OPEN = (IssueStatus.ISSUED, IssueStatus.OVERDUE)
ZERO = Decimal("0.00")
POLICY_FIELDS = ("loan_days", "student_limit", "staff_limit", "renewal_days", "max_renewals", "allow_overdue_renewal", "daily_fine", "fine_cap")


def today():
    return datetime.now(NPT).date()


def effective_status(loan):
    if loan.status in OPEN:
        return "overdue" if loan.due_date_ad < today() else "issued"
    return loan.status.value


def estimated_fine(loan):
    if loan.status not in OPEN:
        return loan.fine_amount
    rate = Decimal(str(loan.policy_snapshot.get("daily_fine", "0")))
    cap = Decimal(str(loan.policy_snapshot.get("fine_cap", "0")))
    days = max(0, (today() - loan.due_date_ad).days)
    remaining = max(ZERO, cap - loan.fine_amount)
    return (loan.fine_amount + min(rate * days, remaining)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LibraryConflict(ValueError):
    pass


class LibraryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _lock(self, value):
        await self.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {"key": f"library:{value}"})

    async def _begin(self, school_id, data, action):
        await self._lock(f"{school_id}:request:{data.request_id}")
        payload = data.model_dump(mode="json", exclude_unset=isinstance(data, BookUpdate), exclude={"request_id"})
        previous = await self.db.scalar(select(LibraryEvent).where(LibraryEvent.school_id == school_id, LibraryEvent.request_id == data.request_id))
        if previous and (previous.action != action or previous.payload != payload):
            raise LibraryConflict("This request ID was already used for different library details")
        return previous, payload

    async def _event(self, school_id, data, action, payload, actor_id, actor_name=None, *, book_id=None, copy_id=None, issue_id=None, before=None, after=None, notes=None):
        self.db.add(LibraryEvent(
            school_id=school_id, request_id=data.request_id, action=action, payload=payload,
            actor_id=actor_id, actor_name=actor_name, book_id=book_id, copy_id=copy_id, issue_id=issue_id,
            before_values=before or {}, after_values=after or {}, notes=notes,
        ))
        await self.db.flush()

    async def _book(self, school_id, book_id, lock=False):
        query = select(Book).where(Book.school_id == school_id, Book.id == book_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        book = await self.db.scalar(query)
        if book is None:
            raise RecordNotFoundError("Book", str(book_id))
        return book

    async def _copy(self, school_id, copy_id, lock=False):
        query = select(BookCopy).where(BookCopy.school_id == school_id, BookCopy.id == copy_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        copy = await self.db.scalar(query)
        if copy is None:
            raise RecordNotFoundError("BookCopy", str(copy_id))
        return copy

    async def _borrower(self, school_id, borrower_id, kind, lock=False):
        model = Student if kind == IssuedToType.STUDENT else Staff
        query = select(model).where(model.id == borrower_id, model.school_id == school_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        borrower = await self.db.scalar(query)
        if borrower is None:
            raise RecordNotFoundError("Borrower", str(borrower_id))
        active = borrower.status == StudentStatus.ACTIVE if kind == IssuedToType.STUDENT else borrower.status in (StaffStatus.ACTIVE, StaffStatus.ON_LEAVE)
        if not active or borrower.is_deleted or borrower.deleted_at is not None:
            raise LibraryConflict("Only currently enrolled students or employed staff can borrow new books")
        return borrower

    async def issue_book(self, school_id, data: IssueBookRequest, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "issued")
        if previous:
            return await self._loan(school_id, previous.issue_id)
        policy = await self.policy(school_id)
        await self._lock(f"{school_id}:borrower:{data.issued_to_type.value}:{data.issued_to_id}")
        borrower = await self._borrower(school_id, data.issued_to_id, data.issued_to_type, lock=True)
        book = await self._book(school_id, data.book_id, lock=True)
        if not book.is_active or not book.is_lendable:
            raise LibraryConflict("Archived and reference-only titles cannot be issued")
        active = (await self.db.scalars(select(BookIssue).where(BookIssue.school_id == school_id,
            BookIssue.issued_to_id == data.issued_to_id, BookIssue.issued_to_type == data.issued_to_type,
            BookIssue.status.in_(OPEN)))).all()
        limit = policy.student_limit if data.issued_to_type == IssuedToType.STUDENT else policy.staff_limit
        if len(active) >= limit:
            raise LibraryConflict(f"The borrower already has the maximum of {limit} active loans")
        if any(loan.book_id == book.id for loan in active):
            raise LibraryConflict("This borrower already has an active copy of this title")
        query = select(BookCopy).where(BookCopy.school_id == school_id, BookCopy.book_id == book.id, BookCopy.status == "available")
        if data.copy_id:
            query = query.where(BookCopy.id == data.copy_id)
        copy = (await self.db.scalars(query.order_by(BookCopy.accession_number).limit(1)
            .with_for_update().execution_options(populate_existing=True))).first()
        if copy is None:
            raise LibraryConflict("No available copy matches this selection")
        reference = (borrower.admission_number or borrower.emis_student_id or f"Grade {borrower.current_grade or '—'} {borrower.current_section or ''}, roll {borrower.roll_number or '—'}") if data.issued_to_type == IssuedToType.STUDENT else borrower.employee_id
        loan = BookIssue(id=uuid4(), school_id=school_id, book_id=book.id, copy_id=copy.id,
            book_title=book.title, accession_number=copy.accession_number, borrower_name=borrower.full_name_en,
            borrower_reference=reference, issued_to_id=borrower.id, issued_to_type=data.issued_to_type,
            issue_date_ad=today(), due_date_ad=today() + timedelta(days=data.due_days or policy.loan_days),
            status=IssueStatus.ISSUED, fine_amount=ZERO, renewal_count=0,
            policy_snapshot=self.policy_response(policy), issued_by=actor_id, notes=data.notes)
        copy.status = "issued"
        self.db.add(loan)
        await self.db.flush()
        await self._sync_stock(book)
        await self._event(school_id, data, "issued", payload, actor_id, actor_name, book_id=book.id,
            copy_id=copy.id, issue_id=loan.id, after={"accession_number": copy.accession_number,
            "borrower_name": loan.borrower_name, "due_date_ad": loan.due_date_ad.isoformat()}, notes=data.notes)
        return loan

    async def _lock_circulation(self, school_id, issue_id):
        loan = await self._loan(school_id, issue_id)
        await self._lock(f"{school_id}:borrower:{loan.issued_to_type.value}:{loan.issued_to_id}")
        book = await self._book(school_id, loan.book_id, lock=True)
        loan = await self._loan(school_id, issue_id, lock=True)
        copy = await self._copy(school_id, loan.copy_id, lock=True) if loan.copy_id else None
        if copy is not None and copy.book_id != book.id:
            raise LibraryConflict("The copy no longer matches the original loan")
        return loan, book, copy

    async def return_book(self, school_id, data: ReturnBookRequest, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "returned")
        if previous:
            return await self._loan(school_id, previous.issue_id)
        loan, book, copy = await self._lock_circulation(school_id, data.book_issue_id)
        if loan.status not in (*OPEN, IssueStatus.LOST):
            raise LibraryConflict("This loan was already returned; stock was not changed")
        if copy is None or copy.status not in ("issued", "lost", "withdrawn"):
            raise LibraryConflict("Reconcile this loan's copy state before returning it")
        suggested = estimated_fine(loan)
        fine = data.fine_amount if data.fine_amount is not None else suggested
        if (fine > 0 or fine != suggested) and (not data.notes or len(data.notes) < 3):
            raise ValueError("Add a reason for the fine assessment or waiver")
        before = {"status": effective_status(loan), "fine_amount": str(loan.fine_amount), "copy_status": copy.status}
        loan.status, loan.return_date_ad = IssueStatus.RETURNED, today()
        loan.returned_to, loan.fine_amount, loan.return_condition = actor_id, fine, data.condition
        loan.notes = data.notes
        copy.status = "available" if data.condition == "good" else "damaged"
        await self.db.flush()
        await self._sync_stock(book)
        await self._event(school_id, data, "returned", payload, actor_id, actor_name, book_id=book.id,
            copy_id=copy.id, issue_id=loan.id, before=before,
            after={"status": "returned", "fine_amount": str(fine), "copy_status": copy.status}, notes=data.notes)
        return loan

    async def renew_book(self, school_id, issue_id, data: RenewBookRequest, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "renewed")
        if previous and previous.issue_id != issue_id:
            raise LibraryConflict("This request ID belongs to a different loan")
        if previous:
            return await self._loan(school_id, issue_id)
        loan, book, copy = await self._lock_circulation(school_id, issue_id)
        if loan.status not in OPEN or copy is None or copy.status != "issued":
            raise LibraryConflict("Only active loans can be renewed")
        # A withdrawn borrower can return a book, but cannot extend a loan.
        await self._borrower(school_id, loan.issued_to_id, loan.issued_to_type, lock=True)
        if not book.is_active or not book.is_lendable:
            raise LibraryConflict("This title is no longer available for lending")
        if loan.renewal_count >= loan.policy_snapshot.get("max_renewals", 2):
            raise LibraryConflict("This loan has reached its renewal limit")
        if loan.due_date_ad < today() and not loan.policy_snapshot.get("allow_overdue_renewal", False):
            raise LibraryConflict("The loan is overdue; its lending policy does not permit renewal")
        before = {"due_date_ad": loan.due_date_ad.isoformat(), "renewal_count": loan.renewal_count, "fine_amount": str(loan.fine_amount)}
        loan.fine_amount = estimated_fine(loan)
        loan.due_date_ad = max(loan.due_date_ad, today()) + timedelta(days=data.due_days or loan.policy_snapshot.get("renewal_days", 14))
        loan.renewal_count += 1
        loan.status = IssueStatus.ISSUED
        await self.db.flush()
        await self._event(school_id, data, "renewed", payload, actor_id, actor_name, book_id=book.id,
            copy_id=copy.id, issue_id=loan.id, before=before,
            after={"due_date_ad": loan.due_date_ad.isoformat(), "renewal_count": loan.renewal_count, "fine_amount": str(loan.fine_amount)}, notes=data.notes)
        return loan

    async def mark_lost(self, school_id, issue_id, data: LostBookRequest, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "lost")
        if previous and previous.issue_id != issue_id:
            raise LibraryConflict("This request ID belongs to a different loan")
        if previous:
            return await self._loan(school_id, issue_id)
        loan, book, copy = await self._lock_circulation(school_id, issue_id)
        if loan.status not in OPEN or copy is None or copy.status != "issued":
            raise LibraryConflict("Only an active loan can be marked lost")
        before = {"status": effective_status(loan), "fine_amount": str(loan.fine_amount)}
        loan.status, loan.fine_amount, loan.notes = IssueStatus.LOST, data.fine_amount, data.notes
        loan.returned_to = actor_id
        copy.status = "lost"
        await self.db.flush()
        await self._sync_stock(book)
        await self._event(school_id, data, "lost", payload, actor_id, actor_name, book_id=book.id,
            copy_id=copy.id, issue_id=loan.id, before=before,
            after={"status": "lost", "fine_amount": str(loan.fine_amount), "copy_status": "lost"}, notes=data.notes)
        return loan

    def loan_response(self, loan):
        return {"id": str(loan.id), "book_id": str(loan.book_id), "copy_id": str(loan.copy_id) if loan.copy_id else None,
            "book_title": loan.book_title, "accession_number": loan.accession_number,
            "issued_to_id": str(loan.issued_to_id), "issued_to_type": loan.issued_to_type.value,
            "borrower_name": loan.borrower_name, "borrower_reference": loan.borrower_reference,
            "issue_date_ad": loan.issue_date_ad.isoformat(), "issue_date_bs": NepalCalendar.ad_to_bs(loan.issue_date_ad),
            "due_date_ad": loan.due_date_ad.isoformat(), "due_date_bs": NepalCalendar.ad_to_bs(loan.due_date_ad),
            "return_date_ad": loan.return_date_ad.isoformat() if loan.return_date_ad else None,
            "return_date_bs": NepalCalendar.ad_to_bs(loan.return_date_ad) if loan.return_date_ad else None,
            "status": effective_status(loan), "renewal_count": loan.renewal_count,
            "max_renewals": loan.policy_snapshot.get("max_renewals", 2),
            "renewal_days": loan.policy_snapshot.get("renewal_days", 14),
            "allow_overdue_renewal": loan.policy_snapshot.get("allow_overdue_renewal", False),
            "overdue_days": max(0, (today() - loan.due_date_ad).days) if loan.status in OPEN else 0,
            "fine_amount": str(loan.fine_amount), "estimated_fine": str(estimated_fine(loan)),
            "return_condition": loan.return_condition, "notes": loan.notes,
            "created_at": loan.created_at.isoformat()}

    def catalog_query(self, school_id, search=None, category=None, is_active=True, available_only=False):
        query = select(Book).where(Book.school_id == school_id)
        if is_active is not None:
            query = query.where(Book.is_active == is_active)
        if search:
            pattern = f"%{search}%"
            copy_match = select(BookCopy.id).where(BookCopy.school_id == school_id,
                BookCopy.book_id == Book.id, BookCopy.accession_number.ilike(pattern)).exists()
            query = query.where(or_(Book.title.ilike(pattern), Book.author.ilike(pattern), Book.isbn.ilike(pattern), copy_match))
        if category:
            query = query.where(Book.category == category)
        if available_only:
            query = query.where(Book.available_copies > 0, Book.is_active.is_(True), Book.is_lendable.is_(True))
        return query.order_by(Book.title, Book.id)

    async def _page(self, query, page=1, limit=20):
        total = await self.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        rows = (await self.db.scalars(query.offset((page - 1) * limit).limit(limit))).all()
        return rows, total

    async def list_books(self, school_id, page=1, limit=20, **filters):
        rows, total = await self._page(self.catalog_query(school_id, **filters), page, limit)
        return {"books": [BookResponse.model_validate(book).model_dump(mode="json") for book in rows], "total": total, "page": page, "limit": limit}

    async def list_copies(self, school_id, book_id, page=1, limit=20, status=None, search=None):
        await self._book(school_id, book_id)
        query = select(BookCopy).where(BookCopy.school_id == school_id, BookCopy.book_id == book_id)
        if status:
            query = query.where(BookCopy.status == status)
        if search:
            query = query.where(BookCopy.accession_number.ilike(f"%{search}%"))
        copies, total = await self._page(query.order_by(BookCopy.accession_number, BookCopy.id), page, limit)
        loans = (await self.db.scalars(select(BookIssue).where(BookIssue.school_id == school_id,
            BookIssue.copy_id.in_([copy.id for copy in copies]), BookIssue.status.in_((*OPEN, IssueStatus.LOST))))).all() if copies else []
        by_copy = {loan.copy_id: loan for loan in loans}
        return {"copies": [self.copy_response(copy, by_copy.get(copy.id)) for copy in copies], "total": total, "page": page, "limit": limit}

    def copy_response(self, copy, loan=None):
        return {"id": str(copy.id), "book_id": str(copy.book_id), "accession_number": copy.accession_number,
            "status": copy.status, "acquired_date_ad": copy.acquired_date_ad.isoformat(), "notes": copy.notes,
            "loan": self.loan_response(loan) if loan else None}

    async def borrowers(self, school_id, kind, search=None, page=1, limit=20):
        model = Student if kind == IssuedToType.STUDENT else Staff
        reference = (func.coalesce(Student.admission_number, Student.emis_student_id) if kind == IssuedToType.STUDENT else Staff.employee_id)
        active = model.status == StudentStatus.ACTIVE if kind == IssuedToType.STUDENT else model.status.in_((StaffStatus.ACTIVE, StaffStatus.ON_LEAVE))
        extra = (Student.current_grade.label("grade"), Student.current_section.label("section"), Student.roll_number.label("roll_number")) if kind == IssuedToType.STUDENT else (Staff.designation.label("designation"),)
        query = select(model.id, model.full_name_en.label("name"), reference.label("reference"), *extra).where(
            model.school_id == school_id, active, model.is_deleted.is_(False), model.deleted_at.is_(None))
        if search:
            query = query.where(or_(model.full_name_en.ilike(f"%{search}%"), model.full_name_np.ilike(f"%{search}%"), reference.ilike(f"%{search}%")))
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = (await self.db.execute(query.order_by(model.full_name_en, model.id).offset((page - 1) * limit).limit(limit))).mappings().all()
        counts = dict((await self.db.execute(select(BookIssue.issued_to_id, func.count()).where(BookIssue.school_id == school_id,
            BookIssue.issued_to_type == kind, BookIssue.issued_to_id.in_([row.id for row in rows]), BookIssue.status.in_(OPEN))
            .group_by(BookIssue.issued_to_id))).all()) if rows else {}
        return {"borrowers": [{**dict(row), "id": str(row.id), "type": kind.value,
            "active_loans": counts.get(row.id, 0)} for row in rows], "total": total, "page": page, "limit": limit}

    def loans_query(self, school_id, status=None, borrower_type=None, borrower_id=None, book_id=None, search=None, start_date=None, end_date=None):
        query = select(BookIssue).where(BookIssue.school_id == school_id)
        if start_date and end_date and start_date > end_date:
            raise ValueError("The start date must be on or before the end date")
        if status in ("active", "issued", "overdue"):
            query = query.where(BookIssue.status.in_(OPEN))
            if status == "issued":
                query = query.where(BookIssue.due_date_ad >= today())
            elif status == "overdue":
                query = query.where(BookIssue.due_date_ad < today())
        elif status:
            query = query.where(BookIssue.status == IssueStatus(status))
        if borrower_type:
            query = query.where(BookIssue.issued_to_type == borrower_type)
        if borrower_id:
            query = query.where(BookIssue.issued_to_id == borrower_id)
        if book_id:
            query = query.where(BookIssue.book_id == book_id)
        if search:
            pattern = f"%{search}%"
            query = query.where(or_(BookIssue.book_title.ilike(pattern), BookIssue.borrower_name.ilike(pattern), BookIssue.borrower_reference.ilike(pattern), BookIssue.accession_number.ilike(pattern)))
        if start_date:
            query = query.where(BookIssue.issue_date_ad >= start_date)
        if end_date:
            query = query.where(BookIssue.issue_date_ad <= end_date)
        return query.order_by(BookIssue.due_date_ad, BookIssue.id)

    async def list_loans(self, school_id, page=1, limit=20, **filters):
        loans, total = await self._page(self.loans_query(school_id, **filters), page, limit)
        return {"issues": [self.loan_response(loan) for loan in loans], "total": total, "page": page, "limit": limit}

    async def history(self, school_id, book_id=None, issue_id=None, page=1, limit=20):
        if book_id:
            await self._book(school_id, book_id)
        if issue_id:
            await self._loan(school_id, issue_id)
        query = select(LibraryEvent).where(LibraryEvent.school_id == school_id)
        if book_id:
            query = query.where(LibraryEvent.book_id == book_id)
        if issue_id:
            query = query.where(LibraryEvent.issue_id == issue_id)
        events, total = await self._page(query.order_by(LibraryEvent.created_at.desc(), LibraryEvent.id), page, limit)
        return {"events": [{"id": str(event.id), "action": event.action, "actor_name": event.actor_name,
            "notes": event.notes, "before": event.before_values, "after": event.after_values,
            "created_at": event.created_at.isoformat()} for event in events], "total": total, "page": page, "limit": limit}

    async def get_library_stats(self, school_id):
        titles, copies, available = (await self.db.execute(select(
            func.count().filter(Book.is_active.is_(True)), func.coalesce(func.sum(Book.total_copies), 0),
            func.coalesce(func.sum(Book.available_copies).filter(Book.is_active.is_(True)), 0),
        ).where(Book.school_id == school_id))).one()
        active, overdue, returned, lost, assessed = (await self.db.execute(select(
            func.count().filter(BookIssue.status.in_(OPEN)),
            func.count().filter(BookIssue.status.in_(OPEN) & (BookIssue.due_date_ad < today())),
            func.count().filter(BookIssue.status == IssueStatus.RETURNED),
            func.count().filter(BookIssue.status == IssueStatus.LOST),
            func.coalesce(func.sum(BookIssue.fine_amount), ZERO),
        ).where(BookIssue.school_id == school_id))).one()
        categories = dict((await self.db.execute(select(Book.category, func.count()).where(Book.school_id == school_id, Book.is_active.is_(True)).group_by(Book.category))).all())
        stock = dict((await self.db.execute(select(BookCopy.status, func.count()).where(BookCopy.school_id == school_id).group_by(BookCopy.status))).all())
        return {"total_books": titles, "total_copies": copies, "available_copies": available,
            "total_issued": active, "overdue_count": overdue, "total_returned": returned, "lost_loans": lost,
            "assessed_fines": str(assessed), "categories": {key.value: value for key, value in categories.items()}, "copy_states": stock}

    async def export_report(self, school_id, report, **filters):
        import csv
        import io
        query = self.catalog_query(school_id, **filters) if report == "catalog" else self.loans_query(school_id, **filters)
        rows = (await self.db.scalars(query.limit(50_001))).all()
        if len(rows) > 50_000:
            raise ValueError("Narrow the report filters before exporting more than 50,000 records")
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        def safe(value):
            value = "" if value is None else str(value)
            return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value
        if report == "catalog":
            writer.writerow(["Title", "Author", "ISBN", "Category", "Language", "Reading level", "Shelf", "Registered copies", "On shelf", "Lendable", "Active"])
            for book in rows:
                writer.writerow([safe(value) for value in (book.title, book.author, book.isbn, book.category.value, book.language,
                    book.reading_level, book.shelf_location, book.total_copies, book.available_copies, book.is_lendable, book.is_active)])
        else:
            writer.writerow(["Title", "Accession", "Borrower", "Borrower type", "Reference", "Issued AD", "Issued BS", "Due AD", "Due BS", "Returned AD", "Status", "Renewals", "Assessed fine NPR"])
            for loan in rows:
                writer.writerow([safe(value) for value in (loan.book_title, loan.accession_number, loan.borrower_name,
                    loan.issued_to_type.value, loan.borrower_reference, loan.issue_date_ad, NepalCalendar.ad_to_bs(loan.issue_date_ad),
                    loan.due_date_ad, NepalCalendar.ad_to_bs(loan.due_date_ad), loan.return_date_ad, effective_status(loan), loan.renewal_count, loan.fine_amount)])
        return ("\ufeff" + stream.getvalue()).encode("utf-8")

    async def _loan(self, school_id, issue_id, lock=False):
        query = select(BookIssue).where(BookIssue.school_id == school_id, BookIssue.id == issue_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        loan = await self.db.scalar(query)
        if loan is None:
            raise RecordNotFoundError("BookIssue", str(issue_id))
        return loan

    async def policy(self, school_id, lock=False):
        await self.db.execute(pg_insert(LibraryPolicy).values(id=uuid4(), school_id=school_id,
            loan_days=14, student_limit=5, staff_limit=10, renewal_days=14, max_renewals=2,
            allow_overdue_renewal=False, daily_fine=ZERO, fine_cap=ZERO, next_accession_number=1,
        ).on_conflict_do_nothing(index_elements=["school_id"]))
        query = select(LibraryPolicy).where(LibraryPolicy.school_id == school_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return await self.db.scalar(query)

    def policy_response(self, policy):
        return {field: str(getattr(policy, field)) if field in ("daily_fine", "fine_cap") else getattr(policy, field) for field in POLICY_FIELDS}

    async def update_policy(self, school_id, data: LendingPolicyUpdate, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "policy_updated")
        policy = await self.policy(school_id, lock=True)
        if previous:
            return self.policy_response(policy)
        before = self.policy_response(policy)
        for field in POLICY_FIELDS:
            setattr(policy, field, getattr(data, field))
        await self.db.flush()
        await self._event(school_id, data, "policy_updated", payload, actor_id, actor_name, before=before, after=self.policy_response(policy))
        return self.policy_response(policy)

    async def _add_stock(self, school_id, book, policy, count, accession_numbers=None, notes=None):
        if accession_numbers is None:
            accession_numbers = []
            # The policy counter is locked before the book row for stock adds.
            # Skip any imported/manual accession using the automatic namespace.
            while len(accession_numbers) < count:
                remaining = count - len(accession_numbers)
                candidates = [f"LIB-{number:06d}" for number in range(policy.next_accession_number, policy.next_accession_number + remaining)]
                policy.next_accession_number += remaining
                existing = set((await self.db.scalars(select(BookCopy.accession_number).where(BookCopy.school_id == school_id, BookCopy.accession_number.in_(candidates)))).all())
                accession_numbers.extend(value for value in candidates if value not in existing)
        copies = [BookCopy(id=uuid4(), school_id=school_id, book_id=book.id,
            accession_number=accession, acquired_date_ad=today(), status="available", notes=notes) for accession in accession_numbers]
        self.db.add_all(copies)
        await self.db.flush()
        await self._sync_stock(book)
        return copies

    async def _sync_stock(self, book):
        total, available = (await self.db.execute(select(
            func.count().filter(BookCopy.status != "withdrawn"), func.count().filter(BookCopy.status == "available"),
        ).where(BookCopy.school_id == book.school_id, BookCopy.book_id == book.id))).one()
        book.total_copies, book.available_copies = total, available
        await self.db.flush()

    async def create_book(self, school_id, data: BookCreate, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "book_added")
        if previous:
            return await self._book(school_id, previous.book_id)
        policy = await self.policy(school_id, lock=True)
        book = Book(id=uuid4(), school_id=school_id, added_date_ad=today(), total_copies=0, available_copies=0,
            **data.model_dump(exclude={"request_id", "total_copies"}))
        self.db.add(book)
        await self.db.flush()
        copies = await self._add_stock(school_id, book, policy, data.total_copies)
        await self._event(school_id, data, "book_added", payload, actor_id, actor_name, book_id=book.id,
            after={"title": book.title, "copies_added": len(copies), "accessions": [copy.accession_number for copy in copies]})
        return book

    async def update_book(self, school_id, book_id, data: BookUpdate, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "book_updated")
        if previous and previous.book_id != book_id:
            raise LibraryConflict("This request ID belongs to a different title")
        book = await self._book(school_id, book_id, lock=True)
        if previous:
            return book
        values = data.model_dump(exclude_unset=True, exclude={"request_id"})
        if "total_copies" in values:
            if values.pop("total_copies") != book.total_copies:
                raise LibraryConflict("Use inventory to add or withdraw accessioned copies")
        before = {key: BookResponse.model_validate(book).model_dump(mode="json")[key] for key in values}
        for key, value in values.items():
            setattr(book, key, value)
        await self.db.flush()
        await self._event(school_id, data, "book_updated", payload, actor_id, actor_name, book_id=book.id,
            before=before, after={key: BookResponse.model_validate(book).model_dump(mode="json")[key] for key in values})
        return book

    async def add_copies(self, school_id, book_id, data: AddCopiesRequest, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "copies_added")
        if previous and previous.book_id != book_id:
            raise LibraryConflict("This request ID belongs to a different title")
        if previous:
            return await self._book(school_id, book_id)
        policy = await self.policy(school_id, lock=True)
        book = await self._book(school_id, book_id, lock=True)
        copies = await self._add_stock(school_id, book, policy, data.count, data.accession_numbers, data.notes)
        await self._event(school_id, data, "copies_added", payload, actor_id, actor_name, book_id=book.id,
            after={"copies_added": len(copies), "accessions": [copy.accession_number for copy in copies]}, notes=data.notes)
        return book

    async def update_copy(self, school_id, copy_id, data: CopyUpdateRequest, actor_id, actor_name=None):
        previous, payload = await self._begin(school_id, data, "copy_updated")
        copy = await self._copy(school_id, copy_id)
        if previous and previous.copy_id != copy_id:
            raise LibraryConflict("This request ID belongs to a different copy")
        if previous:
            return copy
        book = await self._book(school_id, copy.book_id, lock=True)
        copy = await self._copy(school_id, copy_id, lock=True)
        if copy.status == "issued":
            raise LibraryConflict("Return or mark the current loan lost before changing this copy")
        unresolved = await self.db.scalar(select(BookIssue.id).where(BookIssue.school_id == school_id,
            BookIssue.copy_id == copy.id, BookIssue.status.in_((*OPEN, IssueStatus.LOST))).limit(1))
        if unresolved and data.status != CopyStatus.WITHDRAWN:
            raise LibraryConflict("Recover this copy from its original loan before restoring availability")
        before = {"status": copy.status}
        copy.status, copy.notes = data.status.value, data.notes
        await self.db.flush()
        await self._sync_stock(book)
        await self._event(school_id, data, "copy_updated", payload, actor_id, actor_name, book_id=book.id,
            copy_id=copy.id, before=before, after={"status": copy.status, "accession_number": copy.accession_number}, notes=data.notes)
        return copy
