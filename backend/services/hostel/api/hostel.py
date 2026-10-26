"""Authorized boarding-office routes; all records remain school scoped."""

from datetime import date
from typing import Literal, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from services.auth.dependencies.auth import require_permission
from services.hostel.models.hostel import Hostel, RoomAllocation, HostelLeave
from services.hostel.schemas.hostel import (
    HostelCreate,
    HostelUpdate,
    RoomCreate,
    RoomUpdate,
    AddBedsRequest,
    BedUpdate,
    AllocateRequest,
    TransferRequest,
    ReasonCommand,
    Command,
    LeaveRequest,
    VisitRequest,
    RegisterRequest,
    BillRequest,
    Session,
)
from services.hostel.services.hostel_service import HostelService, HostelConflict, today
from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError

router = APIRouter()


def access(permission="hostel:read"):
    async def check(user=Depends(require_permission(permission))):
        if not user.school_id or not user.has_permission("hostel:read"):
            raise HTTPException(
                403,
                detail=error_response(
                    "Hostel access requires an authorized school account",
                    "HOSTEL_SCHOOL_REQUIRED",
                ),
            )
        if (user.has_role("parent") or user.has_role("student")) and not any(
            user.has_permission(code) for code in ("hostel:create", "hostel:allocate")
        ):
            raise HTTPException(
                403,
                detail=error_response(
                    "Residential records require an authorized hostel staff account",
                    "HOSTEL_STAFF_REQUIRED",
                ),
            )
        return user

    return check


async def run(operation):
    try:
        return await operation
    except RecordNotFoundError as exc:
        raise HTTPException(
            404, detail=error_response(str(exc), "HOSTEL_NOT_FOUND")
        ) from exc
    except HostelConflict as exc:
        raise HTTPException(
            409, detail=error_response(str(exc), "HOSTEL_CONFLICT")
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            400, detail=error_response(str(exc), "INVALID_HOSTEL_REQUEST")
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            409,
            detail=error_response(
                "This hostel name, room, bed or active stay conflicts with an existing record. Refresh and review the selection.",
                "HOSTEL_CONFLICT",
            ),
        ) from exc


def result(data):
    return success_response(data=data)


async def command(db, user, action, data, resource=None):
    return result(
        await run(
            HostelService(db).command(
                action, user.school_id, data, user.id, user.full_name_en, resource
            )
        )
    )


@router.get("/hostels")
async def hostels(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, max_length=200),
    is_active: bool = True,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            HostelService(db).list_hostels(user.school_id, page, search, is_active)
        )
    )


@router.post("/hostels", status_code=201)
async def create_hostel(
    data: HostelCreate,
    user=Depends(access("hostel:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "create_hostel", data)


@router.get("/hostels/{hostel_id}")
async def hostel(
    hostel_id: UUID, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    service = HostelService(db)
    return result(
        service.hostel_response(
            await run(service.get(Hostel, user.school_id, hostel_id))
        )
    )


@router.patch("/hostels/{hostel_id}")
async def update_hostel(
    hostel_id: UUID,
    data: HostelUpdate,
    user=Depends(access("hostel:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "update_hostel", data, hostel_id)


@router.get("/rooms")
async def rooms(
    page: int = Query(1, ge=1),
    hostel_id: Optional[UUID] = None,
    search: Optional[str] = Query(None, max_length=200),
    is_active: bool = True,
    available_only: bool = False,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            HostelService(db).list_rooms(
                user.school_id,
                page,
                hostel_id=hostel_id,
                search=search,
                is_active=is_active,
                available_only=available_only,
            )
        )
    )


@router.post("/rooms", status_code=201)
async def create_room(
    data: RoomCreate,
    user=Depends(access("hostel:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "create_room", data)


@router.patch("/rooms/{room_id}")
async def update_room(
    room_id: UUID,
    data: RoomUpdate,
    user=Depends(access("hostel:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "update_room", data, room_id)


@router.get("/rooms/{room_id}/beds")
async def beds(
    room_id: UUID,
    page: int = Query(1, ge=1),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(await run(HostelService(db).beds(user.school_id, room_id, page)))


@router.post("/rooms/{room_id}/beds", status_code=201)
async def add_beds(
    room_id: UUID,
    data: AddBedsRequest,
    user=Depends(access("hostel:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "add_beds", data, room_id)


@router.patch("/beds/{bed_id}")
async def update_bed(
    bed_id: UUID,
    data: BedUpdate,
    user=Depends(access("hostel:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "update_bed", data, bed_id)


@router.get("/students")
async def students(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, max_length=200),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(await run(HostelService(db).students(user.school_id, search, page)))


@router.get("/allocations")
async def allocations(
    page: int = Query(1, ge=1),
    hostel_id: Optional[UUID] = None,
    room_id: Optional[UUID] = None,
    status: Optional[Literal["active", "vacated"]] = "active",
    search: Optional[str] = Query(None, max_length=200),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            HostelService(db).residents(
                user.school_id,
                page,
                hostel_id=hostel_id,
                room_id=room_id,
                status=status,
                search=search,
            )
        )
    )


@router.get("/allocations/{allocation_id}")
async def allocation(
    allocation_id: UUID, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    service = HostelService(db)
    stay = await run(service.get(RoomAllocation, user.school_id, allocation_id))
    leave = await db.scalar(
        select(HostelLeave).where(
            HostelLeave.school_id == user.school_id,
            HostelLeave.allocation_id == stay.id,
            HostelLeave.returned_at.is_(None),
        )
    )
    return result(service.stay_response(stay, leave))


@router.post("/allocate", status_code=201)
async def allocate(
    data: AllocateRequest,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "allocate", data)


@router.post("/vacate/{allocation_id}")
async def vacate(
    allocation_id: UUID,
    data: ReasonCommand,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "vacate", data, allocation_id)


@router.post("/allocations/{allocation_id}/transfer", status_code=201)
async def transfer(
    allocation_id: UUID,
    data: TransferRequest,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "transfer", data, allocation_id)


@router.get("/leaves")
async def leaves(
    page: int = Query(1, ge=1),
    hostel_id: Optional[UUID] = None,
    allocation_id: Optional[UUID] = None,
    search: Optional[str] = Query(None, max_length=200),
    status: Literal["open", "closed", "all"] = "open",
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            HostelService(db).movements(
                user.school_id, "leaves", page, hostel_id, search, status, allocation_id
            )
        )
    )


@router.post("/allocations/{allocation_id}/leave", status_code=201)
async def leave(
    allocation_id: UUID,
    data: LeaveRequest,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "leave", data, allocation_id)


@router.post("/leaves/{leave_id}/return")
async def return_leave(
    leave_id: UUID,
    data: ReasonCommand,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "return_leave", data, leave_id)


@router.get("/visits")
async def visits(
    page: int = Query(1, ge=1),
    hostel_id: Optional[UUID] = None,
    allocation_id: Optional[UUID] = None,
    search: Optional[str] = Query(None, max_length=200),
    status: Literal["open", "closed", "all"] = "open",
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            HostelService(db).movements(
                user.school_id, "visits", page, hostel_id, search, status, allocation_id
            )
        )
    )


@router.post("/visits", status_code=201)
async def visit(
    data: VisitRequest,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "visit", data)


@router.post("/visits/{visit_id}/depart")
async def depart(
    visit_id: UUID,
    data: Command,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "depart_visit", data, visit_id)


@router.get("/register")
async def register(
    date_ad: Optional[date] = None,
    session: Session = "evening",
    page: int = Query(1, ge=1),
    hostel_id: Optional[UUID] = None,
    search: Optional[str] = Query(None, max_length=200),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            HostelService(db).register(
                user.school_id, date_ad or today(), session, page, hostel_id, search
            )
        )
    )


@router.post("/register")
async def save_register(
    data: RegisterRequest,
    user=Depends(access("hostel:allocate")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "save_register", data)


@router.get("/allocations/{allocation_id}/fee-options")
async def fee_options(
    allocation_id: UUID,
    month_bs: str = Query(..., pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    user=Depends(access("fee:create")),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            HostelService(db).fee_options(user.school_id, allocation_id, month_bs)
        )
    )


@router.post("/allocations/{allocation_id}/bill", status_code=201)
async def bill(
    allocation_id: UUID,
    data: BillRequest,
    user=Depends(access("fee:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "bill", data, allocation_id)


@router.get("/occupancy")
async def occupancy(
    hostel_id: Optional[UUID] = None,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(await run(HostelService(db).occupancy(user.school_id, hostel_id)))


@router.get("/history")
async def history(
    page: int = Query(1, ge=1),
    allocation_id: Optional[UUID] = None,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(HostelService(db).history(user.school_id, page, allocation_id))
    )


@router.get("/export")
async def export(
    report: Literal["residents", "register"],
    hostel_id: Optional[UUID] = None,
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[Literal["active", "vacated"]] = None,
    date_ad: Optional[date] = None,
    session: Session = "evening",
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    data = await run(
        HostelService(db).export(
            user.school_id, report, hostel_id, search, status, date_ad, session
        )
    )
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="hostel-{report}-{today()}.csv"'
        },
    )
