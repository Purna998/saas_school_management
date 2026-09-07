"""
Nepal School Management System - Fee Service Business Logic
Handles fee structure management, ledger generation, payment collection, and scholarships
"""

import uuid
import random
import string
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.fee.models.fee import (
    FeeStructure,
    FeeHead,
    FeeLedger,
    FeePayment,
    Scholarship,
    FeeFrequency,
    FeeStatus,
    PaymentMethod,
    DiscountType,
)
from services.fee.schemas.fee import (
    FeeStructureCreate,
    FeeHeadCreate,
    FeePaymentRequest,
    GenerateLedgerRequest,
    ScholarshipCreate,
    StudentFeeStatusResponse,
    LedgerEntryResponse,
    StudentOutstandingEntry,
    OutstandingFeesResponse,
    FeeCollectionSummaryResponse,
    MonthlyCollectionEntry,
)
from shared.utils.exceptions import RecordNotFoundError, DuplicateRecordError


class FeeService:
    """Fee management business logic"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Fee Structure Management ────────────────────────────────────────────

    async def create_fee_structure(
        self,
        school_id: uuid.UUID,
        data: FeeStructureCreate,
    ) -> FeeStructure:
        """
        Create a new fee structure for a grade and academic year.

        Args:
            school_id: Tenant school UUID
            data: Fee structure creation data

        Returns:
            Created FeeStructure with fee heads
        """
        # Check for duplicate structure (same school, year, grade, name)
        existing = await self.db.execute(
            select(FeeStructure).where(
                and_(
                    FeeStructure.school_id == school_id,
                    FeeStructure.academic_year_bs == data.academic_year_bs,
                    FeeStructure.grade == data.grade,
                    FeeStructure.name == data.name,
                )
            )
        )
        if existing.scalar_one_or_none():
            raise DuplicateRecordError(
                model="FeeStructure",
                field="name",
                value=data.name,
            )

        # Create fee structure
        fee_structure = FeeStructure(
            school_id=school_id,
            academic_year_bs=data.academic_year_bs,
            grade=data.grade,
            name=data.name,
            description=data.description,
            is_active=True,
        )
        self.db.add(fee_structure)
        await self.db.flush()

        # Create fee heads if provided
        if data.fee_heads:
            for head_data in data.fee_heads:
                fee_head = FeeHead(
                    fee_structure_id=fee_structure.id,
                    name=head_data.name,
                    amount=head_data.amount,
                    frequency=head_data.frequency,
                    is_optional=head_data.is_optional,
                )
                self.db.add(fee_head)

        await self.db.flush()

        # Reload with relationships
        await self.db.refresh(fee_structure, attribute_names=["fee_heads"])
        return fee_structure

    async def get_fee_structures(
        self,
        school_id: uuid.UUID,
        academic_year_bs: Optional[str] = None,
        grade: Optional[str] = None,
        is_active: Optional[bool] = True,
    ) -> List[FeeStructure]:
        """
        List fee structures with optional filters.

        Args:
            school_id: Tenant school UUID
            academic_year_bs: Filter by academic year
            grade: Filter by grade
            is_active: Filter by active status

        Returns:
            List of FeeStructure objects
        """
        query = select(FeeStructure).where(
            FeeStructure.school_id == school_id
        ).options(selectinload(FeeStructure.fee_heads))

        if academic_year_bs:
            query = query.where(FeeStructure.academic_year_bs == academic_year_bs)
        if grade:
            query = query.where(FeeStructure.grade == grade)
        if is_active is not None:
            query = query.where(FeeStructure.is_active == is_active)

        query = query.order_by(FeeStructure.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def add_fee_head(
        self,
        fee_structure_id: uuid.UUID,
        data: FeeHeadCreate,
    ) -> FeeHead:
        """
        Add a fee head to an existing fee structure.

        Args:
            fee_structure_id: Fee structure UUID
            data: Fee head creation data

        Returns:
            Created FeeHead

        Raises:
            RecordNotFoundError: If fee structure not found
        """
        # Verify fee structure exists
        result = await self.db.execute(
            select(FeeStructure).where(FeeStructure.id == fee_structure_id)
        )
        fee_structure = result.scalar_one_or_none()
        if not fee_structure:
            raise RecordNotFoundError(
                model="FeeStructure",
                identifier=str(fee_structure_id),
            )

        fee_head = FeeHead(
            fee_structure_id=fee_structure_id,
            name=data.name,
            amount=data.amount,
            frequency=data.frequency,
            is_optional=data.is_optional,
        )
        self.db.add(fee_head)
        await self.db.flush()
        await self.db.refresh(fee_head)
        return fee_head

    # ─── Ledger Generation ───────────────────────────────────────────────────

    async def generate_ledger_entries(
        self,
        school_id: uuid.UUID,
        data: GenerateLedgerRequest,
    ) -> List[FeeLedger]:
        """
        Generate fee ledger entries for students in a grade based on fee structure.

        Creates one ledger entry per student per fee head per billing period.
        Monthly fees get 12 entries (Baisakh to Chaitra), annual/one-time get 1 entry.

        Args:
            school_id: Tenant school UUID
            data: Ledger generation request with academic year, grade, and student IDs

        Returns:
            List of created FeeLedger entries

        Raises:
            RecordNotFoundError: If no active fee structure found
        """
        # Find active fee structure for this grade and year
        result = await self.db.execute(
            select(FeeStructure)
            .where(
                and_(
                    FeeStructure.school_id == school_id,
                    FeeStructure.academic_year_bs == data.academic_year_bs,
                    FeeStructure.grade == data.grade,
                    FeeStructure.is_active == True,
                )
            )
            .options(selectinload(FeeStructure.fee_heads))
        )
        fee_structure = result.scalar_one_or_none()
        if not fee_structure:
            raise RecordNotFoundError(
                model="FeeStructure",
                identifier=f"grade={data.grade}, year={data.academic_year_bs}",
            )

        # BS months (Nepali calendar: Baisakh=01 to Chaitra=12)
        bs_months = [f"{data.academic_year_bs[:4]}-{str(m).zfill(2)}" for m in range(1, 13)]

        created_entries = []

        for student_id in data.student_ids:
            for fee_head in fee_structure.fee_heads:
                # Skip optional fees (they need to be opted in separately)
                if fee_head.is_optional:
                    continue

                if fee_head.frequency == FeeFrequency.monthly:
                    # Create 12 monthly entries
                    for i, month_bs in enumerate(bs_months):
                        # Due date: 10th of each following month (approximate AD date)
                        due_date = self._calculate_due_date(data.academic_year_bs, i + 1)

                        # Check if entry already exists
                        existing = await self._check_ledger_exists(
                            school_id, student_id, fee_head.id,
                            data.academic_year_bs, month_bs,
                        )
                        if existing:
                            continue

                        entry = FeeLedger(
                            school_id=school_id,
                            student_id=student_id,
                            fee_head_id=fee_head.id,
                            academic_year_bs=data.academic_year_bs,
                            month_bs=month_bs,
                            amount_due=fee_head.amount,
                            amount_paid=Decimal("0.00"),
                            balance=fee_head.amount,
                            due_date_ad=due_date,
                            status=FeeStatus.pending,
                        )
                        self.db.add(entry)
                        created_entries.append(entry)

                elif fee_head.frequency == FeeFrequency.quarterly:
                    # Create 4 quarterly entries (months 1, 4, 7, 10)
                    quarter_months = [1, 4, 7, 10]
                    for q_month in quarter_months:
                        month_bs = f"{data.academic_year_bs[:4]}-{str(q_month).zfill(2)}"
                        due_date = self._calculate_due_date(data.academic_year_bs, q_month)

                        existing = await self._check_ledger_exists(
                            school_id, student_id, fee_head.id,
                            data.academic_year_bs, month_bs,
                        )
                        if existing:
                            continue

                        entry = FeeLedger(
                            school_id=school_id,
                            student_id=student_id,
                            fee_head_id=fee_head.id,
                            academic_year_bs=data.academic_year_bs,
                            month_bs=month_bs,
                            amount_due=fee_head.amount,
                            amount_paid=Decimal("0.00"),
                            balance=fee_head.amount,
                            due_date_ad=due_date,
                            status=FeeStatus.pending,
                        )
                        self.db.add(entry)
                        created_entries.append(entry)

                elif fee_head.frequency in (FeeFrequency.annual, FeeFrequency.one_time):
                    # Single entry for the year
                    due_date = self._calculate_due_date(data.academic_year_bs, 1)

                    existing = await self._check_ledger_exists(
                        school_id, student_id, fee_head.id,
                        data.academic_year_bs, None,
                    )
                    if existing:
                        continue

                    entry = FeeLedger(
                        school_id=school_id,
                        student_id=student_id,
                        fee_head_id=fee_head.id,
                        academic_year_bs=data.academic_year_bs,
                        month_bs=None,
                        amount_due=fee_head.amount,
                        amount_paid=Decimal("0.00"),
                        balance=fee_head.amount,
                        due_date_ad=due_date,
                        status=FeeStatus.pending,
                    )
                    self.db.add(entry)
                    created_entries.append(entry)

        await self.db.flush()
        return created_entries

    async def _check_ledger_exists(
        self,
        school_id: uuid.UUID,
        student_id: uuid.UUID,
        fee_head_id: uuid.UUID,
        academic_year_bs: str,
        month_bs: Optional[str],
    ) -> bool:
        """Check if a ledger entry already exists for given parameters"""
        conditions = [
            FeeLedger.school_id == school_id,
            FeeLedger.student_id == student_id,
            FeeLedger.fee_head_id == fee_head_id,
            FeeLedger.academic_year_bs == academic_year_bs,
        ]
        if month_bs:
            conditions.append(FeeLedger.month_bs == month_bs)
        else:
            conditions.append(FeeLedger.month_bs.is_(None))

        result = await self.db.execute(
            select(FeeLedger.id).where(and_(*conditions)).limit(1)
        )
        return result.scalar_one_or_none() is not None

    def _calculate_due_date(self, academic_year_bs: str, month_number: int) -> date:
        """
        Calculate approximate AD due date for a BS month.

        Nepal academic year typically starts in Baisakh (mid-April).
        This is an approximation; a proper BS-to-AD converter should be used in production.

        Args:
            academic_year_bs: Academic year string (e.g. "2081/082")
            month_number: BS month number (1=Baisakh to 12=Chaitra)

        Returns:
            Approximate due date in AD
        """
        # BS year start (e.g. "2081" -> AD ~2024)
        bs_year = int(academic_year_bs[:4])
        ad_year = bs_year - 57  # Approximate conversion

        # Baisakh (month 1) starts around April 14
        # Each subsequent month adds ~30 days
        # Due date is 10th of the following month
        base_month = 4 + month_number  # April + month offset
        if base_month > 12:
            base_month -= 12
            ad_year += 1

        # Clamp day to valid range
        day = 10
        try:
            return date(ad_year, base_month, day)
        except ValueError:
            # Handle edge cases (e.g., Feb 30)
            return date(ad_year, base_month, 28)

    # ─── Fee Collection ──────────────────────────────────────────────────────

    async def collect_fee(
        self,
        school_id: uuid.UUID,
        data: FeePaymentRequest,
        received_by: uuid.UUID,
    ) -> FeePayment:
        """
        Record a fee payment for a student.

        Finds the appropriate ledger entry, records the payment,
        updates the ledger balance, and generates a receipt number.

        Args:
            school_id: Tenant school UUID
            data: Payment request data
            received_by: UUID of the user collecting the payment

        Returns:
            Created FeePayment with receipt number

        Raises:
            RecordNotFoundError: If no pending ledger entry found
            ValueError: If payment amount exceeds balance
        """
        # Find the pending/partial ledger entry for this student + fee head
        result = await self.db.execute(
            select(FeeLedger).where(
                and_(
                    FeeLedger.school_id == school_id,
                    FeeLedger.student_id == data.student_id,
                    FeeLedger.fee_head_id == data.fee_head_id,
                    FeeLedger.status.in_([FeeStatus.pending, FeeStatus.partial, FeeStatus.overdue]),
                )
            ).order_by(FeeLedger.due_date_ad.asc())
        )
        ledger_entry = result.scalar_one_or_none()

        if not ledger_entry:
            raise RecordNotFoundError(
                model="FeeLedger",
                identifier=f"student={data.student_id}, fee_head={data.fee_head_id}",
            )

        # Validate payment amount
        if data.amount > ledger_entry.balance:
            raise ValueError(
                f"Payment amount ({data.amount}) exceeds outstanding balance ({ledger_entry.balance})"
            )

        # Generate receipt number: RCP-YYYYMMDD-XXXXX
        receipt_number = self._generate_receipt_number()

        # Create payment record
        today = date.today()
        payment = FeePayment(
            school_id=school_id,
            student_id=data.student_id,
            ledger_id=ledger_entry.id,
            amount=data.amount,
            payment_method=data.payment_method,
            receipt_number=receipt_number,
            paid_date_ad=today,
            paid_date_bs=None,  # BS date conversion can be added later
            received_by=received_by,
            remarks=data.remarks,
        )
        self.db.add(payment)

        # Update ledger entry
        ledger_entry.amount_paid = ledger_entry.amount_paid + data.amount
        ledger_entry.balance = ledger_entry.amount_due - ledger_entry.amount_paid

        # Update status
        if ledger_entry.balance <= Decimal("0.00"):
            ledger_entry.status = FeeStatus.paid
            ledger_entry.balance = Decimal("0.00")
        else:
            ledger_entry.status = FeeStatus.partial

        await self.db.flush()
        await self.db.refresh(payment)
        return payment

    def _generate_receipt_number(self) -> str:
        """
        Generate unique receipt number in format: RCP-YYYYMMDD-XXXXX

        Returns:
            Receipt number string
        """
        today = date.today()
        date_part = today.strftime("%Y%m%d")
        random_part = "".join(random.choices(string.digits, k=5))
        return f"RCP-{date_part}-{random_part}"

    # ─── Student Fee Status ──────────────────────────────────────────────────

    async def get_student_fee_status(
        self,
        school_id: uuid.UUID,
        student_id: uuid.UUID,
        academic_year_bs: Optional[str] = None,
    ) -> StudentFeeStatusResponse:
        """
        Get complete fee status for a student.

        Args:
            school_id: Tenant school UUID
            student_id: Student UUID
            academic_year_bs: Optional filter by academic year

        Returns:
            StudentFeeStatusResponse with all ledger entries
        """
        query = (
            select(FeeLedger)
            .where(
                and_(
                    FeeLedger.school_id == school_id,
                    FeeLedger.student_id == student_id,
                )
            )
            .options(
                selectinload(FeeLedger.fee_head),
                selectinload(FeeLedger.payments),
            )
            .order_by(FeeLedger.due_date_ad.asc())
        )

        if academic_year_bs:
            query = query.where(FeeLedger.academic_year_bs == academic_year_bs)

        result = await self.db.execute(query)
        ledger_entries = list(result.scalars().all())

        # Calculate totals
        total_due = sum(entry.amount_due for entry in ledger_entries)
        total_paid = sum(entry.amount_paid for entry in ledger_entries)
        total_balance = sum(entry.balance for entry in ledger_entries)

        # Build response
        entries_response = []
        for entry in ledger_entries:
            entry_dict = LedgerEntryResponse(
                id=entry.id,
                student_id=entry.student_id,
                fee_head_id=entry.fee_head_id,
                fee_head_name=entry.fee_head.name if entry.fee_head else None,
                academic_year_bs=entry.academic_year_bs,
                month_bs=entry.month_bs,
                amount_due=entry.amount_due,
                amount_paid=entry.amount_paid,
                balance=entry.balance,
                due_date_ad=entry.due_date_ad,
                status=entry.status,
                payments=[],
            )
            entries_response.append(entry_dict)

        return StudentFeeStatusResponse(
            student_id=student_id,
            academic_year_bs=academic_year_bs or "all",
            total_due=total_due,
            total_paid=total_paid,
            total_balance=total_balance,
            ledger_entries=entries_response,
        )

    # ─── Outstanding Fees Report ─────────────────────────────────────────────

    async def get_outstanding_fees(
        self,
        school_id: uuid.UUID,
        grade: Optional[str] = None,
        section: Optional[str] = None,
    ) -> OutstandingFeesResponse:
        """
        Get students with outstanding (unpaid/overdue) fees.

        Args:
            school_id: Tenant school UUID
            grade: Optional grade filter
            section: Optional section filter (reserved for future use)

        Returns:
            OutstandingFeesResponse with list of students and totals
        """
        # Query ledger entries that are not fully paid
        query = (
            select(
                FeeLedger.student_id,
                func.sum(FeeLedger.amount_due).label("total_due"),
                func.sum(FeeLedger.amount_paid).label("total_paid"),
                func.sum(FeeLedger.balance).label("total_balance"),
                func.count(
                    func.nullif(FeeLedger.status == FeeStatus.overdue, False)
                ).label("overdue_count"),
            )
            .where(
                and_(
                    FeeLedger.school_id == school_id,
                    FeeLedger.status.in_([
                        FeeStatus.pending,
                        FeeStatus.partial,
                        FeeStatus.overdue,
                    ]),
                )
            )
            .group_by(FeeLedger.student_id)
            .having(func.sum(FeeLedger.balance) > 0)
        )

        # Note: grade/section filtering would require joining with student data
        # from the student service. For now, we filter by fee_structure grade
        # through ledger -> fee_head -> fee_structure relationship.
        if grade:
            query = query.join(
                FeeHead, FeeLedger.fee_head_id == FeeHead.id
            ).join(
                FeeStructure, FeeHead.fee_structure_id == FeeStructure.id
            ).where(FeeStructure.grade == grade)

        result = await self.db.execute(query)
        rows = result.all()

        students = []
        total_outstanding = Decimal("0.00")

        for row in rows:
            student_entry = StudentOutstandingEntry(
                student_id=row.student_id,
                total_due=row.total_due or Decimal("0.00"),
                total_paid=row.total_paid or Decimal("0.00"),
                total_balance=row.total_balance or Decimal("0.00"),
                overdue_count=row.overdue_count or 0,
            )
            students.append(student_entry)
            total_outstanding += student_entry.total_balance

        return OutstandingFeesResponse(
            school_id=school_id,
            grade=grade,
            section=section,
            total_outstanding=total_outstanding,
            student_count=len(students),
            students=students,
        )

    # ─── Fee Collection Summary ──────────────────────────────────────────────

    async def get_fee_collection_summary(
        self,
        school_id: uuid.UUID,
        academic_year_bs: str,
    ) -> FeeCollectionSummaryResponse:
        """
        Get fee collection summary for an academic year.

        Args:
            school_id: Tenant school UUID
            academic_year_bs: Academic year in BS

        Returns:
            FeeCollectionSummaryResponse with totals and monthly breakdown
        """
        # Overall totals from ledger
        totals_result = await self.db.execute(
            select(
                func.sum(FeeLedger.amount_due).label("total_due"),
                func.sum(FeeLedger.amount_paid).label("total_collected"),
                func.sum(FeeLedger.balance).label("total_pending"),
            ).where(
                and_(
                    FeeLedger.school_id == school_id,
                    FeeLedger.academic_year_bs == academic_year_bs,
                )
            )
        )
        totals = totals_result.one()

        total_collected = totals.total_collected or Decimal("0.00")
        total_pending = totals.total_pending or Decimal("0.00")
        total_due = totals.total_due or Decimal("0.00")

        # Overdue total
        overdue_result = await self.db.execute(
            select(func.sum(FeeLedger.balance)).where(
                and_(
                    FeeLedger.school_id == school_id,
                    FeeLedger.academic_year_bs == academic_year_bs,
                    FeeLedger.status == FeeStatus.overdue,
                )
            )
        )
        total_overdue = overdue_result.scalar() or Decimal("0.00")

        # Collection rate
        collection_rate = Decimal("0.00")
        if total_due > 0:
            collection_rate = (total_collected / total_due * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )

        # Monthly breakdown from ledger entries
        monthly_result = await self.db.execute(
            select(
                FeeLedger.month_bs,
                func.sum(FeeLedger.amount_paid).label("total_collected"),
                func.sum(FeeLedger.balance).label("total_pending"),
                func.count(
                    func.nullif(FeeLedger.amount_paid > 0, False)
                ).label("payment_count"),
            ).where(
                and_(
                    FeeLedger.school_id == school_id,
                    FeeLedger.academic_year_bs == academic_year_bs,
                    FeeLedger.month_bs.isnot(None),
                )
            ).group_by(FeeLedger.month_bs).order_by(FeeLedger.month_bs)
        )
        monthly_rows = monthly_result.all()

        monthly_breakdown = []
        for row in monthly_rows:
            monthly_breakdown.append(
                MonthlyCollectionEntry(
                    month_bs=row.month_bs or "annual",
                    total_collected=row.total_collected or Decimal("0.00"),
                    total_pending=row.total_pending or Decimal("0.00"),
                    payment_count=row.payment_count or 0,
                )
            )

        return FeeCollectionSummaryResponse(
            school_id=school_id,
            academic_year_bs=academic_year_bs,
            total_collected=total_collected,
            total_pending=total_pending,
            total_overdue=total_overdue,
            collection_rate=collection_rate,
            monthly_breakdown=monthly_breakdown,
        )

    # ─── Scholarship Management ──────────────────────────────────────────────

    async def apply_scholarship(
        self,
        school_id: uuid.UUID,
        data: ScholarshipCreate,
    ) -> Scholarship:
        """
        Apply a scholarship/discount to a student.

        Creates the scholarship record and adjusts pending ledger entries
        by reducing the amount_due and balance.

        Args:
            school_id: Tenant school UUID
            data: Scholarship creation data

        Returns:
            Created Scholarship record
        """
        # Validate discount value for percentage type
        if data.discount_type == DiscountType.percentage and data.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100%")

        # Create scholarship record
        scholarship = Scholarship(
            school_id=school_id,
            student_id=data.student_id,
            name=data.name,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            academic_year_bs=data.academic_year_bs,
            is_active=True,
        )
        self.db.add(scholarship)
        await self.db.flush()

        # Apply discount to pending ledger entries for this student/year
        result = await self.db.execute(
            select(FeeLedger).where(
                and_(
                    FeeLedger.school_id == school_id,
                    FeeLedger.student_id == data.student_id,
                    FeeLedger.academic_year_bs == data.academic_year_bs,
                    FeeLedger.status.in_([FeeStatus.pending, FeeStatus.partial]),
                )
            )
        )
        pending_entries = list(result.scalars().all())

        for entry in pending_entries:
            if data.discount_type == DiscountType.percentage:
                discount_amount = (entry.amount_due * data.discount_value / 100).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            else:
                # Fixed discount spread across entries
                discount_amount = min(data.discount_value, entry.balance)

            # Reduce amount due and recalculate balance
            new_due = entry.amount_due - discount_amount
            if new_due < Decimal("0.00"):
                new_due = Decimal("0.00")

            entry.amount_due = new_due
            entry.balance = entry.amount_due - entry.amount_paid

            # Update status if fully covered
            if entry.balance <= Decimal("0.00"):
                entry.status = FeeStatus.paid
                entry.balance = Decimal("0.00")

        await self.db.flush()
        await self.db.refresh(scholarship)
        return scholarship
