"""
Nepal School Management System - Library Models
Book catalog and issue/return tracking
"""

import uuid
from datetime import datetime, date
from sqlalchemy import CheckConstraint, Column, String, Boolean, Date, Integer, ForeignKey, Index, Enum as SQLEnum, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import enum

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


class BookCategory(str, enum.Enum):
    TEXTBOOK = "textbook"
    REFERENCE = "reference"
    FICTION = "fiction"
    NON_FICTION = "non_fiction"
    MAGAZINE = "magazine"
    NEWSPAPER = "newspaper"


class IssueStatus(str, enum.Enum):
    ISSUED = "issued"
    RETURNED = "returned"
    OVERDUE = "overdue"
    LOST = "lost"


class IssuedToType(str, enum.Enum):
    STUDENT = "student"
    STAFF = "staff"


class CopyStatus(str, enum.Enum):
    AVAILABLE = "available"
    ISSUED = "issued"
    DAMAGED = "damaged"
    LOST = "lost"
    WITHDRAWN = "withdrawn"


class Book(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "books"
    __table_args__ = (
        Index("idx_books_school_id", "school_id"),
        Index("ix_books_school_catalog", "school_id", "is_active", "title", "id"),
        Index("uq_books_school_isbn", "school_id", "isbn", unique=True, postgresql_where=text("isbn IS NOT NULL")),
        CheckConstraint("total_copies >= 0 AND available_copies >= 0 AND available_copies <= total_copies", name="ck_book_stock"),
    )

    isbn = Column(String(20), nullable=True, index=True)
    title = Column(String(300), nullable=False, index=True)
    author = Column(String(200), nullable=False)
    publisher = Column(String(200), nullable=True)
    edition = Column(String(50), nullable=True)
    category = Column(SQLEnum(BookCategory), default=BookCategory.TEXTBOOK, nullable=False)
    total_copies = Column(Integer, default=1, nullable=False)
    available_copies = Column(Integer, default=1, nullable=False)
    shelf_location = Column(String(50), nullable=True)
    cover_image_url = Column(String(500), nullable=True)
    added_date_ad = Column(Date, default=date.today, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_lendable = Column(Boolean, default=True, nullable=False)
    language = Column(String(50), nullable=True)
    reading_level = Column(String(50), nullable=True)

    issues = relationship("BookIssue", back_populates="book", lazy="raise")

    def __repr__(self):
        return f"<Book(title={self.title}, available={self.available_copies}/{self.total_copies})>"


class BookIssue(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "book_issues"
    __table_args__ = (
        Index("idx_book_issues_school_id", "school_id"),
        Index("ix_library_open_due", "school_id", "due_date_ad", postgresql_where=text("status IN ('ISSUED', 'OVERDUE')")),
        Index("ix_library_borrower", "school_id", "issued_to_type", "issued_to_id", "status"),
        Index("uq_library_copy_open_loan", "copy_id", unique=True, postgresql_where=text("status IN ('ISSUED', 'OVERDUE')")),
        CheckConstraint("fine_amount >= 0 AND renewal_count >= 0", name="ck_library_loan_values"),
        CheckConstraint("due_date_ad >= issue_date_ad AND (return_date_ad IS NULL OR return_date_ad >= issue_date_ad)", name="ck_library_loan_dates"),
        CheckConstraint("status = 'RETURNED' OR copy_id IS NOT NULL", name="ck_library_loan_copy"),
    )

    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="RESTRICT"), nullable=False, index=True)
    copy_id = Column(UUID(as_uuid=True), ForeignKey("book_copies.id", ondelete="RESTRICT"), nullable=True)
    book_title = Column(String(300), nullable=False)
    accession_number = Column(String(50), nullable=True)
    borrower_name = Column(String(200), nullable=False)
    borrower_reference = Column(String(50), nullable=True)
    return_condition = Column(String(20), nullable=True)
    notes = Column(String(1000), nullable=True)
    renewal_count = Column(Integer, default=0, nullable=False)
    policy_snapshot = Column(JSONB, default=dict, nullable=False)
    issued_to_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    issued_to_type = Column(SQLEnum(IssuedToType), nullable=False)
    issue_date_ad = Column(Date, nullable=False, default=date.today)
    due_date_ad = Column(Date, nullable=False)
    return_date_ad = Column(Date, nullable=True)
    status = Column(SQLEnum(IssueStatus), default=IssueStatus.ISSUED, nullable=False, index=True)
    fine_amount = Column(Numeric(10, 2), default=0, nullable=False)
    issued_by = Column(UUID(as_uuid=True), nullable=True)
    returned_to = Column(UUID(as_uuid=True), nullable=True)

    book = relationship("Book", back_populates="issues")

    def __repr__(self):
        return f"<BookIssue(book_id={self.book_id}, status={self.status})>"


class BookCopy(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "book_copies"
    __table_args__ = (
        Index("uq_library_accession", "school_id", "accession_number", unique=True),
        Index("ix_library_copy_inventory", "school_id", "book_id", "status"),
        CheckConstraint("status IN ('available', 'issued', 'damaged', 'lost', 'withdrawn')", name="ck_library_copy_status"),
    )
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="RESTRICT"), nullable=False)
    accession_number = Column(String(50), nullable=False)
    status = Column(String(20), default="available", nullable=False)
    acquired_date_ad = Column(Date, nullable=False)
    notes = Column(String(1000), nullable=True)


class LibraryPolicy(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "library_policies"
    __table_args__ = (
        Index("uq_library_policy_school", "school_id", unique=True),
        CheckConstraint("loan_days BETWEEN 1 AND 90 AND renewal_days BETWEEN 1 AND 90 AND max_renewals BETWEEN 0 AND 10", name="ck_library_policy_periods"),
        CheckConstraint("student_limit BETWEEN 1 AND 100 AND staff_limit BETWEEN 1 AND 100 AND next_accession_number >= 1", name="ck_library_policy_limits"),
        CheckConstraint("daily_fine >= 0 AND fine_cap >= 0 AND (daily_fine = 0 OR fine_cap > 0)", name="ck_library_policy_fines"),
    )
    loan_days = Column(Integer, default=14, nullable=False)
    student_limit = Column(Integer, default=5, nullable=False)
    staff_limit = Column(Integer, default=10, nullable=False)
    renewal_days = Column(Integer, default=14, nullable=False)
    max_renewals = Column(Integer, default=2, nullable=False)
    allow_overdue_renewal = Column(Boolean, default=False, nullable=False)
    daily_fine = Column(Numeric(10, 2), default=0, nullable=False)
    fine_cap = Column(Numeric(10, 2), default=0, nullable=False)
    next_accession_number = Column(Integer, default=1, nullable=False)


class LibraryEvent(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "library_events"
    __table_args__ = (
        Index("uq_library_request", "school_id", "request_id", unique=True),
        Index("ix_library_history", "school_id", "book_id", "created_at"),
        Index("ix_library_loan_history", "school_id", "issue_id", "created_at"),
    )
    request_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(30), nullable=False)
    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="RESTRICT"), nullable=True)
    copy_id = Column(UUID(as_uuid=True), ForeignKey("book_copies.id", ondelete="RESTRICT"), nullable=True)
    issue_id = Column(UUID(as_uuid=True), ForeignKey("book_issues.id", ondelete="RESTRICT"), nullable=True)
    actor_id = Column(UUID(as_uuid=True), nullable=False)
    actor_name = Column(String(200), nullable=True)
    notes = Column(String(1000), nullable=True)
    payload = Column(JSONB, nullable=False)
    before_values = Column(JSONB, default=dict, nullable=False)
    after_values = Column(JSONB, default=dict, nullable=False)
