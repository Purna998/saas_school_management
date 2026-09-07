"""
Nepal School Management System - Fee Service API Endpoints
REST API routes for fee management
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from services.auth.dependencies.auth import get_current_active_user, require_permission
from services.fee.services.fee_service import FeeService
from services.fee.schemas.fee import (
    FeeStructureCreate,
    FeeStructureResponse,
    FeeHeadCreate,
    FeeHeadResponse,
    FeePaymentRequest,
    FeePaymentResponse,
    GenerateLedgerRequest,
    ScholarshipCreate,
    ScholarshipResponse,
)
from shared.utils.exceptions import RecordNotFoundError, DuplicateRecordError


router = APIRouter()


# ─── Fee Structure Endpoints ─────────────────────────────────────────────────


@router.post(
    "/structures",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fee:create"))],
)
async def create_fee_structure(
    data: FeeStructureCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Create a new fee structure for a grade and academic year.

    Requires permission: fee:create
    """
    try:
        service = FeeService(db)
        fee_structure = await service.create_fee_structure(
            school_id=current_user.school_id,
            data=data,
        )
        return success_response(
            data=FeeStructureResponse.model_validate(fee_structure).model_dump(mode="json")
        )
    except DuplicateRecordError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(
                message=str(e),
                code="DUPLICATE_FEE_STRUCTURE",
            ),
        )


@router.get("/structures")
async def list_fee_structures(
    academic_year_bs: Optional[str] = Query(default=None, description="Filter by academic year"),
    grade: Optional[str] = Query(default=None, description="Filter by grade"),
    is_active: Optional[bool] = Query(default=True, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    List fee structures with optional filters.

    Returns all fee structures for the current school.
    """
    service = FeeService(db)
    structures = await service.get_fee_structures(
        school_id=current_user.school_id,
        academic_year_bs=academic_year_bs,
        grade=grade,
        is_active=is_active,
    )
    return success_response(
        data=[
            FeeStructureResponse.model_validate(s).model_dump(mode="json")
            for s in structures
        ]
    )


@router.post(
    "/structures/{structure_id}/heads",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fee:create"))],
)
async def add_fee_head(
    structure_id: uuid.UUID,
    data: FeeHeadCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Add a fee head to an existing fee structure.

    Requires permission: fee:create
    """
    try:
        service = FeeService(db)
        fee_head = await service.add_fee_head(
            fee_structure_id=structure_id,
            data=data,
        )
        return success_response(
            data=FeeHeadResponse.model_validate(fee_head).model_dump(mode="json")
        )
    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                message=str(e),
                code="FEE_STRUCTURE_NOT_FOUND",
            ),
        )


# ─── Ledger Generation ───────────────────────────────────────────────────────


@router.post(
    "/generate-ledger",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fee:create"))],
)
async def generate_ledger(
    data: GenerateLedgerRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Generate fee ledger entries for students in a grade.

    Based on the active fee structure, creates due entries for each student.
    Skips entries that already exist (idempotent).

    Requires permission: fee:create
    """
    try:
        service = FeeService(db)
        entries = await service.generate_ledger_entries(
            school_id=current_user.school_id,
            data=data,
        )
        return success_response(
            data={
                "entries_created": len(entries),
                "academic_year_bs": data.academic_year_bs,
                "grade": data.grade,
                "student_count": len(data.student_ids),
            }
        )
    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                message=str(e),
                code="FEE_STRUCTURE_NOT_FOUND",
            ),
        )


# ─── Fee Collection ──────────────────────────────────────────────────────────


@router.post(
    "/collect",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fee:collect"))],
)
async def collect_fee(
    data: FeePaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Record a fee payment from a student.

    Finds the earliest pending ledger entry for the given fee head,
    records the payment, updates the balance, and generates a receipt.

    Requires permission: fee:collect
    """
    try:
        service = FeeService(db)
        payment = await service.collect_fee(
            school_id=current_user.school_id,
            data=data,
            received_by=current_user.id,
        )
        return success_response(
            data=FeePaymentResponse.model_validate(payment).model_dump(mode="json")
        )
    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(
                message=str(e),
                code="LEDGER_ENTRY_NOT_FOUND",
            ),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message=str(e),
                code="INVALID_PAYMENT_AMOUNT",
            ),
        )


# ─── Student Fee Status ──────────────────────────────────────────────────────


@router.get("/student/{student_id}")
async def get_student_fee_status(
    student_id: uuid.UUID,
    academic_year_bs: Optional[str] = Query(default=None, description="Filter by academic year"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get complete fee status for a student.

    Returns all ledger entries, payments, and totals.
    """
    service = FeeService(db)
    status_response = await service.get_student_fee_status(
        school_id=current_user.school_id,
        student_id=student_id,
        academic_year_bs=academic_year_bs,
    )
    return success_response(data=status_response.model_dump(mode="json"))


# ─── Outstanding Fees Report ─────────────────────────────────────────────────


@router.get("/outstanding")
async def get_outstanding_fees(
    grade: Optional[str] = Query(default=None, description="Filter by grade"),
    section: Optional[str] = Query(default=None, description="Filter by section"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get outstanding fees report.

    Returns list of students with unpaid/overdue fees, with totals.
    """
    service = FeeService(db)
    report = await service.get_outstanding_fees(
        school_id=current_user.school_id,
        grade=grade,
        section=section,
    )
    return success_response(data=report.model_dump(mode="json"))


# ─── Fee Collection Summary ──────────────────────────────────────────────────


@router.get("/collection-summary")
async def get_fee_collection_summary(
    academic_year_bs: str = Query(..., description="Academic year in BS"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Get fee collection summary for an academic year.

    Returns total collected, pending, overdue, collection rate, and monthly breakdown.
    """
    service = FeeService(db)
    summary = await service.get_fee_collection_summary(
        school_id=current_user.school_id,
        academic_year_bs=academic_year_bs,
    )
    return success_response(data=summary.model_dump(mode="json"))


# ─── Scholarship ─────────────────────────────────────────────────────────────


@router.post(
    "/scholarships",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission("fee:create"))],
)
async def apply_scholarship(
    data: ScholarshipCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Apply a scholarship/discount to a student.

    Creates the scholarship record and adjusts pending ledger entries
    by reducing the outstanding amounts.

    Requires permission: fee:create
    """
    try:
        service = FeeService(db)
        scholarship = await service.apply_scholarship(
            school_id=current_user.school_id,
            data=data,
        )
        return success_response(
            data=ScholarshipResponse.model_validate(scholarship).model_dump(mode="json")
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                message=str(e),
                code="INVALID_SCHOLARSHIP",
            ),
        )
