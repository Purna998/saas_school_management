"""Tenant-scoped fee accounting. The request boundary owns each transaction."""

import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import String, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.auth.models.user import User
from services.fee.models.fee import (
    DiscountType, FeeDiscountAllocation, FeeFrequency, FeeHead, FeeLedger, FeePayment, FeeRefund,
    FeeStatus, FeeStructure, Scholarship,
)
from services.fee.schemas.fee import (
    FeeCollectionSummaryResponse, FeeHeadCreate, FeePaymentRequest, FeePaymentResponse,
    FeeRefundRequest, FeeRefundResponse, FeeStructureCreate, FeeStructureUpdate,
    GenerateLedgerRequest, LedgerEntryResponse, MonthlyCollectionEntry,
    OutstandingFeesResponse, ScholarshipCreate, StudentFeeStatusResponse,
    StudentOutstandingEntry, normalize_academic_year,
)
from services.student.models.student import Student, StudentStatus
from services.tenant.models.tenant import Tenant
from shared.utils.exceptions import RecordNotFoundError
from shared.utils.nepali_calendar import NPT, NepalCalendar

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class FeeConflictError(ValueError):
    """A change conflicts with existing billing or a previously used request ID."""


def school_today():
    return datetime.now(NPT).date()


def ledger_status(entry):
    if entry.balance == ZERO:
        return FeeStatus.waived if entry.amount_due == ZERO else FeeStatus.paid
    if entry.due_date_ad < school_today():
        return FeeStatus.overdue
    return FeeStatus.partial if entry.amount_paid > ZERO else FeeStatus.pending


class FeeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _request_lock(self, school_id, request_id):
        # Serializes retries before checking the unique request key. Row locks
        # below separately serialize different operations on the same student.
        await self.db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {
            "key": f"fee:{school_id}:{request_id}",
        })

    async def _student(self, school_id, student_id, *, lock=False):
        query = select(Student).where(Student.school_id == school_id, Student.id == student_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        student = (await self.db.execute(query)).scalar_one_or_none()
        if student is None:
            raise RecordNotFoundError("Student", str(student_id))
        return student

    async def _structure(self, school_id, structure_id, *, lock=False):
        query = select(FeeStructure).where(FeeStructure.school_id == school_id, FeeStructure.id == structure_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        structure = (await self.db.execute(query)).scalar_one_or_none()
        if structure is None:
            raise RecordNotFoundError("FeeStructure", str(structure_id))
        return structure

    async def create_fee_structure(self, school_id, data: FeeStructureCreate):
        existing = await self.db.scalar(select(FeeStructure.id).where(
            FeeStructure.school_id == school_id, FeeStructure.grade == data.grade,
            FeeStructure.academic_year_bs == data.academic_year_bs, FeeStructure.is_active.is_(True),
        ))
        if existing:
            raise FeeConflictError("An active fee structure already exists for this grade and academic year")
        billed = await self.db.scalar(select(FeeLedger.id).join(FeeHead, FeeHead.id == FeeLedger.fee_head_id)
            .join(FeeStructure, FeeStructure.id == FeeHead.fee_structure_id).where(
                FeeStructure.school_id == school_id, FeeLedger.school_id == school_id,
                FeeStructure.grade == data.grade, FeeStructure.academic_year_bs == data.academic_year_bs,
            ).limit(1))
        if billed:
            raise FeeConflictError("This grade and year already have a billed structure. Restore it or use a new academic year to avoid charging the same periods twice")
        structure = FeeStructure(
            school_id=school_id, academic_year_bs=data.academic_year_bs, grade=data.grade,
            name=data.name, description=data.description, is_active=True,
            fee_heads=[FeeHead(**head.model_dump()) for head in data.fee_heads],
        )
        self.db.add(structure)
        await self.db.flush()
        return structure

    async def get_fee_structures(self, school_id, academic_year_bs=None, grade=None, is_active=True):
        query = select(FeeStructure).where(FeeStructure.school_id == school_id)
        if academic_year_bs:
            query = query.where(FeeStructure.academic_year_bs == normalize_academic_year(academic_year_bs))
        if grade:
            query = query.where(FeeStructure.grade == grade)
        if is_active is not None:
            query = query.where(FeeStructure.is_active == is_active)
        structures = list((await self.db.scalars(query.order_by(FeeStructure.created_at.desc(), FeeStructure.id))).all())
        if structures:
            billed = set((await self.db.scalars(select(FeeLedger.fee_head_id).where(
                FeeLedger.school_id == school_id,
                FeeLedger.fee_head_id.in_([head.id for structure in structures for head in structure.fee_heads]),
            ).distinct())).all())
            for structure in structures:
                for head in structure.fee_heads:
                    head.is_billed = head.id in billed
        return structures

    async def update_fee_structure(self, school_id, structure_id, data: FeeStructureUpdate):
        structure = await self._structure(school_id, structure_id, lock=True)
        if data.is_active:
            existing = await self.db.scalar(select(FeeStructure.id).where(
                FeeStructure.school_id == school_id, FeeStructure.grade == structure.grade,
                FeeStructure.academic_year_bs == structure.academic_year_bs,
                FeeStructure.is_active.is_(True), FeeStructure.id != structure.id,
            ))
            if existing:
                raise FeeConflictError("Archive the current active structure before restoring this one")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(structure, field, value)
        await self.db.flush()
        await self.db.refresh(structure, attribute_names=["updated_at"])
        return structure

    async def add_fee_head(self, fee_structure_id, data: FeeHeadCreate, school_id):
        structure = await self._structure(school_id, fee_structure_id, lock=True)
        if not structure.is_active:
            raise FeeConflictError("Restore the fee structure before changing its fee heads")
        if any(head.name.casefold() == data.name.casefold() for head in structure.fee_heads):
            raise FeeConflictError("A fee head with this name already exists")
        if len(structure.fee_heads) >= 50:
            raise ValueError("A structure can contain at most 50 fee heads")
        head = FeeHead(fee_structure_id=structure.id, **data.model_dump())
        self.db.add(head)
        await self.db.flush()
        return head

    async def change_fee_head(self, school_id, structure_id, head_id, data=None):
        structure = await self._structure(school_id, structure_id, lock=True)
        head = next((head for head in structure.fee_heads if head.id == head_id), None)
        if head is None:
            raise RecordNotFoundError("FeeHead", str(head_id))
        if await self.db.scalar(select(FeeLedger.id).where(FeeLedger.fee_head_id == head_id).limit(1)):
            raise FeeConflictError("Billed fee heads are locked. Existing bills and receipts must retain their terms")
        if data is None:
            await self.db.delete(head)
        else:
            if any(other.id != head_id and other.name.casefold() == data.name.casefold() for other in structure.fee_heads):
                raise FeeConflictError("A fee head with this name already exists")
            for field, value in data.model_dump().items():
                setattr(head, field, value)
        await self.db.flush()
        return head

    async def generate_ledger_entries(self, school_id, data: GenerateLedgerRequest):
        if data.fee_structure_id:
            structure = await self._structure(school_id, data.fee_structure_id, lock=True)
        else:
            structure_id = await self.db.scalar(select(FeeStructure.id).where(
                FeeStructure.school_id == school_id, FeeStructure.grade == data.grade,
                FeeStructure.academic_year_bs == data.academic_year_bs, FeeStructure.is_active.is_(True),
            ))
            if structure_id is None:
                raise RecordNotFoundError("FeeStructure", f"grade={data.grade}, year={data.academic_year_bs}")
            structure = await self._structure(school_id, structure_id, lock=True)
        if not structure.is_active or structure.grade != data.grade or structure.academic_year_bs != data.academic_year_bs:
            raise ValueError("Select an active structure matching the grade and academic year")
        if not data.grade.isdigit():
            raise ValueError("Billing requires a grade linked to current student enrollments")
        students = (await self.db.scalars(select(Student).where(
            Student.school_id == school_id, Student.id.in_(data.student_ids),
            Student.current_grade == int(data.grade), Student.status == StudentStatus.ACTIVE,
            Student.deleted_at.is_(None), Student.is_deleted.is_(False),
        ).order_by(Student.id).with_for_update())).all()
        if {student.id for student in students} != set(data.student_ids):
            raise ValueError("Every selected student must be active and enrolled in this school and grade")
        optional_ids = {head.id for head in structure.fee_heads if head.is_optional}
        if not set(data.optional_head_ids).issubset(optional_ids):
            raise ValueError("Optional fees must belong to the selected structure")
        periods = []
        for head in structure.fee_heads:
            if head.is_optional and head.id not in data.optional_head_ids:
                continue
            months = sorted(data.months)
            if head.frequency == FeeFrequency.quarterly:
                months = [month for month in months if month in (1, 4, 7, 10)]
            elif head.frequency in (FeeFrequency.annual, FeeFrequency.one_time):
                # Annual/one-time charges are only in a batch including Baisakh.
                months = [None] if 1 in data.months else []
            for month in months:
                due_date = NepalCalendar.bs_to_ad(f"{data.academic_year_bs[:4]}-{month or 1:02d}-{data.due_day_bs:02d}")
                periods.append((head, month, due_date))
        if not periods:
            raise ValueError("No fees match the selected periods and optional fee choices")
        expected = len(students) * len(periods)
        if expected > 25_000:
            raise ValueError("Generate at most 25,000 bills at once; select fewer students or months")
        values = [{
            "id": uuid.uuid4(), "school_id": school_id, "student_id": student.id,
            "fee_head_id": head.id, "fee_head_name": head.name,
            "academic_year_bs": data.academic_year_bs,
            "month_bs": f"{data.academic_year_bs[:4]}-{month:02d}" if month else None,
            "original_amount": head.amount, "discount_amount": ZERO,
            "amount_due": head.amount, "amount_paid": ZERO, "balance": head.amount,
            "due_date_ad": due_date,
            "status": FeeStatus.overdue if due_date < school_today() else FeeStatus.pending,
        } for student in students for head, month, due_date in periods]
        created, total = 0, ZERO
        for offset in range(0, len(values), 500):
            result = await self.db.execute(pg_insert(FeeLedger).values(values[offset:offset + 500])
                .on_conflict_do_nothing(index_elements=[
                    "school_id", "student_id", "fee_head_id", "academic_year_bs", text("coalesce(month_bs, '')"),
                ]).returning(FeeLedger.id, FeeLedger.amount_due))
            rows = result.all()
            created += len(rows)
            total += sum((row.amount_due for row in rows), ZERO)
        return {"entries_created": created, "entries_skipped": expected - created,
                "student_count": len(students), "total_assessed": str(total),
                "academic_year_bs": data.academic_year_bs, "grade": data.grade}

    async def collect_fee(self, school_id, data: FeePaymentRequest, received_by):
        await self._request_lock(school_id, data.request_id)
        await self._student(school_id, data.student_id, lock=True)
        existing = await self.db.scalar(select(FeePayment).where(
            FeePayment.school_id == school_id, FeePayment.request_id == data.request_id,
        ))
        if existing:
            previous_head = await self.db.scalar(select(FeeLedger.fee_head_id).where(FeeLedger.id == existing.ledger_id)) if data.fee_head_id else None
            same = (existing.student_id == data.student_id and existing.amount == data.amount
                    and existing.payment_method == data.payment_method and existing.reference == data.reference
                    and existing.remarks == data.remarks and (data.ledger_id is None or existing.ledger_id == data.ledger_id)
                    and (data.fee_head_id is None or previous_head == data.fee_head_id))
            if not same:
                raise FeeConflictError("This payment request ID was already used with different details")
            return existing
        query = select(FeeLedger).where(FeeLedger.school_id == school_id, FeeLedger.student_id == data.student_id)
        if data.ledger_id:
            query = query.where(FeeLedger.id == data.ledger_id)
        else:
            query = query.where(FeeLedger.fee_head_id == data.fee_head_id, FeeLedger.balance > ZERO)
        entry = (await self.db.scalars(query.order_by(FeeLedger.due_date_ad, FeeLedger.id)
            .limit(1).with_for_update().execution_options(populate_existing=True))).first()
        if entry is None:
            raise RecordNotFoundError("FeeLedger", str(data.ledger_id or data.fee_head_id))
        if data.fee_head_id and entry.fee_head_id != data.fee_head_id:
            raise ValueError("The selected fee head does not match this bill")
        if data.amount > entry.balance:
            raise ValueError(f"Payment exceeds the bill's remaining balance of NPR {entry.balance}")
        entry.amount_paid += data.amount
        entry.balance = entry.amount_due - entry.amount_paid
        entry.status = ledger_status(entry)
        today, payment_id = school_today(), uuid.uuid4()
        payment = FeePayment(
            id=payment_id, school_id=school_id, student_id=data.student_id, ledger_id=entry.id,
            amount=data.amount, refunded_amount=ZERO, payment_method=data.payment_method,
            reference=data.reference, receipt_number=f"RCP-{today:%Y%m%d}-{payment_id.hex[:16].upper()}",
            paid_date_ad=today, paid_date_bs=NepalCalendar.ad_to_bs(today), received_by=received_by,
            remarks=data.remarks, request_id=data.request_id, balance_after=entry.balance,
        )
        self.db.add(payment)
        await self.db.flush()
        return payment

    async def refund_payment(self, school_id, payment_id, data: FeeRefundRequest, refunded_by):
        await self._request_lock(school_id, data.request_id)
        payment = await self.db.scalar(select(FeePayment).where(FeePayment.school_id == school_id, FeePayment.id == payment_id))
        if payment is None:
            raise RecordNotFoundError("FeePayment", str(payment_id))
        await self._student(school_id, payment.student_id, lock=True)
        previous = await self.db.scalar(select(FeeRefund).where(FeeRefund.school_id == school_id, FeeRefund.request_id == data.request_id))
        if previous:
            if (previous.payment_id, previous.amount, previous.reason, previous.payment_method, previous.reference) != (payment_id, data.amount, data.reason, data.payment_method, data.reference):
                raise FeeConflictError("This refund request ID was already used with different details")
            return previous
        payment = await self.db.scalar(select(FeePayment).where(FeePayment.id == payment_id, FeePayment.school_id == school_id)
            .with_for_update().execution_options(populate_existing=True))
        entry = await self.db.scalar(select(FeeLedger).where(FeeLedger.id == payment.ledger_id, FeeLedger.school_id == school_id, FeeLedger.student_id == payment.student_id)
            .with_for_update().execution_options(populate_existing=True))
        if entry is None:
            raise RecordNotFoundError("FeeLedger", str(payment.ledger_id))
        if data.amount > payment.amount - payment.refunded_amount or data.amount > entry.amount_paid:
            raise ValueError("Refund exceeds the unrefunded payment or the bill's net paid amount")
        payment.refunded_amount += data.amount
        entry.amount_paid -= data.amount
        entry.balance = entry.amount_due - entry.amount_paid
        entry.status = ledger_status(entry)
        today, refund_id = school_today(), uuid.uuid4()
        refund = FeeRefund(
            id=refund_id, school_id=school_id, payment_id=payment.id, student_id=payment.student_id,
            request_id=data.request_id, amount=data.amount, reason=data.reason,
            payment_method=data.payment_method, reference=data.reference,
            refund_number=f"RFD-{today:%Y%m%d}-{refund_id.hex[:16].upper()}",
            refunded_date_ad=today, refunded_date_bs=NepalCalendar.ad_to_bs(today), refunded_by=refunded_by,
        )
        self.db.add(refund)
        await self.db.flush()
        return refund

    async def apply_scholarship(self, school_id, data: ScholarshipCreate, applied_by=None):
        await self._request_lock(school_id, data.request_id)
        await self._student(school_id, data.student_id, lock=True)
        previous = await self.db.scalar(select(Scholarship).where(Scholarship.school_id == school_id, Scholarship.request_id == data.request_id))
        if previous:
            if (previous.student_id, previous.name, previous.discount_type, previous.discount_value, previous.academic_year_bs) != (data.student_id, data.name, data.discount_type, data.discount_value, data.academic_year_bs):
                raise FeeConflictError("This scholarship request ID was already used with different details")
            requested = sorted(str(value) for value in data.ledger_ids) if data.ledger_ids is not None else None
            if previous.requested_ledger_ids != requested:
                raise FeeConflictError("This scholarship request ID was already used for different bills")
            return previous
        query = select(FeeLedger).where(
            FeeLedger.school_id == school_id, FeeLedger.student_id == data.student_id,
            FeeLedger.academic_year_bs == data.academic_year_bs, FeeLedger.balance > ZERO,
        )
        if data.ledger_ids is not None:
            query = query.where(FeeLedger.id.in_(data.ledger_ids))
        entries = (await self.db.scalars(query.order_by(FeeLedger.due_date_ad, FeeLedger.id).with_for_update()
            .execution_options(populate_existing=True))).all()
        if data.ledger_ids is not None and {entry.id for entry in entries} != set(data.ledger_ids):
            raise ValueError("Every selected bill must belong to this student and year and have an unpaid balance")
        outstanding = sum((entry.balance for entry in entries), ZERO)
        if outstanding == ZERO:
            raise ValueError("This student has no unpaid bills in the selected academic year")
        budget = data.discount_value if data.discount_type == DiscountType.fixed else (
            outstanding * data.discount_value / 100).quantize(CENT, rounding=ROUND_HALF_UP)
        if budget > outstanding:
            raise ValueError(f"The discount exceeds the unpaid balance of NPR {outstanding}")
        if budget == ZERO:
            raise ValueError("This percentage rounds to less than NPR 0.01")
        scholarship_id = uuid.uuid4()
        allocations = []
        remaining, cumulative, allocated = budget, ZERO, ZERO
        for entry in entries:
            if data.discount_type == DiscountType.percentage:
                # Cumulative rounding distributes a percentage proportionally
                # across bills while preserving the exact rounded total.
                cumulative += entry.balance
                target = (cumulative * data.discount_value / 100).quantize(CENT, rounding=ROUND_HALF_UP)
                discount, allocated = target - allocated, target
            else:
                discount = min(entry.balance, remaining)
            if discount == ZERO:
                continue
            entry.discount_amount += discount
            entry.amount_due -= discount
            entry.balance -= discount
            entry.status = ledger_status(entry)
            remaining -= discount
            allocations.append(FeeDiscountAllocation(school_id=school_id, scholarship_id=scholarship_id, ledger_id=entry.id, amount=discount))
            if remaining == ZERO:
                break
        scholarship = Scholarship(
            id=scholarship_id,
            school_id=school_id, student_id=data.student_id, name=data.name,
            discount_type=data.discount_type, discount_value=data.discount_value,
            academic_year_bs=data.academic_year_bs, is_active=True, request_id=data.request_id,
            applied_amount=budget, applied_by=applied_by,
            requested_ledger_ids=sorted(str(value) for value in data.ledger_ids) if data.ledger_ids is not None else None,
        )
        self.db.add(scholarship)
        await self.db.flush()
        self.db.add_all(allocations)
        await self.db.flush()
        return scholarship

    async def reverse_scholarship(self, school_id, scholarship_id, reason, reversed_by):
        scholarship = await self.db.scalar(select(Scholarship).where(Scholarship.school_id == school_id, Scholarship.id == scholarship_id))
        if scholarship is None:
            raise RecordNotFoundError("Scholarship", str(scholarship_id))
        await self._student(school_id, scholarship.student_id, lock=True)
        await self.db.refresh(scholarship)
        if not scholarship.is_active:
            return scholarship
        allocations = (await self.db.scalars(select(FeeDiscountAllocation).where(
            FeeDiscountAllocation.school_id == school_id, FeeDiscountAllocation.scholarship_id == scholarship.id,
        ))).all()
        if not allocations or sum((row.amount for row in allocations), ZERO) != scholarship.applied_amount:
            raise FeeConflictError("This legacy award has no complete bill allocation record and cannot be reversed automatically")
        entries = {entry.id: entry for entry in (await self.db.scalars(select(FeeLedger).where(
            FeeLedger.school_id == school_id, FeeLedger.student_id == scholarship.student_id,
            FeeLedger.id.in_([allocation.ledger_id for allocation in allocations]),
        ).order_by(FeeLedger.id).with_for_update().execution_options(populate_existing=True))).all()}
        for allocation in allocations:
            entry = entries.get(allocation.ledger_id)
            if entry is None or entry.discount_amount < allocation.amount:
                raise FeeConflictError("The award no longer matches its bill allocation record")
            entry.amount_due += allocation.amount
            entry.discount_amount -= allocation.amount
            entry.balance += allocation.amount
            entry.status = ledger_status(entry)
        scholarship.is_active = False
        scholarship.reversed_by = reversed_by
        scholarship.reversed_at = datetime.now(NPT)
        scholarship.reversal_reason = reason
        await self.db.flush()
        return scholarship

    async def get_student_fee_status(self, school_id, student_id, academic_year_bs=None):
        student = await self._student(school_id, student_id)
        query = select(FeeLedger).where(FeeLedger.school_id == school_id, FeeLedger.student_id == student_id)
        if academic_year_bs:
            query = query.where(FeeLedger.academic_year_bs == normalize_academic_year(academic_year_bs))
        entries = (await self.db.scalars(query.options(selectinload(FeeLedger.payments))
            .order_by(FeeLedger.due_date_ad, FeeLedger.fee_head_name, FeeLedger.id))).all()
        return StudentFeeStatusResponse(
            student_id=student.id, student_name=student.full_name_en,
            academic_year_bs=normalize_academic_year(academic_year_bs) if academic_year_bs else "all",
            total_original=sum((entry.original_amount for entry in entries), ZERO),
            total_discount=sum((entry.discount_amount for entry in entries), ZERO),
            total_due=sum((entry.amount_due for entry in entries), ZERO),
            total_paid=sum((entry.amount_paid for entry in entries), ZERO),
            total_balance=sum((entry.balance for entry in entries), ZERO),
            ledger_entries=[LedgerEntryResponse(
                id=entry.id, student_id=entry.student_id, fee_head_id=entry.fee_head_id,
                fee_head_name=entry.fee_head_name, academic_year_bs=entry.academic_year_bs,
                month_bs=entry.month_bs, original_amount=entry.original_amount,
                discount_amount=entry.discount_amount, amount_due=entry.amount_due,
                amount_paid=entry.amount_paid, balance=entry.balance, due_date_ad=entry.due_date_ad,
                due_date_bs=NepalCalendar.ad_to_bs(entry.due_date_ad), status=ledger_status(entry),
                payments=[FeePaymentResponse.model_validate(payment) for payment in sorted(entry.payments, key=lambda payment: (payment.created_at, payment.id))],
            ) for entry in entries],
        )

    async def search_students(self, school_id, search=None, grade=None, section=None, limit=20):
        query = select(Student.id, Student.full_name_en, Student.current_grade,
            Student.current_section, Student.roll_number, Student.status).where(Student.school_id == school_id)
        if search:
            pattern = f"%{search}%"
            query = query.where(or_(Student.full_name_en.ilike(pattern), Student.full_name_np.ilike(pattern),
                Student.admission_number.ilike(pattern), Student.emis_student_id.ilike(pattern)))
        if grade:
            if not grade.isdigit():
                return []
            query = query.where(Student.current_grade == int(grade))
        if section:
            query = query.where(Student.current_section == section)
        rows = (await self.db.execute(query.order_by(Student.full_name_en, Student.id).limit(limit))).mappings().all()
        return [{**dict(row), "id": str(row.id), "status": row.status.value} for row in rows]

    async def list_payments(self, school_id, academic_year_bs=None, student_id=None, search=None, page=1, limit=20, grade=None):
        conditions = [FeePayment.school_id == school_id, FeeLedger.school_id == school_id, Student.school_id == school_id]
        if academic_year_bs:
            conditions.append(FeeLedger.academic_year_bs == normalize_academic_year(academic_year_bs))
        if student_id:
            conditions.append(FeePayment.student_id == student_id)
        if grade:
            conditions.append(cast(Student.current_grade, String) == grade)
        if search:
            conditions.append(or_(FeePayment.receipt_number.ilike(f"%{search}%"), Student.full_name_en.ilike(f"%{search}%"), FeePayment.reference.ilike(f"%{search}%")))
        query = select(FeePayment, Student.full_name_en.label("student_name"),
            FeeLedger.fee_head_name, FeeLedger.academic_year_bs).join(FeeLedger, FeeLedger.id == FeePayment.ledger_id)
        query = query.join(Student, Student.id == FeePayment.student_id).where(*conditions)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = (await self.db.execute(query.order_by(FeePayment.created_at.desc(), FeePayment.id)
            .offset((page - 1) * limit).limit(limit))).all()
        return {"payments": [{**FeePaymentResponse.model_validate(row.FeePayment).model_dump(mode="json"),
            "student_name": row.student_name, "fee_head_name": row.fee_head_name,
            "academic_year_bs": row.academic_year_bs} for row in rows], "total": total, "page": page, "limit": limit}

    async def get_receipt(self, school_id, payment_id):
        payment = await self.db.scalar(select(FeePayment).where(FeePayment.school_id == school_id, FeePayment.id == payment_id)
            .options(selectinload(FeePayment.refunds)))
        if payment is None:
            raise RecordNotFoundError("FeePayment", str(payment_id))
        student = await self._student(school_id, payment.student_id)
        entry = await self.db.scalar(select(FeeLedger).where(FeeLedger.id == payment.ledger_id, FeeLedger.school_id == school_id, FeeLedger.student_id == payment.student_id))
        if entry is None:
            raise RecordNotFoundError("FeeLedger", str(payment.ledger_id))
        school = (await self.db.execute(select(Tenant.name_en, Tenant.phone, Tenant.email, Tenant.municipality, Tenant.district)
            .where(Tenant.id == school_id))).mappings().first()
        cashier = await self.db.scalar(select(User.full_name_en).where(User.id == payment.received_by))
        return {
            "payment": FeePaymentResponse.model_validate(payment).model_dump(mode="json"),
            "refunds": [FeeRefundResponse.model_validate(refund).model_dump(mode="json") for refund in sorted(payment.refunds, key=lambda refund: refund.created_at)],
            "school": dict(school) if school else {"name_en": "School", "phone": None, "email": None, "municipality": None, "district": None},
            "student_name": student.full_name_en, "admission_number": student.admission_number,
            "fee_head_name": entry.fee_head_name, "month_bs": entry.month_bs,
            "academic_year_bs": entry.academic_year_bs, "cashier_name": cashier,
        }

    async def list_scholarships(self, school_id, academic_year_bs=None, student_id=None, page=1, limit=20, grade=None):
        query = select(Scholarship, Student.full_name_en.label("student_name")).join(Student, Student.id == Scholarship.student_id)
        query = query.where(Scholarship.school_id == school_id, Student.school_id == school_id)
        if academic_year_bs:
            query = query.where(Scholarship.academic_year_bs == normalize_academic_year(academic_year_bs))
        if student_id:
            query = query.where(Scholarship.student_id == student_id)
        if grade:
            query = query.where(cast(Student.current_grade, String) == grade)
        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        rows = (await self.db.execute(query.order_by(Scholarship.created_at.desc(), Scholarship.id).offset((page - 1) * limit).limit(limit))).all()
        from services.fee.schemas.fee import ScholarshipResponse
        return {"scholarships": [{**ScholarshipResponse.model_validate(row.Scholarship).model_dump(mode="json"), "student_name": row.student_name} for row in rows], "total": total, "page": page, "limit": limit}

    async def get_outstanding_fees(self, school_id, grade=None, section=None, academic_year_bs=None, page=1, limit=20):
        conditions = [FeeLedger.school_id == school_id, Student.school_id == school_id]
        if academic_year_bs:
            conditions.append(FeeLedger.academic_year_bs == normalize_academic_year(academic_year_bs))
        if grade:
            conditions.append(cast(Student.current_grade, String) == grade)
        if section:
            conditions.append(Student.current_section == section)
        # Aggregate bills before pagination; payments are not joined here, so
        # partial payments cannot multiply the outstanding totals.
        grouped = select(Student.id.label("student_id"), Student.full_name_en.label("student_name"),
            Student.current_grade.label("grade"), Student.current_section.label("section"),
            func.sum(FeeLedger.amount_due).label("total_due"), func.sum(FeeLedger.amount_paid).label("total_paid"),
            func.sum(FeeLedger.balance).label("total_balance"),
            func.count().filter((FeeLedger.balance > ZERO) & (FeeLedger.due_date_ad < school_today())).label("overdue_count"),
        ).join(FeeLedger, FeeLedger.student_id == Student.id).where(*conditions).group_by(
            Student.id, Student.full_name_en, Student.current_grade, Student.current_section,
        ).having(func.sum(FeeLedger.balance) > ZERO).subquery()
        count, total = (await self.db.execute(select(func.count(), func.coalesce(func.sum(grouped.c.total_balance), ZERO)).select_from(grouped))).one()
        rows = (await self.db.execute(select(grouped).order_by(grouped.c.total_balance.desc(), grouped.c.student_id)
            .offset((page - 1) * limit).limit(limit))).mappings().all()
        return OutstandingFeesResponse(
            school_id=school_id, grade=grade, section=section,
            academic_year_bs=normalize_academic_year(academic_year_bs) if academic_year_bs else None,
            total_outstanding=total, student_count=count, page=page, limit=limit,
            students=[StudentOutstandingEntry(**row) for row in rows],
        )

    async def get_fee_collection_summary(self, school_id, academic_year_bs):
        year = normalize_academic_year(academic_year_bs)
        scope = (FeeLedger.school_id == school_id, FeeLedger.academic_year_bs == year)
        original, discount, due, paid, balance, overdue = (await self.db.execute(select(
            func.coalesce(func.sum(FeeLedger.original_amount), ZERO), func.coalesce(func.sum(FeeLedger.discount_amount), ZERO),
            func.coalesce(func.sum(FeeLedger.amount_due), ZERO), func.coalesce(func.sum(FeeLedger.amount_paid), ZERO),
            func.coalesce(func.sum(FeeLedger.balance), ZERO),
            func.coalesce(func.sum(FeeLedger.balance).filter(FeeLedger.due_date_ad < school_today()), ZERO),
        ).where(*scope))).one()
        gross, refunded = (await self.db.execute(select(func.coalesce(func.sum(FeePayment.amount), ZERO),
            func.coalesce(func.sum(FeePayment.refunded_amount), ZERO)).join(FeeLedger, FeeLedger.id == FeePayment.ledger_id)
            .where(FeePayment.school_id == school_id, *scope))).one()
        monthly = (await self.db.execute(select(FeeLedger.month_bs,
            func.sum(FeeLedger.amount_paid).label("collected"), func.sum(FeeLedger.balance).label("pending"))
            .where(*scope).group_by(FeeLedger.month_bs).order_by(FeeLedger.month_bs))).all()
        payment_counts = dict((await self.db.execute(select(FeeLedger.month_bs, func.count(FeePayment.id))
            .join(FeePayment, FeePayment.ledger_id == FeeLedger.id)
            .where(FeePayment.school_id == school_id, *scope).group_by(FeeLedger.month_bs))).all())
        return FeeCollectionSummaryResponse(
            school_id=school_id, academic_year_bs=year, total_original=original, total_discount=discount,
            total_due=due, gross_collected=gross, total_refunded=refunded, total_collected=paid,
            total_pending=balance, total_overdue=overdue,
            collection_rate=(paid / due * 100).quantize(CENT, rounding=ROUND_HALF_UP) if due else ZERO,
            monthly_breakdown=[MonthlyCollectionEntry(month_bs=row.month_bs or "annual", total_collected=row.collected,
                total_pending=row.pending, payment_count=payment_counts.get(row.month_bs, 0)) for row in monthly],
        )
