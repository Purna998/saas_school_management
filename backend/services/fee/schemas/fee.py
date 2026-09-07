"""
Nepal School Management System - Fee Service Schemas
Pydantic request/response models for fee management
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator

from services.fee.models.fee import FeeFrequency, FeeStatus, PaymentMethod, DiscountType


# ─── Fee Structure Schemas ───────────────────────────────────────────────────


class FeeHeadCreate(BaseModel):
    """Schema for creating a fee head"""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Fee head name (e.g. 'Tuition', 'Exam Fee')",
        examples=["Tuition Fee"],
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Fee amount in NPR",
        examples=[1500.00],
    )
    frequency: FeeFrequency = Field(
        ...,
        description="Payment frequency",
        examples=["monthly"],
    )
    is_optional: bool = Field(
        default=False,
        description="Whether the fee is optional",
    )


class FeeHeadResponse(BaseModel):
    """Schema for fee head response"""

    id: uuid.UUID
    fee_structure_id: uuid.UUID
    name: str
    amount: Decimal
    frequency: FeeFrequency
    is_optional: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FeeStructureCreate(BaseModel):
    """Schema for creating a fee structure"""

    academic_year_bs: str = Field(
        ...,
        min_length=7,
        max_length=9,
        description="Academic year in BS (e.g. '2081/082')",
        examples=["2081/082"],
    )
    grade: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Grade/class",
        examples=["10"],
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Fee structure name",
        examples=["Grade 10 Regular Fee 2081"],
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional description",
    )
    fee_heads: Optional[List[FeeHeadCreate]] = Field(
        default=None,
        description="Optional list of fee heads to create with the structure",
    )


class FeeStructureResponse(BaseModel):
    """Schema for fee structure response"""

    id: uuid.UUID
    school_id: uuid.UUID
    academic_year_bs: str
    grade: str
    name: str
    description: Optional[str]
    is_active: bool
    fee_heads: List[FeeHeadResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Fee Payment Schemas ─────────────────────────────────────────────────────


class FeePaymentRequest(BaseModel):
    """Schema for recording a fee payment"""

    student_id: uuid.UUID = Field(
        ...,
        description="Student UUID",
    )
    fee_head_id: uuid.UUID = Field(
        ...,
        description="Fee head UUID (identifies what is being paid)",
    )
    amount: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Payment amount in NPR",
        examples=[1500.00],
    )
    payment_method: PaymentMethod = Field(
        default=PaymentMethod.cash,
        description="Payment method",
    )
    remarks: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Additional payment remarks",
    )


class FeePaymentResponse(BaseModel):
    """Schema for fee payment response"""

    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    ledger_id: uuid.UUID
    amount: Decimal
    payment_method: PaymentMethod
    receipt_number: str
    paid_date_ad: date
    paid_date_bs: Optional[str]
    received_by: uuid.UUID
    remarks: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Ledger Schemas ──────────────────────────────────────────────────────────


class LedgerEntryResponse(BaseModel):
    """Schema for a single ledger entry"""

    id: uuid.UUID
    student_id: uuid.UUID
    fee_head_id: uuid.UUID
    fee_head_name: Optional[str] = None
    academic_year_bs: str
    month_bs: Optional[str]
    amount_due: Decimal
    amount_paid: Decimal
    balance: Decimal
    due_date_ad: date
    status: FeeStatus
    payments: List[FeePaymentResponse] = []

    class Config:
        from_attributes = True


class GenerateLedgerRequest(BaseModel):
    """Schema for generating ledger entries for a grade"""

    academic_year_bs: str = Field(
        ...,
        min_length=7,
        max_length=9,
        description="Academic year in BS",
        examples=["2081/082"],
    )
    grade: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Grade/class",
        examples=["10"],
    )
    student_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="List of student UUIDs to generate ledger entries for",
    )


# ─── Student Fee Status Schemas ──────────────────────────────────────────────


class StudentFeeStatusResponse(BaseModel):
    """Schema for complete fee status of a student"""

    student_id: uuid.UUID
    academic_year_bs: str
    total_due: Decimal
    total_paid: Decimal
    total_balance: Decimal
    ledger_entries: List[LedgerEntryResponse]


# ─── Outstanding Fees Schemas ────────────────────────────────────────────────


class StudentOutstandingEntry(BaseModel):
    """Schema for a student's outstanding fees summary"""

    student_id: uuid.UUID
    total_due: Decimal
    total_paid: Decimal
    total_balance: Decimal
    overdue_count: int


class OutstandingFeesResponse(BaseModel):
    """Schema for outstanding fees report"""

    school_id: uuid.UUID
    grade: Optional[str]
    section: Optional[str]
    total_outstanding: Decimal
    student_count: int
    students: List[StudentOutstandingEntry]


# ─── Fee Collection Summary Schemas ──────────────────────────────────────────


class MonthlyCollectionEntry(BaseModel):
    """Schema for monthly fee collection"""

    month_bs: str
    total_collected: Decimal
    total_pending: Decimal
    payment_count: int


class FeeCollectionSummaryResponse(BaseModel):
    """Schema for fee collection summary"""

    school_id: uuid.UUID
    academic_year_bs: str
    total_collected: Decimal
    total_pending: Decimal
    total_overdue: Decimal
    collection_rate: Decimal = Field(description="Collection rate as percentage")
    monthly_breakdown: List[MonthlyCollectionEntry]


# ─── Scholarship Schemas ─────────────────────────────────────────────────────


class ScholarshipCreate(BaseModel):
    """Schema for applying a scholarship"""

    student_id: uuid.UUID = Field(
        ...,
        description="Student UUID",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Scholarship name",
        examples=["Merit Scholarship"],
    )
    discount_type: DiscountType = Field(
        ...,
        description="Discount type: percentage or fixed",
    )
    discount_value: Decimal = Field(
        ...,
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Discount value (percentage 0-100 or fixed NPR amount)",
        examples=[25.00],
    )
    academic_year_bs: str = Field(
        ...,
        min_length=7,
        max_length=9,
        description="Academic year in BS",
        examples=["2081/082"],
    )

    @field_validator("discount_value")
    @classmethod
    def validate_discount_value(cls, v, info):
        """Validate that percentage is between 0 and 100"""
        # Note: We can only validate range for percentage after knowing discount_type.
        # Full cross-field validation is done in the service layer.
        if v <= 0:
            raise ValueError("Discount value must be positive")
        return v


class ScholarshipResponse(BaseModel):
    """Schema for scholarship response"""

    id: uuid.UUID
    school_id: uuid.UUID
    student_id: uuid.UUID
    name: str
    discount_type: DiscountType
    discount_value: Decimal
    academic_year_bs: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
