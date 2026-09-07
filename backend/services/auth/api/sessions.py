"""
Nepal School Management System - Sessions API Routes
User session management endpoints
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import RecordNotFoundError
from services.auth.dependencies.auth import get_current_active_user
from services.auth.models.user import User
from services.auth.models.session import UserSession, SessionStatus
from services.auth.schemas.session import SessionResponse, SessionListResponse
from services.auth.utils.jwt import revoke_token

router = APIRouter()


@router.get("/", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all active sessions for current user.

    Returns:
        - List of sessions with device info, location, last activity

    Status Codes:
        - 200: Success
        - 401: Unauthorized
    """
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.status == SessionStatus.ACTIVE,
            UserSession.expires_at > datetime.utcnow()
        ).order_by(UserSession.last_activity_at.desc())
    )
    sessions = result.scalars().all()

    # Determine current session from token info
    token_info = getattr(current_user, '_token_info', None)
    current_session_id = token_info.get("session_id") if token_info else None

    session_responses = []
    for session in sessions:
        session_responses.append(SessionResponse(
            id=session.id,
            user_id=session.user_id,
            device_name=session.device_name,
            device_type=session.device_type,
            browser=session.browser,
            os=session.os,
            ip_address=str(session.ip_address) if session.ip_address else None,
            location=session.location,
            status=session.status.value,
            last_activity_at=session.last_activity_at,
            created_at=session.created_at,
            expires_at=session.expires_at,
            is_current=(session.id == current_session_id) if current_session_id else False,
        ))

    return SessionListResponse(
        sessions=session_responses,
        total=len(session_responses)
    )


@router.delete("/{session_id}")
async def revoke_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke a specific session.

    Invalidates the refresh token and marks session as revoked.

    Status Codes:
        - 200: Session revoked
        - 401: Unauthorized
        - 404: Session not found
    """
    result = await db.execute(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response("Session not found", "SESSION_NOT_FOUND"),
        )

    if session.status != SessionStatus.ACTIVE:
        return success_response(data={"message": "Session is already revoked"})

    # Revoke session
    session.revoke(current_user.id)

    # Add refresh token to blocklist
    if session.refresh_token_jti:
        remaining = int((session.expires_at - datetime.utcnow()).total_seconds())
        if remaining > 0:
            await revoke_token(session.refresh_token_jti, remaining)

    await db.commit()

    return success_response(data={"message": "Session revoked successfully"})


@router.delete("/")
async def revoke_all_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Revoke all sessions except the current one.

    Useful for "logout from all devices" feature.

    Status Codes:
        - 200: All sessions revoked
        - 401: Unauthorized
    """
    # Get current session ID
    token_info = getattr(current_user, '_token_info', None)
    current_session_id = token_info.get("session_id") if token_info else None

    # Get all active sessions
    result = await db.execute(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.status == SessionStatus.ACTIVE
        )
    )
    sessions = result.scalars().all()

    revoked_count = 0
    for session in sessions:
        # Skip current session
        if current_session_id and session.id == current_session_id:
            continue

        session.revoke(current_user.id)

        # Add refresh token to blocklist
        if session.refresh_token_jti:
            remaining = int((session.expires_at - datetime.utcnow()).total_seconds())
            if remaining > 0:
                await revoke_token(session.refresh_token_jti, remaining)

        revoked_count += 1

    await db.commit()

    return success_response(data={
        "message": f"Revoked {revoked_count} session(s)",
        "revoked_count": revoked_count,
    })
