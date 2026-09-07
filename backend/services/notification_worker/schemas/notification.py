"""Nepal School Management System - Notification Schemas"""
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    event_type: str
    payload: Dict = Field(default_factory=dict)


class EventResponse(BaseModel):
    id: UUID
    event_type: str
    payload: Dict
    status: str
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    events: List[EventResponse]
    total: int
    page: int
    limit: int


class PreferenceUpdate(BaseModel):
    event_type: str
    channel: str = "sms"
    is_enabled: bool = True


class PreferenceResponse(BaseModel):
    id: UUID
    user_id: UUID
    event_type: str
    channel: str
    is_enabled: bool
    class Config:
        from_attributes = True
