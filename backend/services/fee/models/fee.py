"""
Nepal School Management System - Fee Service Models
Fee structure, ledger, payments, and scholarships
"""

import uuid
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Numeric,
    Date,
    DateTime,
    Text,
    Enum,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin, TenantMixin


# ─── Enums ───────────────────────────────────────────────────────────────────


class FeeFrequency(str, enum.Enum):
    """Fee payment frequency"""
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    one_time = "one_time"


class FeeStatus(str, enum.Enum):
    """Fee ledger entry status"""
    pending = "pending"
    partial = "partial"
    paid = "paid"
    overdue = "overdue"
    waived = "waived"


class PaymentMethod(str, enum.Enum):
    """Payment method options"""
    cash = "cash"
    bank_transfer = "bank_transfer"
    cheque = "cheque"


class DiscountType(str, enum.Enum):
    """Scholarship discount type"""
    percentage = "percentage"
    fixed = "fixed"


# ─── Models ──────────────────────────────────────────────────────────────────


class FeeStructure(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    Fee structure defines the fee plan for a grade in an academic year.
    Each school can have different structures per grade per year.
    """

    __tablename__ = "fee_structures"
    __table_args__ = (
        Index("idx_fee_structures_school_year", "school_id", "academic_year_bs"),
        Index("idx_fee_structures_school_grade", "school_id", "grade"),
    )

    academic_year_bs = Column(
        String(9),
        nullable=False,
        comment="Academic year in BS (e.g. 2081/082)",
    )
    grade = Column(
        String(20),
        nullable=False,
        comment="Grade/class (e.g. 1, 2, ... 12, Nursery, LKG, UKG)",
    )
    name = Column(
        String(150),
        nullable=False,
        comment="Fee structure name (e.g. 'Grade 10 Regular Fee 2081')",
    )
    description = Column(
        Text,
        nullable=True,
        comment="Optional description",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Relationships
    fee_heads = relationship("FeeHead", back_populates="fee_structure", lazy="selectin")


class FeeHead(Base, BaseModel, TimestampMixin):
    """
    Individual fee component within a fee structure.
    Examples: Tuition, Exam Fee, Lab Fee, Computer Fee, etc.
    """

    __tablename__ = "fee_heads"
    __table_args__ = (
        Index("idx_fee_heads_structure", "fee_structure_id"),
    )

    fee_structure_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fee_structures.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(
        String(100),
        nullable=False,
        comment="Fee head name (e.g. 'Tuition', 'Exam Fee')",
    )
    amount = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Fee amount in NPR",
    )
    frequency = Column(
        Enum(FeeFrequency, name="fee_frequency_enum"),
        nullable=False,
        default=FeeFrequency.monthly,
        comment="Payment frequency",
    )
    is_optional = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the fee is optional (e.g. transport, hostel)",
    )

    # Relationships
    fee_structure = relationship("FeeStructure", back_populates="fee_heads")
    ledger_entries = relationship("FeeLedger", back_populates="fee_head", lazy="selectin")


class FeeLedger(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    Fee ledger tracks what each student owes and has paid for each fee head.
    One entry per student per fee head per billing period.
    """

    __tablename__ = "fee_ledger"
    __table_args__ = (
        Index("idx_fee_ledger_student", "school_id", "student_id"),
        Index("idx_fee_ledger_status", "school_id", "status"),
        Index("idx_fee_ledger_due_date", "due_date_ad"),
        Index("idx_fee_ledger_year_month", "academic_year_bs", "month_bs"),
    )

    student_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Reference to student (from student service)",
    )
    fee_head_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fee_heads.id", ondelete="RESTRICT"),
        nullable=False,
    )
    academic_year_bs = Column(
        String(9),
        nullable=False,
        comment="Academic year in BS (e.g. 2081/082)",
    )
    month_bs = Column(
        String(7),
        nullable=True,
        comment="Month in BS for monthly fees (e.g. 2081-01). NULL for annual/one-time.",
    )
    amount_due = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total amount due",
    )
    amount_paid = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total amount paid so far",
    )
    balance = Column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Remaining balance (amount_due - amount_paid)",
    )
    due_date_ad = Column(
        Date,
        nullable=False,
        comment="Due date in AD for sorting and overdue calculation",
    )
    status = Column(
        Enum(FeeStatus, name="fee_status_enum"),
        nullable=False,
        default=FeeStatus.pending,
        index=True,
    )

    # Relationships
    fee_head = relationship("FeeHead", back_populates="ledger_entries")
    payments = relationship("FeePayment", back_populates="ledger", lazy="selectin")


class FeePayment(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    Records individual fee payments made by students.
    Each payment generates a unique receipt number.
    """

    __tablename__ = "fee_payments"
    __table_args__ = (
        Index("idx_fee_payments_student", "school_id", "student_id"),
        Index("idx_fee_payments_receipt", "receipt_number", unique=True),
        Index("idx_fee_payments_date", "paid_date_ad"),
    )

    student_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Reference to student (from student service)",
    )
    ledger_id = Column(
        UUID(as_uuid=True),
        ForeignKey("fee_ledger.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Payment amount in NPR",
    )
    payment_method = Column(
        Enum(PaymentMethod, name="payment_method_enum"),
        nullable=False,
        default=PaymentMethod.cash,
    )
    receipt_number = Column(
        String(30),
        nullable=False,
        unique=True,
        comment="Unique receipt number (RCP-YYYYMMDD-XXXXX)",
    )
    paid_date_ad = Column(
        Date,
        nullable=False,
        comment="Payment date in AD",
    )
    paid_date_bs = Column(
        String(10),
        nullable=True,
        comment="Payment date in BS (YYYY-MM-DD)",
    )
    received_by = Column(
        UUID(as_uuid=True),
        nullable=False,
        comment="User ID who received the payment (cashier/accountant)",
    )
    remarks = Column(
        Text,
        nullable=True,
        comment="Additional payment remarks",
    )

    # Relationships
    ledger = relationship("FeeLedger", back_populates="payments")


class Scholarship(Base, BaseModel, TimestampMixin, TenantMixin):
    """
    Scholarship/discount applied to a student.
    Reduces fee amounts in the ledger.
    """

    __tablename__ = "scholarships"
    __table_args__ = (
        Index("idx_scholarships_student", "school_id", "student_id"),
        Index("idx_scholarships_year", "school_id", "academic_year_bs"),
    )

    student_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Reference to student (from student service)",
    )
    name = Column(
        String(150),
        nullable=False,
        comment="Scholarship name (e.g. 'Merit Scholarship', 'Dalit Scholarship')",
    )
    discount_type = Column(
        Enum(DiscountType, name="discount_type_enum"),
        nullable=False,
        comment="Discount type: percentage or fixed amount",
    )
    discount_value = Column(
        Numeric(12, 2),
        nullable=False,
        comment="Discount value (percentage 0-100 or fixed NPR amount)",
    )
    academic_year_bs = Column(
        String(9),
        nullable=False,
        comment="Academic year in BS (e.g. 2081/082)",
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
