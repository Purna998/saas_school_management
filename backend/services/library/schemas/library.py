"""Validated catalog, inventory, circulation and school lending policy."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional
from uuid import UUID, uuid4
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from services.library.models.library import BookCategory, CopyStatus, IssuedToType

Fine = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


def normalize_isbn(value):
    if value is not None and not isinstance(value, str):
        raise ValueError("ISBN must be text")
    if value is None or not value.strip():
        return None
    value = value.replace("-", "").replace(" ", "").upper()
    valid = len(value) == 13 and value.isascii() and value.isdigit() and sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(value)) % 10 == 0
    if len(value) == 10 and value[:9].isascii() and value[:9].isdigit() and value[-1] in "0123456789X":
        valid = sum((10 - i) * (10 if c == "X" else int(c)) for i, c in enumerate(value)) % 11 == 0
    if not valid:
        raise ValueError("Enter a valid ISBN-10 or ISBN-13, or leave ISBN blank")
    return value


class LibrarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class LibraryCommand(LibrarySchema):
    request_id: UUID = Field(default_factory=uuid4)


class BookCreate(LibraryCommand):
    isbn: Optional[str] = Field(default=None, max_length=30)
    title: str = Field(min_length=1, max_length=300)
    author: str = Field(min_length=1, max_length=200)
    publisher: Optional[str] = Field(default=None, max_length=200)
    edition: Optional[str] = Field(default=None, max_length=50)
    category: BookCategory = BookCategory.TEXTBOOK
    total_copies: int = Field(default=1, ge=1, le=500)
    shelf_location: Optional[str] = Field(default=None, max_length=50)
    language: Optional[str] = Field(default=None, max_length=50)
    reading_level: Optional[str] = Field(default=None, max_length=50)
    is_lendable: Optional[bool] = None
    _isbn = field_validator("isbn", mode="before")(normalize_isbn)

    @model_validator(mode="after")
    def reference_default(self):
        if self.is_lendable is None:
            self.is_lendable = self.category not in (BookCategory.REFERENCE, BookCategory.NEWSPAPER)
        return self


class BookUpdate(LibraryCommand):
    isbn: Optional[str] = Field(default=None, max_length=30)
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    author: Optional[str] = Field(default=None, min_length=1, max_length=200)
    publisher: Optional[str] = Field(default=None, max_length=200)
    edition: Optional[str] = Field(default=None, max_length=50)
    category: Optional[BookCategory] = None
    total_copies: Optional[int] = Field(default=None, ge=0)
    shelf_location: Optional[str] = Field(default=None, max_length=50)
    language: Optional[str] = Field(default=None, max_length=50)
    reading_level: Optional[str] = Field(default=None, max_length=50)
    is_lendable: Optional[bool] = None
    is_active: Optional[bool] = None
    _isbn = field_validator("isbn", mode="before")(normalize_isbn)

    @model_validator(mode="after")
    def required_values(self):
        for name in ("title", "author", "category", "is_active", "is_lendable", "total_copies"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name.replace('_', ' ')} cannot be empty")
        return self


class BookResponse(LibrarySchema):
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
    language: Optional[str] = None
    reading_level: Optional[str] = None
    is_lendable: bool
    is_active: bool
    added_date_ad: date
    created_at: datetime


class BookListResponse(LibrarySchema):
    books: list[BookResponse]
    total: int
    page: int
    limit: int


class AddCopiesRequest(LibraryCommand):
    count: int = Field(default=1, ge=1, le=500)
    accession_numbers: Optional[list[str]] = Field(default=None, min_length=1, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def valid_accessions(self):
        if self.accession_numbers is not None:
            values = [unicodedata.normalize("NFC", value.strip().upper()) for value in self.accession_numbers]
            if len(values) != self.count or len(set(values)) != len(values):
                raise ValueError("Provide one distinct accession number for each new copy")
            if any(not value or len(value) > 50 or not value[0].isalnum() or any(not c.isalnum() and not unicodedata.category(c).startswith("M") and c not in "-_./" for c in value) for value in values):
                raise ValueError("Accession numbers must start with a letter/number and contain only letters, numbers, -, _, ., or /")
            self.accession_numbers = values
        return self


class CopyUpdateRequest(LibraryCommand):
    status: CopyStatus
    notes: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def no_manual_issue(self):
        if self.status == CopyStatus.ISSUED:
            raise ValueError("Issue a copy through the borrowing workflow")
        return self


class IssueBookRequest(LibraryCommand):
    book_id: UUID
    copy_id: Optional[UUID] = None
    issued_to_id: UUID
    issued_to_type: IssuedToType = IssuedToType.STUDENT
    due_days: Optional[int] = Field(default=None, ge=1, le=90)
    notes: Optional[str] = Field(default=None, max_length=1000)


class ReturnBookRequest(LibraryCommand):
    book_issue_id: UUID
    condition: Literal["good", "damaged"] = "good"
    fine_amount: Optional[Fine] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def explain_assessment(self):
        if (self.condition == "damaged" or (self.fine_amount is not None and self.fine_amount > 0)) and (not self.notes or len(self.notes) < 3):
            raise ValueError("Add a reason for damage or a fine assessment")
        return self


class RenewBookRequest(LibraryCommand):
    due_days: Optional[int] = Field(default=None, ge=1, le=90)
    notes: Optional[str] = Field(default=None, max_length=1000)


class LostBookRequest(LibraryCommand):
    fine_amount: Fine = Decimal("0.00")
    notes: str = Field(min_length=3, max_length=1000)


class LendingPolicyUpdate(LibraryCommand):
    loan_days: int = Field(default=14, ge=1, le=90)
    student_limit: int = Field(default=5, ge=1, le=100)
    staff_limit: int = Field(default=10, ge=1, le=100)
    renewal_days: int = Field(default=14, ge=1, le=90)
    max_renewals: int = Field(default=2, ge=0, le=10)
    allow_overdue_renewal: bool = False
    daily_fine: Fine = Decimal("0.00")
    fine_cap: Fine = Decimal("0.00")

    @model_validator(mode="after")
    def cap_required(self):
        if self.daily_fine > 0 and self.fine_cap == 0:
            raise ValueError("Set a positive fine cap when enabling a daily fine rate")
        return self
