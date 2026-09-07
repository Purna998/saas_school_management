"""
Nepal School Management System - Library Models
Book catalog and issue/return tracking
"""

import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Boolean, DateTime, Date, Integer, Text, ForeignKey, Enum as SQLEnum, Numeric
from sqlalchemy.dialects.postgresql import UUID
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


class Book(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "books"

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

    issues = relationship("BookIssue", back_populates="book", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Book(title={self.title}, available={self.available_copies}/{self.total_copies})>"


class BookIssue(Base, BaseModel, TimestampMixin, TenantMixin):
    __tablename__ = "book_issues"

    book_id = Column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
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
