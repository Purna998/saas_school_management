"""Nepal School Management System - Notification Service"""
import uuid
import logging
from typing import Optional, List, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from services.notification_worker.models.notification import (
    NotificationEvent, NotificationPreference, EventType, EventStatus, NotificationChannel
)

logger = logging.getLogger(__name__)

MESSAGE_TEMPLATES = {
    EventType.ATTENDANCE_MARKED: "{child_name} was {status} on {date}. - {school_name}",
    EventType.FEE_DUE: "Fee reminder: NPR {amount} due for {child_name} by {due_date}. - {school_name}",
    EventType.EXAM_PUBLISHED: "Exam results for {exam_name} have been published. Check the portal. - {school_name}",
    EventType.ANNOUNCEMENT: "{message} - {school_name}",
    EventType.LEAVE_APPROVED: "Your leave request from {start_date} to {end_date} has been {status}. - {school_name}",
    EventType.STUDENT_ENROLLED: "{student_name} has been enrolled in Grade {grade} Section {section}. - {school_name}",
}


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(self, school_id: uuid.UUID, event_type: str, payload: dict) -> NotificationEvent:
        event = NotificationEvent(
            id=uuid.uuid4(), school_id=school_id,
            event_type=EventType(event_type), payload=payload,
            status=EventStatus.PENDING,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def process_pending_events(self, school_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            select(NotificationEvent).where(
                NotificationEvent.school_id == school_id,
                NotificationEvent.status == EventStatus.PENDING
            ).limit(100)
        )
        events = result.scalars().all()
        processed = 0
        failed = 0

        for event in events:
            try:
                event.status = EventStatus.PROCESSING
                await self.db.flush()

                template = MESSAGE_TEMPLATES.get(event.event_type)
                if template:
                    try:
                        message = template.format(**event.payload)
                    except KeyError:
                        message = str(event.payload)

                    logger.info(f"Notification [{event.event_type.value}]: {message}")

                event.status = EventStatus.PROCESSED
                event.processed_at = datetime.utcnow()
                processed += 1
            except Exception as e:
                event.status = EventStatus.FAILED
                event.error_message = str(e)
                failed += 1

        await self.db.commit()
        return {"processed": processed, "failed": failed, "total": len(events)}

    async def get_events(self, school_id: uuid.UUID, page: int = 1, limit: int = 20, status_filter: Optional[str] = None) -> Tuple[List[NotificationEvent], int]:
        query = select(NotificationEvent).where(NotificationEvent.school_id == school_id)
        if status_filter:
            query = query.where(NotificationEvent.status == EventStatus(status_filter))
        total = (await self.db.execute(select(func.count()).select_from(query.subquery()))).scalar()
        query = query.offset((page - 1) * limit).limit(limit).order_by(NotificationEvent.created_at.desc())
        events = (await self.db.execute(query)).scalars().all()
        return events, total

    async def get_preferences(self, school_id: uuid.UUID, user_id: uuid.UUID) -> List[NotificationPreference]:
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.school_id == school_id,
                NotificationPreference.user_id == user_id
            )
        )
        return result.scalars().all()

    async def update_preference(self, school_id: uuid.UUID, user_id: uuid.UUID, data: dict) -> NotificationPreference:
        event_type = EventType(data["event_type"])
        result = await self.db.execute(
            select(NotificationPreference).where(
                NotificationPreference.school_id == school_id,
                NotificationPreference.user_id == user_id,
                NotificationPreference.event_type == event_type
            )
        )
        pref = result.scalar_one_or_none()

        if pref:
            pref.channel = NotificationChannel(data.get("channel", "sms"))
            pref.is_enabled = data.get("is_enabled", True)
        else:
            pref = NotificationPreference(
                id=uuid.uuid4(), school_id=school_id, user_id=user_id,
                event_type=event_type, channel=NotificationChannel(data.get("channel", "sms")),
                is_enabled=data.get("is_enabled", True),
            )
            self.db.add(pref)

        await self.db.commit()
        await self.db.refresh(pref)
        return pref
