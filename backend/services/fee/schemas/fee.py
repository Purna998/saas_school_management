"""Validated requests and decimal-valued accounting responses."""

import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Optional
from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator
from services.fee.models.fee import DiscountType, FeeFrequency, FeeStatus, PaymentMethod
from shared.utils.nepali_calendar import NepalCalendar


def normalize_academic_year(value: str) -> str:
    value = value.strip()
    if not re.fullmatch(r"\d{4}(?:/\d{3,4})?", value):
        raise ValueError("Use a BS academic year such as 2083 or 2083/084")
    year = int(value[:4])
    if "/" in value and int(value.split("/")[1]) not in (year + 1, (year + 1) % 1000):
        raise ValueError("The second year must follow the first year")
    NepalCalendar.bs_to_ad(f"{year}-01-01")
    return f"{year}/{(year + 1) % 1000:03d}"


AcademicYear = Annotated[str, AfterValidator(normalize_academic_year)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class FeeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class FeeHeadCreate(FeeSchema):
    name: str = Field(min_length=1, max_length=100)
    amount: PositiveMoney
    frequency: FeeFrequency = FeeFrequency.monthly
    is_optional: bool = False


class FeeHeadResponse(FeeHeadCreate):
    id: uuid.UUID
    fee_structure_id: uuid.UUID
    created_at: datetime
    is_billed: bool = False


class FeeStructureCreate(FeeSchema):
    academic_year_bs: AcademicYear
    grade: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    fee_heads: list[FeeHeadCreate] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def distinct_heads(self):
        names = [head.name.casefold() for head in self.fee_heads]
        if len(names) != len(set(names)):
            raise ValueError("Fee head names must be unique within a structure")
        if self.grade.isdigit():
            self.grade = str(int(self.grade))
            if not 1 <= int(self.grade) <= 12:
                raise ValueError("Numeric grades must be between 1 and 12")
        return self


class FeeStructureUpdate(FeeSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    description: Optional[str] = Field(default=None, max_length=2000)
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def non_null_required_fields(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Name cannot be empty")
        if "is_active" in self.model_fields_set and self.is_active is None:
            raise ValueError("Active status cannot be empty")
        return self


class FeeStructureResponse(FeeSchema):
    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_bs: str
    grade: str
    name: str
    description: Optional[str] = None
    is_active: bool
    fee_heads: list[FeeHeadResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class GenerateLedgerRequest(FeeSchema):
    academic_year_bs: AcademicYear
    grade: str = Field(min_length=1, max_length=20)
    student_ids: list[uuid.UUID] = Field(min_length=1, max_length=2000)
    fee_structure_id: Optional[uuid.UUID] = None
    months: list[int] = Field(default_factory=lambda: list(range(1, 13)), min_length=1, max_length=12)
    optional_head_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    due_day_bs: int = Field(default=10, ge=1, le=28)

    @model_validator(mode="after")
    def valid_selection(self):
        if self.grade.isdigit():
            self.grade = str(int(self.grade))
            if not 1 <= int(self.grade) <= 12:
                raise ValueError("Numeric grades must be between 1 and 12")
        if len(set(self.student_ids)) != len(self.student_ids):
            raise ValueError("Select each student only once")
        if len(set(self.months)) != len(self.months) or any(month < 1 or month > 12 for month in self.months):
            raise ValueError("Select distinct BS months between 1 and 12")
        if len(set(self.optional_head_ids)) != len(self.optional_head_ids):
            raise ValueError("Select each optional fee only once")
        return self


class FeePaymentRequest(FeeSchema):
    student_id: uuid.UUID
    ledger_id: Optional[uuid.UUID] = None
    fee_head_id: Optional[uuid.UUID] = None
    amount: PositiveMoney
    payment_method: PaymentMethod = PaymentMethod.cash
    reference: Optional[str] = Field(default=None, max_length=100)
    remarks: Optional[str] = Field(default=None, max_length=500)
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)

    @model_validator(mode="after")
    def validate_payment(self):
        if self.ledger_id is None and self.fee_head_id is None:
            raise ValueError("Select the bill being paid")
        if self.payment_method != PaymentMethod.cash and not self.reference:
            raise ValueError("A bank transaction or cheque reference is required")
        return self


class FeeRefundRequest(FeeSchema):
    amount: PositiveMoney
    reason: str = Field(min_length=3, max_length=500)
    payment_method: PaymentMethod = PaymentMethod.cash
    reference: Optional[str] = Field(default=None, max_length=100)
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)

    @model_validator(mode="after")
    def validate_reference(self):
        if self.payment_method != PaymentMethod.cash and not self.reference:
            raise ValueError("A bank transaction or cheque reference is required")
        return self


class FeeRefundResponse(FeeSchema):
    id: uuid.UUID
    payment_id: uuid.UUID
    student_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod
    reference: Optional[str] = None
    reason: str
    refund_number: str
    refunded_date_ad: date
    refunded_date_bs: str
    refunded_by: uuid.UUID
    created_at: datetime


class FeePaymentResponse(FeeSchema):
    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    ledger_id: uuid.UUID
    amount: Decimal
    refunded_amount: Decimal = Decimal("0.00")
    payment_method: PaymentMethod
    reference: Optional[str] = None
    receipt_number: str
    paid_date_ad: date
    paid_date_bs: Optional[str] = None
    received_by: uuid.UUID
    remarks: Optional[str] = None
    balance_after: Optional[Decimal] = None
    created_at: datetime


class LedgerEntryResponse(FeeSchema):
    id: uuid.UUID
    student_id: uuid.UUID
    fee_head_id: uuid.UUID
    fee_head_name: str
    academic_year_bs: str
    month_bs: Optional[str] = None
    original_amount: Decimal
    discount_amount: Decimal
    amount_due: Decimal
    amount_paid: Decimal
    balance: Decimal
    due_date_ad: date
    due_date_bs: str
    status: FeeStatus
    payments: list[FeePaymentResponse] = Field(default_factory=list)


class StudentFeeStatusResponse(FeeSchema):
    student_id: uuid.UUID
    student_name: str
    academic_year_bs: str
    total_original: Decimal
    total_discount: Decimal
    total_due: Decimal
    total_paid: Decimal
    total_balance: Decimal
    ledger_entries: list[LedgerEntryResponse]


class StudentOutstandingEntry(FeeSchema):
    student_id: uuid.UUID
    student_name: str
    grade: Optional[int] = None
    section: Optional[str] = None
    total_due: Decimal
    total_paid: Decimal
    total_balance: Decimal
    overdue_count: int


class OutstandingFeesResponse(FeeSchema):
    school_id: uuid.UUID
    grade: Optional[str] = None
    section: Optional[str] = None
    academic_year_bs: Optional[str] = None
    total_outstanding: Decimal
    student_count: int
    page: int = 1
    limit: int = 20
    students: list[StudentOutstandingEntry]


class MonthlyCollectionEntry(FeeSchema):
    month_bs: str
    total_collected: Decimal
    total_pending: Decimal
    payment_count: int


class FeeCollectionSummaryResponse(FeeSchema):
    school_id: uuid.UUID
    academic_year_bs: str
    total_original: Decimal
    total_discount: Decimal
    total_due: Decimal
    gross_collected: Decimal
    total_refunded: Decimal
    total_collected: Decimal
    total_pending: Decimal
    total_overdue: Decimal
    collection_rate: Decimal
    monthly_breakdown: list[MonthlyCollectionEntry]


class ScholarshipCreate(FeeSchema):
    student_id: uuid.UUID
    name: str = Field(min_length=1, max_length=150)
    discount_type: DiscountType
    discount_value: PositiveMoney
    academic_year_bs: AcademicYear
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    ledger_ids: Optional[list[uuid.UUID]] = Field(default=None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def percentage_limit(self):
        if self.discount_type == DiscountType.percentage and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100%")
        if self.ledger_ids is not None and len(set(self.ledger_ids)) != len(self.ledger_ids):
            raise ValueError("Select each bill only once")
        return self


class ScholarshipResponse(FeeSchema):
    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    name: str
    discount_type: DiscountType
    discount_value: Decimal
    academic_year_bs: str
    applied_amount: Decimal
    applied_by: Optional[uuid.UUID] = None
    reversed_by: Optional[uuid.UUID] = None
    reversed_at: Optional[datetime] = None
    reversal_reason: Optional[str] = None
    is_active: bool
    created_at: datetime


class ScholarshipReversalRequest(FeeSchema):
    reason: str = Field(min_length=3, max_length=500)
