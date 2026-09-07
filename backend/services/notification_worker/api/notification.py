"""Nepal School Management System - Notification API Routes"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from shared.database.base import get_db
from shared.schemas.responses import success_response
from services.auth.dependencies.auth import get_current_active_user, require_permission, require_role
from services.auth.models.user import User
from services.notification_worker.schemas.notification import *
from services.notification_worker.services.notification_service import NotificationService

router = APIRouter()


@router.post("/events", response_model=EventResponse, status_code=201)
async def create_event(data: EventCreate, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    s = NotificationService(db)
    event = await s.create_event(user.school_id, data.event_type, data.payload)
    return EventResponse(id=event.id, event_type=event.event_type.value, payload=event.payload, status=event.status.value, processed_at=event.processed_at, error_message=event.error_message, created_at=event.created_at)


@router.post("/process")
async def process_events(user: User = Depends(require_role("school_admin")), db: AsyncSession = Depends(get_db)):
    s = NotificationService(db)
    result = await s.process_pending_events(user.school_id)
    return success_response(data=result)


@router.get("/events", response_model=EventListResponse)
async def list_events(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100), status_filter: Optional[str] = Query(None, alias="status"), user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    s = NotificationService(db)
    events, total = await s.get_events(user.school_id, page, limit, status_filter)
    return EventListResponse(events=[EventResponse(id=e.id, event_type=e.event_type.value, payload=e.payload, status=e.status.value, processed_at=e.processed_at, error_message=e.error_message, created_at=e.created_at) for e in events], total=total, page=page, limit=limit)


@router.get("/preferences", response_model=list[PreferenceResponse])
async def get_preferences(user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    s = NotificationService(db)
    prefs = await s.get_preferences(user.school_id, user.id)
    return [PreferenceResponse(id=p.id, user_id=p.user_id, event_type=p.event_type.value, channel=p.channel.value, is_enabled=p.is_enabled) for p in prefs]


@router.patch("/preferences", response_model=PreferenceResponse)
async def update_preference(data: PreferenceUpdate, user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    s = NotificationService(db)
    pref = await s.update_preference(user.school_id, user.id, data.model_dump())
    return PreferenceResponse(id=pref.id, user_id=pref.user_id, event_type=pref.event_type.value, channel=pref.channel.value, is_enabled=pref.is_enabled)
