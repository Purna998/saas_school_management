"""
Nepal School Management System - Session Schemas
Pydantic models for session management endpoints
"""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Session response schema"""

    id: UUID = Field(..., description="Session ID")
    user_id: UUID = Field(..., description="User ID")
    device_name: Optional[str] = Field(None, description="Device name")
    device_type: Optional[str] = Field(None, description="Device type (desktop, mobile, tablet)")
    browser: Optional[str] = Field(None, description="Browser name")
    os: Optional[str] = Field(None, description="Operating system")
    ip_address: Optional[str] = Field(None, description="IP address")
    location: Optional[str] = Field(None, description="Geographic location")
    status: str = Field(..., description="Session status")
    last_activity_at: Optional[datetime] = Field(None, description="Last activity timestamp")
    created_at: datetime = Field(..., description="Session creation timestamp")
    expires_at: datetime = Field(..., description="Session expiry timestamp")
    is_current: bool = Field(default=False, description="Current session flag")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "session-uuid",
                "user_id": "user-uuid",
                "device_name": "Chrome on Windows",
                "device_type": "desktop",
                "browser": "Chrome 115",
                "os": "Windows 11",
                "ip_address": "103.10.28.123",
                "location": "Kathmandu, Nepal",
                "status": "active",
                "last_activity_at": "2026-06-25T08:30:00Z",
                "created_at": "2026-06-25T08:00:00Z",
                "expires_at": "2026-07-02T08:00:00Z",
                "is_current": True,
            }
        }


class SessionListResponse(BaseModel):
    """Session list response schema"""

    sessions: List[SessionResponse] = Field(..., description="List of active sessions")
    total: int = Field(..., description="Total number of sessions")

    class Config:
        json_schema_extra = {
            "example": {"sessions": [], "total": 3}
        }


class RevokeSessionRequest(BaseModel):
    """Revoke session request schema"""

    session_id: UUID = Field(..., description="Session ID to revoke")

    class Config:
        json_schema_extra = {"example": {"session_id": "session-uuid"}}
