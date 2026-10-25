"""Fee setup, billing, collections, receipts, refunds and financial reports."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth.dependencies.auth import require_permission
from services.fee.schemas.fee import (
    FeeHeadCreate, FeeHeadResponse, FeePaymentRequest, FeePaymentResponse,
    FeeRefundRequest, FeeRefundResponse, FeeStructureCreate, FeeStructureResponse,
    FeeStructureUpdate, GenerateLedgerRequest, ScholarshipCreate, ScholarshipResponse,
    ScholarshipReversalRequest,
)
from services.fee.services.fee_service import FeeConflictError, FeeService
from services.student.services.student_service import StudentService
from shared.database.base import get_db
from shared.schemas.responses import error_response, success_response
from shared.utils.exceptions import RecordNotFoundError

router = APIRouter()


def fee_permission(permission):
    async def check(user=Depends(require_permission(permission))):
        if not user.school_id:
            raise HTTPException(403, detail=error_response("A school context is required", "SCHOOL_REQUIRED"))
        # Guardians have a legacy fee:read permission but no verified account-to-
        # student link. It must not grant access to a school's financial register.
        if (user.has_role("parent") or user.has_role("student")) and not any(
            user.has_permission(code) for code in ("fee:create", "fee:collect", "fee:report")
        ):
            raise HTTPException(403, detail=error_response("School fee administration requires an authorized staff account", "FEE_STAFF_REQUIRED"))
        return user
    return check


async def run(operation):
    try:
        return await operation
    except RecordNotFoundError as exc:
        raise HTTPException(404, detail=error_response(str(exc), "FEE_RECORD_NOT_FOUND")) from exc
    except FeeConflictError as exc:
        raise HTTPException(409, detail=error_response(str(exc), "FEE_CONFLICT")) from exc
    except ValueError as exc:
        raise HTTPException(400, detail=error_response(str(exc), "INVALID_FEE_REQUEST")) from exc
    except IntegrityError as exc:
        raise HTTPException(409, detail=error_response("This change conflicts with existing fee records. Refresh and review the current values.", "FEE_CONFLICT")) from exc


def response(data, schema=None):
    if schema:
        data = schema.model_validate(data).model_dump(mode="json")
    elif hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    return success_response(data=data)


@router.get("/structures")
async def list_structures(academic_year_bs: Optional[str] = None, grade: Optional[str] = None,
    is_active: Optional[bool] = True, db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:read"))):
    structures = await run(FeeService(db).get_fee_structures(user.school_id, academic_year_bs, grade, is_active))
    return response([FeeStructureResponse.model_validate(item).model_dump(mode="json") for item in structures])


@router.post("/structures", status_code=201)
async def create_structure(data: FeeStructureCreate, db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    return response(await run(FeeService(db).create_fee_structure(user.school_id, data)), FeeStructureResponse)


@router.patch("/structures/{structure_id}")
async def update_structure(structure_id: uuid.UUID, data: FeeStructureUpdate,
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    return response(await run(FeeService(db).update_fee_structure(user.school_id, structure_id, data)), FeeStructureResponse)


@router.post("/structures/{structure_id}/heads", status_code=201)
async def create_head(structure_id: uuid.UUID, data: FeeHeadCreate,
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    return response(await run(FeeService(db).add_fee_head(structure_id, data, user.school_id)), FeeHeadResponse)


@router.put("/structures/{structure_id}/heads/{head_id}")
async def update_head(structure_id: uuid.UUID, head_id: uuid.UUID, data: FeeHeadCreate,
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    return response(await run(FeeService(db).change_fee_head(user.school_id, structure_id, head_id, data)), FeeHeadResponse)


@router.delete("/structures/{structure_id}/heads/{head_id}")
async def delete_head(structure_id: uuid.UUID, head_id: uuid.UUID,
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    await run(FeeService(db).change_fee_head(user.school_id, structure_id, head_id))
    return response({"message": "Unbilled fee head removed"})


@router.post("/generate-ledger", status_code=201)
async def generate_ledger(data: GenerateLedgerRequest, db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    return response(await run(FeeService(db).generate_ledger_entries(user.school_id, data)))


@router.get("/roster")
async def class_roster(grade: int = Query(..., ge=1, le=12), section: Optional[str] = Query(None, max_length=10),
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:read"))):
    students = await run(StudentService(db).get_roster(user.school_id, grade, section))
    return response({"students": [{**row, "id": str(row["id"])} for row in students], "total": len(students)})


@router.get("/students")
async def search_students(search: Optional[str] = Query(None, max_length=100), grade: Optional[str] = Query(None, max_length=20),
    section: Optional[str] = Query(None, max_length=10), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:read"))):
    return response(await run(FeeService(db).search_students(user.school_id, search, grade, section, limit)))


@router.get("/student/{student_id}")
@router.get("/students/{student_id}/ledger", include_in_schema=False)
async def student_statement(student_id: uuid.UUID, academic_year_bs: Optional[str] = None,
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:read"))):
    return response(await run(FeeService(db).get_student_fee_status(user.school_id, student_id, academic_year_bs)))


@router.post("/collect", status_code=201)
async def collect(data: FeePaymentRequest, db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:collect"))):
    return response(await run(FeeService(db).collect_fee(user.school_id, data, user.id)), FeePaymentResponse)


@router.get("/payments")
async def payments(academic_year_bs: Optional[str] = None, student_id: Optional[uuid.UUID] = None,
    grade: Optional[str] = Query(None, max_length=20),
    search: Optional[str] = Query(None, max_length=100), page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:read"))):
    return response(await run(FeeService(db).list_payments(user.school_id, academic_year_bs, student_id, search, page, limit, grade)))


@router.get("/payments/{payment_id}/receipt")
async def receipt(payment_id: uuid.UUID, db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:read"))):
    return response(await run(FeeService(db).get_receipt(user.school_id, payment_id)))


@router.post("/payments/{payment_id}/refunds", status_code=201)
async def refund(payment_id: uuid.UUID, data: FeeRefundRequest,
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:refund"))):
    return response(await run(FeeService(db).refund_payment(user.school_id, payment_id, data, user.id)), FeeRefundResponse)


@router.get("/outstanding")
async def outstanding(grade: Optional[str] = Query(None, max_length=20), section: Optional[str] = Query(None, max_length=10),
    academic_year_bs: Optional[str] = None, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:report"))):
    return response(await run(FeeService(db).get_outstanding_fees(user.school_id, grade, section, academic_year_bs, page, limit)))


@router.get("/collection-summary")
async def summary(academic_year_bs: str, db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:report"))):
    return response(await run(FeeService(db).get_fee_collection_summary(user.school_id, academic_year_bs)))


@router.post("/scholarships", status_code=201)
async def award(data: ScholarshipCreate, db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    return response(await run(FeeService(db).apply_scholarship(user.school_id, data, user.id)), ScholarshipResponse)


@router.get("/scholarships")
async def scholarships(academic_year_bs: Optional[str] = None, student_id: Optional[uuid.UUID] = None,
    grade: Optional[str] = Query(None, max_length=20),
    page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:read"))):
    return response(await run(FeeService(db).list_scholarships(user.school_id, academic_year_bs, student_id, page, limit, grade)))


@router.post("/scholarships/{scholarship_id}/reverse")
async def reverse_award(scholarship_id: uuid.UUID, data: ScholarshipReversalRequest,
    db: AsyncSession = Depends(get_db), user=Depends(fee_permission("fee:create"))):
    return response(await run(FeeService(db).reverse_scholarship(user.school_id, scholarship_id, data.reason, user.id)), ScholarshipResponse)
