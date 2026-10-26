"""School report previews, snapshots, exports and reasoned archive actions."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from services.auth.dependencies.auth import require_permission
from services.report.schemas.report import (
    ReportRequest,
    ReportGenerateRequest,
    ReportArchiveRequest,
)
from services.report.services.report_service import ReportService, ReportConflict
from services.student.models.student import Student
from services.exam.models.exam import Exam
from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError

router = APIRouter()


def access(permission="report:read"):
    async def check(user=Depends(require_permission(permission))):
        if (
            not user.school_id
            or not user.has_permission("report:read")
            or user.has_role("parent")
            or user.has_role("student")
        ):
            raise HTTPException(
                403,
                detail=error_response(
                    "Reports require an authorized school staff account",
                    "REPORT_STAFF_REQUIRED",
                ),
            )
        return user

    return check


def private(response):
    response.headers["Cache-Control"] = "no-store, private"


async def run(operation):
    try:
        return await operation
    except RecordNotFoundError as exc:
        raise HTTPException(
            404, detail=error_response(str(exc), "REPORT_NOT_FOUND")
        ) from exc
    except (ReportConflict, IntegrityError) as exc:
        raise HTTPException(
            409,
            detail=error_response(
                str(exc)
                if isinstance(exc, ReportConflict)
                else "Report action conflicts with another request. Refresh and retry.",
                "REPORT_CONFLICT",
            ),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            400, detail=error_response(str(exc), "INVALID_REPORT")
        ) from exc


@router.get("/catalog")
async def catalog(
    response: Response, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    private(response)
    return success_response(data=ReportService(db).catalog(user))


@router.post("/preview")
async def preview(
    data: ReportRequest,
    response: Response,
    page: int = Query(1, ge=1, le=10000),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return success_response(data=await run(ReportService(db).preview(user, data, page)))


@router.post("/generate", status_code=201)
async def generate(
    data: ReportGenerateRequest,
    response: Response,
    user=Depends(access("report:generate")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return success_response(
        data=await run(ReportService(db).generate_report(user, data))
    )


@router.get("/students")
async def students(
    response: Response,
    search: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    if not user.has_permission("student:read"):
        raise HTTPException(403, "Student report permission is required")
    private(response)
    query = select(
        Student.id,
        Student.full_name_en,
        Student.admission_number,
        Student.current_grade,
    ).where(
        Student.school_id == user.school_id,
        Student.deleted_at.is_(None),
        Student.is_deleted.is_(False),
    )
    if search:
        query = query.where(
            or_(
                Student.full_name_en.ilike(f"%{search}%"),
                Student.full_name_np.ilike(f"%{search}%"),
                Student.admission_number.ilike(f"%{search}%"),
                Student.emis_student_id.ilike(f"%{search}%"),
            )
        )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        (
            await db.execute(
                query.order_by(Student.full_name_en, Student.id)
                .offset((page - 1) * 20)
                .limit(20)
            )
        )
        .mappings()
        .all()
    )
    return success_response(
        data={"items": [{**row, "id": str(row["id"])} for row in rows], "total": total}
    )


@router.get("/exams")
async def exams(
    response: Response,
    search: str = Query("", max_length=100),
    page: int = Query(1, ge=1),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    if not user.has_permission("exam:read") or not user.has_permission("marks:read"):
        raise HTTPException(403, "Exam and marks report permissions are required")
    private(response)
    query = select(
        Exam.id, Exam.name, Exam.grade, Exam.academic_year_bs, Exam.status
    ).where(Exam.school_id == user.school_id, Exam.deleted_at.is_(None))
    if search:
        query = query.where(Exam.name.ilike(f"%{search}%"))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (
        (
            await db.execute(
                query.order_by(Exam.created_at.desc(), Exam.id)
                .offset((page - 1) * 20)
                .limit(20)
            )
        )
        .mappings()
        .all()
    )
    return success_response(
        data={
            "items": [
                {**row, "id": str(row["id"]), "status": row["status"].value}
                for row in rows
            ],
            "total": total,
        }
    )


@router.get("")
@router.get("/", include_in_schema=False)
async def history(
    response: Response,
    page: int = Query(1, ge=1),
    report_type: str | None = Query(None, max_length=40),
    archived: bool = False,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return success_response(
        data=await run(
            ReportService(db).list_reports(user, page, report_type, archived)
        )
    )


@router.get("/{report_id}")
async def detail(
    report_id: UUID,
    response: Response,
    page: int = Query(1, ge=1),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return success_response(
        data=await run(ReportService(db).detail(user, report_id, page))
    )


@router.get("/{report_id}/print")
async def print_report(
    report_id: UUID,
    response: Response,
    user=Depends(access("report:export")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    service = ReportService(db)
    report, rows = await run(service.full_snapshot(user, report_id, True))
    service.event(user, report, "print_view")
    await db.flush()
    return success_response(data={**service.metadata(report), "rows": rows})


@router.get("/{report_id}/download")
async def download(
    report_id: UUID,
    format: str | None = Query(None, max_length=10),
    user=Depends(access("report:export")),
    db: AsyncSession = Depends(get_db),
):
    content, extension = await run(ReportService(db).download(user, report_id, format))
    return Response(
        content,
        media_type="text/csv; charset=utf-8"
        if extension == "csv"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Cache-Control": "no-store, private",
            "Content-Disposition": f'attachment; filename="school-report-{report_id}.{extension}"',
        },
    )


@router.post("/{report_id}/archive")
@router.delete("/{report_id}", include_in_schema=False)
async def archive(
    report_id: UUID,
    data: ReportArchiveRequest,
    response: Response,
    user=Depends(access("report:delete")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return success_response(
        data=await run(ReportService(db).archive(user, report_id, data))
    )
