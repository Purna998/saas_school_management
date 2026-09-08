"""
Nepal School Management System - Exam API Routes
Exam management, marks entry, results, and report card endpoints
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError
from services.auth.dependencies.auth import (
    get_current_active_user,
    require_permission,
)
from services.auth.models.user import User
from services.exam.schemas.exam import (
    ExamCreate,
    ExamStatusUpdate,
    ExamResponse,
    ExamListResponse,
    ExamSubjectResponse,
    MarkEntryRequest,
    MarkResponse,
    MarkListResponse,
    ResultResponse,
    ResultListResponse,
    ReportCardResponse,
    SubjectResult,
)
from services.exam.services.exam_service import ExamService

router = APIRouter()


# ============================================================
# Helpers
# ============================================================

def _exam_to_response(exam) -> ExamResponse:
    """Convert exam model to response schema"""
    return ExamResponse(
        id=exam.id,
        school_id=exam.school_id,
        name=exam.name,
        exam_type=exam.exam_type.value,
        academic_year_bs=exam.academic_year_bs,
        grade=exam.grade,
        start_date_ad=exam.start_date_ad,
        end_date_ad=exam.end_date_ad,
        status=exam.status.value,
        is_locked=exam.is_locked,
        subjects=[
            ExamSubjectResponse(
                id=s.id,
                exam_id=s.exam_id,
                subject_id=s.subject_id,
                full_marks=s.full_marks,
                pass_marks=s.pass_marks,
                exam_date_ad=s.exam_date_ad,
                start_time=s.start_time,
                end_time=s.end_time,
            )
            for s in (exam.subjects or [])
        ],
        created_at=exam.created_at,
        updated_at=exam.updated_at,
    )


def _mark_to_response(mark) -> MarkResponse:
    """Convert mark model to response schema"""
    return MarkResponse(
        id=mark.id,
        exam_id=mark.exam_id,
        exam_subject_id=mark.exam_subject_id,
        student_id=mark.student_id,
        marks_obtained=mark.marks_obtained,
        grade_point=mark.grade_point,
        remarks=mark.remarks,
        entered_by=mark.entered_by,
        created_at=mark.created_at,
    )


def _result_to_response(result) -> ResultResponse:
    """Convert result model to response schema"""
    return ResultResponse(
        id=result.id,
        exam_id=result.exam_id,
        student_id=result.student_id,
        total_marks=result.total_marks,
        percentage=result.percentage,
        gpa=result.gpa,
        division=result.division.value if result.division else None,
        rank=result.rank,
        status=result.status.value,
        created_at=result.created_at,
    )


# ============================================================
# Exam Endpoints
# ============================================================

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_data: ExamCreate,
    current_user: User = Depends(require_permission("exam:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new exam with subject configurations.

    Requires: exam:create permission

    Status Codes:
        - 201: Exam created
        - 400: Validation error
    """
    try:
        service = ExamService(db)
        exam = await service.create_exam(
            data=exam_data,
            school_id=current_user.school_id,
        )
        return success_response(data=_exam_to_response(exam).model_dump(mode="json"))

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "VALIDATION_ERROR"),
        )


@router.get("/")
async def list_exams(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    grade: Optional[int] = Query(default=None, ge=1, le=12),
    academic_year_bs: Optional[str] = Query(default=None),
    exam_type: Optional[str] = Query(default=None),
    exam_status: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(require_permission("exam:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    List exams with pagination and filters.

    Requires: exam:read permission

    Query Parameters:
        - grade: Filter by grade (1-12)
        - academic_year_bs: Filter by academic year
        - exam_type: Filter by type (terminal/unit_test/final/pre_board/send_up)
        - status: Filter by status (draft/scheduled/ongoing/completed/published)

    Status Codes:
        - 200: Success
    """
    service = ExamService(db)
    exams, total = await service.list_exams(
        school_id=current_user.school_id,
        page=page,
        limit=limit,
        grade=grade,
        academic_year_bs=academic_year_bs,
        exam_type=exam_type,
        status_filter=exam_status,
    )

    return success_response(
        data=ExamListResponse(
            exams=[_exam_to_response(e) for e in exams],
            total=total,
            page=page,
            limit=limit,
        ).model_dump(mode="json")
    )


@router.get("/{exam_id}")
async def get_exam(
    exam_id: uuid.UUID,
    current_user: User = Depends(require_permission("exam:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get exam details by ID.

    Requires: exam:read permission

    Status Codes:
        - 200: Success
        - 404: Exam not found
    """
    try:
        service = ExamService(db)
        exam = await service.get_exam(exam_id, current_user.school_id)
        return success_response(data=_exam_to_response(exam).model_dump(mode="json"))

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "EXAM_NOT_FOUND"),
        )


@router.patch("/{exam_id}/status")
async def update_exam_status(
    exam_id: uuid.UUID,
    status_data: ExamStatusUpdate,
    current_user: User = Depends(require_permission("exam:update")),
    db: AsyncSession = Depends(get_db),
):
    """
    Update exam status.

    Valid transitions: draft->scheduled->ongoing->completed->published

    Requires: exam:update permission

    Status Codes:
        - 200: Status updated
        - 400: Invalid status transition
        - 404: Exam not found
    """
    try:
        service = ExamService(db)
        exam = await service.update_exam_status(exam_id, status_data, current_user.school_id)
        return success_response(data=_exam_to_response(exam).model_dump(mode="json"))

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "EXAM_NOT_FOUND"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_STATUS_TRANSITION"),
        )


# ============================================================
# Marks Endpoints
# ============================================================

@router.post("/marks")
async def enter_marks(
    mark_data: MarkEntryRequest,
    current_user: User = Depends(require_permission("exam:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch enter marks for students in a subject.

    Supports upsert - existing marks will be updated.
    Automatically calculates grade points for GPA system (grades 1-10).

    Requires: exam:create permission

    Status Codes:
        - 200: Marks entered successfully
        - 400: Validation error (marks exceed full marks, exam locked)
        - 404: Exam subject not found
    """
    try:
        service = ExamService(db)
        marks = await service.enter_marks(
            data=mark_data,
            school_id=current_user.school_id,
            entered_by=current_user.id,
        )
        return success_response(
            data={
                "message": f"Successfully entered marks for {len(marks)} students",
                "marks": [_mark_to_response(m).model_dump(mode="json") for m in marks],
                "total": len(marks),
            }
        )

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "EXAM_SUBJECT_NOT_FOUND"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "VALIDATION_ERROR"),
        )


# ============================================================
# Results Endpoints
# ============================================================

@router.get("/{exam_id}/results")
async def get_results(
    exam_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    result_status: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(require_permission("exam:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get results for an exam.

    Requires: exam:read permission

    Query Parameters:
        - status: Filter by result status (pass/fail/absent)

    Status Codes:
        - 200: Success
        - 404: Exam not found
    """
    try:
        service = ExamService(db)
        exam = await service.get_exam(exam_id, current_user.school_id)
        results, total = await service.get_results(
            exam_id=exam_id,
            school_id=current_user.school_id,
            page=page,
            limit=limit,
            status_filter=result_status,
        )

        return success_response(
            data=ResultListResponse(
                exam_id=exam_id,
                exam_name=exam.name,
                grade=exam.grade,
                results=[_result_to_response(r) for r in results],
                total=total,
            ).model_dump(mode="json")
        )

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "EXAM_NOT_FOUND"),
        )


@router.post("/{exam_id}/calculate")
async def calculate_results(
    exam_id: uuid.UUID,
    current_user: User = Depends(require_permission("exam:create")),
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate results for all students in an exam.

    Grading:
    - Grades 1-10: GPA system (4.0 scale)
    - Grades 11-12: Percentage with division (First/Second/Third/Fail)

    Requires: exam:create permission

    Status Codes:
        - 200: Results calculated
        - 400: No marks entered or exam is locked
        - 404: Exam not found
    """
    try:
        service = ExamService(db)
        results = await service.calculate_results(exam_id, current_user.school_id)

        exam = await service.get_exam(exam_id, current_user.school_id)
        return success_response(
            data={
                "message": f"Results calculated for {len(results)} students",
                "exam_id": str(exam_id),
                "exam_name": exam.name,
                "grade": exam.grade,
                "grading_system": "percentage" if exam.grade >= 11 else "gpa",
                "total_students": len(results),
                "passed": sum(1 for r in results if r.status == "pass"),
                "failed": sum(1 for r in results if r.status == "fail"),
                "absent": sum(1 for r in results if r.status == "absent"),
            }
        )

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "EXAM_NOT_FOUND"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "CALCULATION_ERROR"),
        )


@router.post("/{exam_id}/publish")
async def publish_results(
    exam_id: uuid.UUID,
    current_user: User = Depends(require_permission("exam:publish")),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish exam results - locks marks and makes results visible.

    Prerequisites:
    - Exam must be in 'completed' status
    - Results must be calculated first

    Requires: exam:publish permission

    Status Codes:
        - 200: Results published
        - 400: Cannot publish (wrong status or no results)
        - 404: Exam not found
    """
    try:
        service = ExamService(db)
        exam = await service.publish_results(exam_id, current_user.school_id)
        return success_response(
            data={
                "message": f"Results published for exam: {exam.name}",
                "exam": _exam_to_response(exam).model_dump(mode="json"),
            }
        )

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "EXAM_NOT_FOUND"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "PUBLISH_ERROR"),
        )


# ============================================================
# Report Card Endpoint
# ============================================================

@router.get("/report-card/{student_id}")
async def get_report_card(
    student_id: uuid.UUID,
    exam_id: uuid.UUID = Query(..., description="Exam ID for the report card"),
    current_user: User = Depends(require_permission("exam:read")),
    db: AsyncSession = Depends(get_db),
):
    """
    Get student report card for a specific exam.

    Returns complete subject-wise marks, GPA/percentage, division, and rank.

    Requires: exam:read permission

    Status Codes:
        - 200: Report card generated
        - 404: Student result not found
    """
    try:
        service = ExamService(db)
        report = await service.get_report_card(student_id, exam_id, current_user.school_id)

        return success_response(
            data=ReportCardResponse(
                student_id=report["student_id"],
                student_name=report["student_name"],
                exam_id=report["exam_id"],
                exam_name=report["exam_name"],
                exam_type=report["exam_type"],
                academic_year_bs=report["academic_year_bs"],
                grade=report["grade"],
                subjects=[
                    SubjectResult(
                        subject_id=s["subject_id"],
                        subject_name=s["subject_name"],
                        full_marks=s["full_marks"],
                        pass_marks=s["pass_marks"],
                        marks_obtained=s["marks_obtained"],
                        grade_point=s["grade_point"],
                        remarks=s["remarks"],
                    )
                    for s in report["subjects"]
                ],
                total_marks=report["total_marks"],
                full_marks_total=report["full_marks_total"],
                percentage=report["percentage"],
                gpa=report["gpa"],
                division=report["division"],
                rank=report["rank"],
                status=report["status"],
                grading_system=report["grading_system"],
            ).model_dump(mode="json")
        )

    except RecordNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "RESULT_NOT_FOUND"),
        )
