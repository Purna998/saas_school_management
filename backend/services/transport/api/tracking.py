"""Separate minimal tracking surfaces; office/roster permissions stay unchanged."""

from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from services.auth.dependencies.auth import get_current_active_user
from services.transport.api.transport import access, result, run
from services.transport.schemas.transport import ReasonCommand
from services.transport.schemas.tracking import (
    FamilyLink,
    PhoneIssue,
    LiveFix,
    StopProgress,
)
from services.transport.services.tracking_service import TrackingService
from shared.database.base import get_db

router = APIRouter()


def private(response: Response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Referrer-Policy"] = "no-referrer"


async def school_user(user=Depends(get_current_active_user)):
    if not user.school_id:
        raise HTTPException(403, "A school account is required")
    return user


@router.get("/live")
async def live(
    response: Response,
    page: int = Query(1, ge=1, le=10000),
    user=Depends(school_user),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(await run(TrackingService(db).feed(user, page)))


@router.get("/family-access")
async def families(
    response: Response,
    page: int = Query(1, ge=1),
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(await run(TrackingService(db).families(user.school_id, page)))


@router.post("/family-access", status_code=201)
async def link(
    data: FamilyLink,
    response: Response,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(
        await run(
            TrackingService(db).command(
                "link_parent", user.school_id, data, user.id, user.full_name_en
            )
        )
    )


@router.post("/family-access/{link_id}/revoke")
async def unlink(
    link_id: UUID,
    data: ReasonCommand,
    response: Response,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(
        await run(
            TrackingService(db).command(
                "revoke_parent",
                user.school_id,
                data,
                user.id,
                user.full_name_en,
                link_id,
            )
        )
    )


@router.post("/trips/{trip_id}/phone", status_code=201)
async def issue(
    trip_id: UUID,
    data: PhoneIssue,
    response: Response,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(
        await run(
            TrackingService(db).issue_phone(user.school_id, trip_id, data.label, user)
        )
    )


@router.post("/trips/{trip_id}/phone/revoke")
async def revoke(
    trip_id: UUID,
    response: Response,
    user=Depends(access("transport:create")),
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(
        await run(TrackingService(db).revoke_phone(user.school_id, trip_id, user))
    )


PhoneToken = Annotated[str | None, Header(alias="X-Transport-Token", max_length=150)]


@router.get("/phone/context")
async def context(
    response: Response, token: PhoneToken = None, db: AsyncSession = Depends(get_db)
):
    private(response)
    service = TrackingService(db)
    session, trip = await run(service.phone(token))
    return result(service.phone_context(session, trip))


@router.post("/phone/position")
async def position(
    data: LiveFix,
    response: Response,
    token: PhoneToken = None,
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(await run(TrackingService(db).ingest(token, data)))


@router.post("/phone/progress")
async def progress(
    data: StopProgress,
    response: Response,
    token: PhoneToken = None,
    db: AsyncSession = Depends(get_db),
):
    private(response)
    return result(await run(TrackingService(db).progress(token, data)))
