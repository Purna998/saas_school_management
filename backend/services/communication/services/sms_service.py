"""
Nepal School Management System - SMS Service
SMS sending via Sparrow SMS (primary) and Aakash SMS (fallback)
"""

import uuid
import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from shared.config.settings import settings
from shared.utils.exceptions import SMSGatewayError
from services.communication.models.message import (
    Message,
    MessageChannel,
    MessageStatus,
    MessageType,
    SMSProvider,
    SMSTemplate,
)

logger = logging.getLogger(__name__)


class SMSService:
    """SMS service with Sparrow SMS (primary) and Aakash SMS (fallback)"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_sms(
        self,
        school_id: uuid.UUID,
        phone_number: str,
        message: str,
        message_type: MessageType = MessageType.CUSTOM,
        recipient_id: Optional[uuid.UUID] = None,
        recipient_name: Optional[str] = None,
        sent_by: Optional[uuid.UUID] = None,
    ) -> Message:
        """
        Send a single SMS message.

        Tries Sparrow SMS first, falls back to Aakash SMS on failure.
        """
        # Create message record
        msg = Message(
            id=uuid.uuid4(),
            school_id=school_id,
            channel=MessageChannel.SMS,
            message_type=message_type,
            status=MessageStatus.QUEUED,
            recipient_id=recipient_id,
            recipient_phone=phone_number,
            recipient_name=recipient_name,
            body=message,
            sent_by=sent_by,
        )
        self.db.add(msg)
        await self.db.flush()

        # Attempt to send
        try:
            if settings.sparrow_sms_enabled:
                provider_msg_id = await self._send_via_sparrow(phone_number, message)
                msg.provider = SMSProvider.SPARROW.value
            elif settings.aakash_sms_enabled:
                provider_msg_id = await self._send_via_aakash(phone_number, message)
                msg.provider = SMSProvider.AAKASH.value
            else:
                # No provider configured - log only
                logger.warning(f"No SMS provider configured. Message queued: {msg.id}")
                msg.status = MessageStatus.QUEUED
                await self.db.commit()
                return msg

            msg.provider_message_id = provider_msg_id
            msg.status = MessageStatus.SENT
            msg.sent_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"SMS send failed: {str(e)}")
            msg.status = MessageStatus.FAILED
            msg.failed_at = datetime.utcnow()
            msg.failure_reason = str(e)

            # Try fallback provider
            if settings.sparrow_sms_enabled and settings.aakash_sms_enabled and msg.provider != SMSProvider.AAKASH.value:
                try:
                    provider_msg_id = await self._send_via_aakash(phone_number, message)
                    msg.provider = SMSProvider.AAKASH.value
                    msg.provider_message_id = provider_msg_id
                    msg.status = MessageStatus.SENT
                    msg.sent_at = datetime.utcnow()
                    msg.failed_at = None
                    msg.failure_reason = None
                except Exception as fallback_error:
                    logger.error(f"Fallback SMS also failed: {str(fallback_error)}")

        await self.db.commit()
        return msg

    async def send_bulk_sms(
        self,
        school_id: uuid.UUID,
        recipients: List[dict],
        message: str,
        message_type: MessageType = MessageType.CUSTOM,
        sent_by: Optional[uuid.UUID] = None,
    ) -> dict:
        """
        Send SMS to multiple recipients.

        Args:
            recipients: List of {phone, name, id} dicts
            message: SMS body
        """
        sent_count = 0
        failed_count = 0

        for recipient in recipients:
            try:
                await self.send_sms(
                    school_id=school_id,
                    phone_number=recipient["phone"],
                    message=message,
                    message_type=message_type,
                    recipient_id=recipient.get("id"),
                    recipient_name=recipient.get("name"),
                    sent_by=sent_by,
                )
                sent_count += 1
            except Exception:
                failed_count += 1

        return {
            "total": len(recipients),
            "sent": sent_count,
            "failed": failed_count,
        }

    async def send_from_template(
        self,
        school_id: uuid.UUID,
        template_code: str,
        phone_number: str,
        variables: dict,
        recipient_id: Optional[uuid.UUID] = None,
        sent_by: Optional[uuid.UUID] = None,
    ) -> Message:
        """Send SMS using a template"""
        # Get template
        result = await self.db.execute(
            select(SMSTemplate).where(
                SMSTemplate.school_id == school_id,
                SMSTemplate.code == template_code,
                SMSTemplate.is_active == True,
            )
        )
        template = result.scalar_one_or_none()

        if not template:
            # Try global template (school_id = None patterns not used, just use body directly)
            raise SMSGatewayError(f"Template '{template_code}' not found")

        # Render template
        try:
            body = template.body_en.format(**variables)
        except KeyError as e:
            raise SMSGatewayError(f"Missing template variable: {e}")

        return await self.send_sms(
            school_id=school_id,
            phone_number=phone_number,
            message=body,
            message_type=template.message_type,
            recipient_id=recipient_id,
            sent_by=sent_by,
        )

    async def get_message_history(
        self,
        school_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        channel: Optional[MessageChannel] = None,
        status_filter: Optional[MessageStatus] = None,
    ) -> tuple:
        """Get message history with pagination"""
        query = select(Message).where(Message.school_id == school_id)

        if channel:
            query = query.where(Message.channel == channel)
        if status_filter:
            query = query.where(Message.status == status_filter)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Message.created_at.desc())

        result = await self.db.execute(query)
        messages = result.scalars().all()

        return messages, total

    async def _send_via_sparrow(self, phone: str, message: str) -> str:
        """Send SMS via Sparrow SMS API"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.sparrow_sms_api_url}sms/send",
                data={
                    "token": settings.sparrow_sms_token,
                    "from": settings.sparrow_sms_from,
                    "to": phone,
                    "text": message,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("response_code") == 200:
                    return data.get("message_id", "")
                raise SMSGatewayError(f"Sparrow SMS error: {data.get('message', 'Unknown error')}")
            raise SMSGatewayError(f"Sparrow SMS HTTP error: {response.status_code}")

    async def _send_via_aakash(self, phone: str, message: str) -> str:
        """Send SMS via Aakash SMS API"""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.aakash_sms_api_url}sms/send",
                json={
                    "auth_token": settings.aakash_sms_token,
                    "from": settings.aakash_sms_from,
                    "to": phone,
                    "text": message,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("message_id", str(uuid.uuid4()))
            raise SMSGatewayError(f"Aakash SMS HTTP error: {response.status_code}")
