"""
Nepal School Management System - Communication Schemas
Pydantic models for SMS, Email, Push notification endpoints
"""

from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class SendSMSRequest(BaseModel):
    """Send SMS request"""

    phone_numbers: List[str] = Field(..., min_length=1, description="Recipient phone numbers")
    message: str = Field(..., min_length=1, max_length=480, description="SMS body (max 480 chars)")
    message_type: str = Field(default="custom", description="Message type")
    template_code: Optional[str] = Field(None, description="Template code to use")
    template_data: Optional[Dict] = Field(None, description="Template variables")

    class Config:
        json_schema_extra = {
            "example": {
                "phone_numbers": ["+977-9841234567", "+977-9851234567"],
                "message": "Your child Aarav was absent today (2083-03-14).",
                "message_type": "attendance",
            }
        }


class SendEmailRequest(BaseModel):
    """Send email request"""

    recipients: List[EmailStr] = Field(..., min_length=1)
    subject: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)
    message_type: str = Field(default="custom")
    is_html: bool = Field(default=False)


class SendBulkSMSRequest(BaseModel):
    """Bulk SMS to a group"""

    grade: Optional[int] = Field(None, ge=1, le=12)
    section: Optional[str] = None
    message: str = Field(..., min_length=1, max_length=480)
    message_type: str = Field(default="announcement")
    target: str = Field(default="parents", description="Target: parents, students, or all")


class MessageResponse(BaseModel):
    """Message response"""

    id: UUID
    channel: str
    message_type: str
    status: str
    recipient_phone: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None
    body: str
    subject: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """Message list"""

    messages: List[MessageResponse]
    total: int
    page: int
    limit: int


class SMSBalanceResponse(BaseModel):
    """SMS credit balance"""

    provider: str
    credits_remaining: int
    credits_used_today: int
    credits_used_month: int


class SMSTemplateResponse(BaseModel):
    """SMS template"""

    id: UUID
    code: str
    name_en: str
    name_np: Optional[str] = None
    body_en: str
    body_np: Optional[str] = None
    message_type: str
    variables: Optional[Dict] = None
    is_active: bool

    class Config:
        from_attributes = True
