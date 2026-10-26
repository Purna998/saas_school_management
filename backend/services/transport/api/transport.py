"""School-scoped transport office, dispatch, boarding and financial handoff."""

from datetime import date
from typing import Literal, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from services.auth.dependencies.auth import require_permission
from services.transport.models.transport import Vehicle, StudentTransport, TransportRun
from services.transport.schemas.transport import (
    VehicleCreate,
    VehicleUpdate,
    RouteCreate,
    RouteUpdate,
    StopCreate,
    StopUpdate,
    ReorderStops,
    RunCreate,
    RunUpdate,
    QuoteRequest,
    StudentTransportAssign,
    ReasonCommand,
    StartTrip,
    PassengerUpdate,
    CompleteTrip,
    MaintenanceRequest,
    PositionRequest,
    BillRequest,
    Direction,
)
from services.transport.services.transport_service import (
    TransportService,
    TransportConflict,
    today,
    fields,
)
from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError

router = APIRouter()


def access(permission="transport:read"):
    async def check(user=Depends(require_permission(permission))):
        if not user.school_id or not user.has_permission("transport:read"):
            raise HTTPException(
                403,
                detail=error_response(
                    "Transport access requires an authorized school account",
                    "TRANSPORT_SCHOOL_REQUIRED",
                ),
            )
        if (user.has_role("parent") or user.has_role("student")) and not any(
            user.has_permission(code)
            for code in ("transport:create", "transport:delete")
        ):
            raise HTTPException(
                403,
                detail=error_response(
                    "Student transport and vehicle locations require an authorized transport staff account",
                    "TRANSPORT_STAFF_REQUIRED",
                ),
            )
        return user

    return check


async def run(operation):
    try:
        return await operation
    except RecordNotFoundError as exc:
        raise HTTPException(
            404, detail=error_response(str(exc), "TRANSPORT_NOT_FOUND")
        ) from exc
    except TransportConflict as exc:
        raise HTTPException(
            409, detail=error_response(str(exc), "TRANSPORT_CONFLICT")
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            400, detail=error_response(str(exc), "INVALID_TRANSPORT_REQUEST")
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            409,
            detail=error_response(
                "This vehicle, route, run, student assignment or trip conflicts with an existing record. Refresh and review the selection.",
                "TRANSPORT_CONFLICT",
            ),
        ) from exc


def result(data):
    return success_response(data=data)


async def command(db, user, action, data, resource=None):
    return result(
        await run(
            TransportService(db).command(
                action, user.school_id, data, user.id, user.full_name_en, resource
            )
        )
    )


@router.get("/vehicles")
async def vehicles(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, max_length=200),
    is_active: bool = True,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            TransportService(db).vehicles(user.school_id, page, search, is_active)
        )
    )


@router.get("/vehicles/{vehicle_id}")
async def vehicle(
    vehicle_id: UUID, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    service = TransportService(db)
    return result(
        service.vehicle_response(
            await run(service.get(Vehicle, user.school_id, vehicle_id))
        )
    )


@router.post("/vehicles", status_code=201)
async def create_vehicle(
    data: VehicleCreate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "create_vehicle", data)


@router.patch("/vehicles/{vehicle_id}")
async def update_vehicle(
    vehicle_id: UUID,
    data: VehicleUpdate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "update_vehicle", data, vehicle_id)


@router.get("/vehicles/{vehicle_id}/maintenance")
async def maintenance(
    vehicle_id: UUID,
    page: int = Query(1, ge=1),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(TransportService(db).maintenance(user.school_id, vehicle_id, page))
    )


@router.post("/vehicles/{vehicle_id}/maintenance", status_code=201)
async def record_maintenance(
    vehicle_id: UUID,
    data: MaintenanceRequest,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "maintenance", data, vehicle_id)


@router.get("/vehicles/{vehicle_id}/location")
async def location(
    vehicle_id: UUID, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    return result(await run(TransportService(db).location(user.school_id, vehicle_id)))


@router.post("/vehicles/{vehicle_id}/location", status_code=201)
async def position(
    vehicle_id: UUID,
    data: PositionRequest,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "position", data, vehicle_id)


@router.get("/routes")
async def routes(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, max_length=200),
    is_active: bool = True,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(TransportService(db).routes(user.school_id, page, search, is_active))
    )


@router.get("/routes/{route_id}")
async def route(
    route_id: UUID, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    return result(await run(TransportService(db).route(user.school_id, route_id)))


@router.post("/routes", status_code=201)
async def create_route(
    data: RouteCreate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "create_route", data)


@router.patch("/routes/{route_id}")
async def update_route(
    route_id: UUID,
    data: RouteUpdate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "update_route", data, route_id)


@router.post("/routes/{route_id}/stops", status_code=201)
async def create_stop(
    route_id: UUID,
    data: StopCreate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "create_stop", data, route_id)


@router.patch("/stops/{stop_id}")
async def update_stop(
    stop_id: UUID,
    data: StopUpdate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "update_stop", data, stop_id)


@router.post("/routes/{route_id}/stop-order")
async def reorder(
    route_id: UUID,
    data: ReorderStops,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "reorder_stops", data, route_id)


@router.get("/runs")
async def runs(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, max_length=200),
    is_active: bool = True,
    direction: Optional[Direction] = None,
    route_id: Optional[UUID] = None,
    vehicle_id: Optional[UUID] = None,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            TransportService(db).runs(
                user.school_id, page, search, is_active, direction, route_id, vehicle_id
            )
        )
    )


@router.get("/runs/{run_id}")
async def run_details(
    run_id: UUID, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    service = TransportService(db)
    row = await run(service.get(TransportRun, user.school_id, run_id))
    vehicle = await run(service.get(Vehicle, user.school_id, row.vehicle_id))
    return result(
        fields(
            row,
            "id name route_id vehicle_id direction start_time end_time weekdays is_active notes",
        )
        | {
            "vehicle_number": vehicle.vehicle_number,
            "capacity": vehicle.capacity,
            "route": await run(service.route(user.school_id, row.route_id)),
        }
    )


@router.post("/runs", status_code=201)
async def create_run(
    data: RunCreate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "create_run", data)


@router.patch("/runs/{run_id}")
async def update_run(
    run_id: UUID,
    data: RunUpdate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "update_run", data, run_id)


@router.get("/students")
async def students(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, max_length=200),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(TransportService(db).students(user.school_id, page, search))
    )


@router.post("/quote")
async def quote(
    data: QuoteRequest, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    return result(await run(TransportService(db).quote(user.school_id, data)))


@router.get("/assignments")
async def assignments(
    page: int = Query(1, ge=1),
    search: Optional[str] = Query(None, max_length=200),
    is_active: bool = True,
    run_id: Optional[UUID] = None,
    route_id: Optional[UUID] = None,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            TransportService(db).assignments(
                user.school_id,
                page,
                search=search,
                is_active=is_active,
                run_id=run_id,
                route_id=route_id,
            )
        )
    )


@router.get("/assignments/{assignment_id}")
async def assignment(
    assignment_id: UUID, user=Depends(access()), db: AsyncSession = Depends(get_db)
):
    service = TransportService(db)
    return result(
        service.assignment_response(
            await run(service.get(StudentTransport, user.school_id, assignment_id))
        )
    )


@router.post("/assign", status_code=201)
async def assign(
    data: StudentTransportAssign,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "assign", data)


@router.post("/assignments/{assignment_id}/change", status_code=201)
async def change_assignment(
    assignment_id: UUID,
    data: StudentTransportAssign,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    if not user.has_permission("transport:delete"):
        raise HTTPException(
            403,
            detail=error_response(
                "Changing a current assignment also requires permission to end the previous assignment",
                "TRANSPORT_END_REQUIRED",
            ),
        )
    return await command(db, user, "change_assignment", data, assignment_id)


@router.post("/assignments/{assignment_id}/end")
@router.delete("/assign/{assignment_id}")
async def end_assignment(
    assignment_id: UUID,
    data: ReasonCommand,
    user=Depends(access("transport:delete")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "end_assignment", data, assignment_id)


@router.get("/routes/{route_id}/students")
async def route_students(
    route_id: UUID,
    page: int = Query(1, ge=1),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            TransportService(db).assignments(user.school_id, page, route_id=route_id)
        )
    )


@router.get("/trips")
async def trips(
    page: int = Query(1, ge=1),
    date_ad: Optional[date] = None,
    status: Optional[Literal["in_progress", "completed", "cancelled"]] = None,
    run_id: Optional[UUID] = None,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            TransportService(db).trips(user.school_id, page, date_ad, status, run_id)
        )
    )


@router.get("/trips/{trip_id}")
async def trip(
    trip_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=200),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(TransportService(db).trip(user.school_id, trip_id, page, limit))
    )


@router.post("/trips", status_code=201)
async def start_trip(
    data: StartTrip,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "start_trip", data)


@router.post("/passengers/{passenger_id}")
async def passenger(
    passenger_id: UUID,
    data: PassengerUpdate,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "passenger", data, passenger_id)


@router.post("/trips/{trip_id}/complete")
async def complete_trip(
    trip_id: UUID,
    data: CompleteTrip,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "complete_trip", data, trip_id)


@router.post("/trips/{trip_id}/cancel")
async def cancel_trip(
    trip_id: UUID,
    data: ReasonCommand,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "cancel_trip", data, trip_id)


@router.get("/assignments/{assignment_id}/fee-options")
async def fee_options(
    assignment_id: UUID,
    month_bs: str = Query(..., pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    user=Depends(access("fee:create")),
    db: AsyncSession = Depends(get_db),
):
    return result(
        await run(
            TransportService(db).fee_options(user.school_id, assignment_id, month_bs)
        )
    )


@router.post("/assignments/{assignment_id}/bill", status_code=201)
async def bill(
    assignment_id: UUID,
    data: BillRequest,
    user=Depends(access("fee:create")),
    db: AsyncSession = Depends(get_db),
):
    return await command(db, user, "bill", data, assignment_id)


@router.get("/stats")
async def stats(user=Depends(access()), db: AsyncSession = Depends(get_db)):
    return result(await run(TransportService(db).stats(user.school_id)))


@router.get("/history")
async def history(
    page: int = Query(1, ge=1),
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    return result(await run(TransportService(db).history(user.school_id, page)))


@router.get("/export")
async def export(
    report: Literal["assignments", "trip"],
    search: Optional[str] = Query(None, max_length=200),
    is_active: bool = True,
    run_id: Optional[UUID] = None,
    trip_id: Optional[UUID] = None,
    user=Depends(access()),
    db: AsyncSession = Depends(get_db),
):
    data = await run(
        TransportService(db).export(
            user.school_id, report, search, is_active, run_id, trip_id
        )
    )
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="transport-{report}-{today()}.csv"'
        },
    )
