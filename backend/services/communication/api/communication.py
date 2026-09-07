"""
Nepal School Management System - Communication API Routes
SMS, Email, and Push notification endpoints
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import SMSGatewayError
from services.auth.dependencies.auth import get_current_active_user, require_permission
from services.auth.models.user import User
from services.communication.schemas.message import (
    SendSMSRequest,
    SendBulkSMSRequest,
    SendEmailRequest,
    MessageResponse,
    MessageListResponse,
)
from services.communication.services.sms_service import SMSService
from shared.config.settings import settings
from services.communication.models.message import MessageChannel, MessageStatus, MessageType

router = APIRouter()


@router.post("/sms/send")
async def send_sms(
    sms_data: SendSMSRequest,
    current_user: User = Depends(require_permission("communication:sms:send")),
    db: AsyncSession = Depends(get_db)
):
    """
    Send SMS to one or more phone numbers.

    Status Codes:
        - 200: SMS sent/queued
        - 503: SMS gateway error
    """
    sms_service = SMSService(db)
    message_type = MessageType(sms_data.message_type) if sms_data.message_type else MessageType.CUSTOM

    if len(sms_data.phone_numbers) == 1:
        msg = await sms_service.send_sms(
            school_id=current_user.school_id,
            phone_number=sms_data.phone_numbers[0],
            message=sms_data.message,
            message_type=message_type,
            sent_by=current_user.id,
        )
        return success_response(data={
            "message_id": str(msg.id),
            "status": msg.status.value,
            "sent_at": msg.sent_at.isoformat() if msg.sent_at else None,
        })
    else:
        recipients = [{"phone": p} for p in sms_data.phone_numbers]
        result = await sms_service.send_bulk_sms(
            school_id=current_user.school_id,
            recipients=recipients,
            message=sms_data.message,
            message_type=message_type,
            sent_by=current_user.id,
        )
        return success_response(data=result)


@router.post("/sms/bulk")
async def send_bulk_sms(
    bulk_data: SendBulkSMSRequest,
    current_user: User = Depends(require_permission("communication:sms:bulk")),
    db: AsyncSession = Depends(get_db)
):
    """
    Send bulk SMS to parents/students of a grade/section.

    Status Codes:
        - 200: Bulk SMS initiated
    """
    # In production, this would query the student service for phone numbers
    # For now, return a placeholder response
    return success_response(data={
        "message": "Bulk SMS queued",
        "target": bulk_data.target,
        "grade": bulk_data.grade,
        "section": bulk_data.section,
        "status": "queued",
    })


@router.post("/email/send")
async def send_email(
    email_data: SendEmailRequest,
    current_user: User = Depends(require_permission("communication:email:send")),
    db: AsyncSession = Depends(get_db)
):
    """
    Send email to recipients.

    Status Codes:
        - 200: Email sent/queued
    """
    # Email sending would integrate with Amazon SES
    return success_response(data={
        "message": "Email queued for delivery",
        "recipients_count": len(email_data.recipients),
        "subject": email_data.subject,
        "status": "queued",
    })


@router.get("/messages", response_model=MessageListResponse)
async def list_messages(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    channel: Optional[str] = Query(default=None),
    message_status: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(require_permission("communication:read")),
    db: AsyncSession = Depends(get_db)
):
    """
    List sent messages with filters.

    Status Codes:
        - 200: Success
    """
    sms_service = SMSService(db)

    channel_enum = MessageChannel(channel) if channel else None
    status_enum = MessageStatus(message_status) if message_status else None

    messages, total = await sms_service.get_message_history(
        school_id=current_user.school_id,
        page=page,
        limit=limit,
        channel=channel_enum,
        status_filter=status_enum,
    )

    return MessageListResponse(
        messages=[
            MessageResponse(
                id=m.id,
                channel=m.channel.value,
                message_type=m.message_type.value,
                status=m.status.value,
                recipient_phone=m.recipient_phone,
                recipient_email=m.recipient_email,
                recipient_name=m.recipient_name,
                body=m.body,
                subject=m.subject,
                sent_at=m.sent_at,
                delivered_at=m.delivered_at,
                failure_reason=m.failure_reason,
                created_at=m.created_at,
            )
            for m in messages
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/sms/balance")
async def get_sms_balance(
    current_user: User = Depends(require_permission("communication:read")),
    db: AsyncSession = Depends(get_db)
):
    """
    Get SMS credit balance from provider.

    Status Codes:
        - 200: Success
    """
    # Would query Sparrow/Aakash SMS balance API
    return success_response(data={
        "provider": "sparrow" if settings.sparrow_sms_enabled else "aakash",
        "credits_remaining": -1,  # -1 indicates not available
        "message": "Balance check not configured",
    })
