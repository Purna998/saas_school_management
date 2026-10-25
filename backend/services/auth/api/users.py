"""
Nepal School Management System - Users API Routes
User profile management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.config.settings import settings
from shared.schemas.responses import success_response, error_response
from shared.storage import local_storage
from shared.utils.exceptions import (
    InvalidCredentialsError,
)
from services.auth.dependencies.auth import get_current_active_user
from services.auth.models.user import User
from services.auth.schemas.user import (
    UserResponse,
    UserUpdate,
    ChangePasswordRequest,
    UploadPhotoResponse,
)
from services.auth.services.user_service import UserService

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user profile.

    Returns:
        - User profile with roles and permissions

    Status Codes:
        - 200: Success
        - 401: Unauthorized
    """
    try:
        user_service = UserService(db)
        user = await user_service.get_user_by_id(current_user.id)

        return UserResponse(
            id=user.id,
            email=user.email,
            full_name_en=user.full_name_en,
            full_name_np=user.full_name_np,
            phone=user.phone,
            photo_url=user.photo_url,
            school_id=user.school_id,
            status=user.status.value,
            email_verified=user.email_verified,
            mfa_enabled=user.mfa_enabled,
            roles=[
                {
                    "id": role.id,
                    "code": role.code,
                    "name_en": role.name_en,
                    "name_np": role.name_np,
                }
                for role in user.roles
            ],
            permissions=list(user.get_permissions()),
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response("Failed to get user profile", "USER_FETCH_ERROR"),
        )


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user profile.

    Allowed fields: full_name_en, full_name_np, phone

    Status Codes:
        - 200: Updated successfully
        - 400: Validation error
        - 401: Unauthorized
    """
    try:
        user_service = UserService(db)
        updated_user = await user_service.update_user(
            user_id=current_user.id,
            user_data=user_data
        )

        return UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            full_name_en=updated_user.full_name_en,
            full_name_np=updated_user.full_name_np,
            phone=updated_user.phone,
            photo_url=updated_user.photo_url,
            school_id=updated_user.school_id,
            status=updated_user.status.value,
            email_verified=updated_user.email_verified,
            mfa_enabled=updated_user.mfa_enabled,
            roles=[
                {
                    "id": role.id,
                    "code": role.code,
                    "name_en": role.name_en,
                    "name_np": role.name_np,
                }
                for role in updated_user.roles
            ],
            permissions=list(updated_user.get_permissions()),
            last_login_at=updated_user.last_login_at,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response("Failed to update user profile", "USER_UPDATE_ERROR"),
        )


@router.post("/me/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change password for current user.

    Requires: old_password, new_password

    Status Codes:
        - 200: Password changed
        - 400: Validation error or incorrect old password
        - 401: Unauthorized
    """
    try:
        user_service = UserService(db)
        await user_service.change_password(
            user_id=current_user.id,
            old_password=password_data.old_password,
            new_password=password_data.new_password
        )

        return success_response(
            data={"message": "Password changed successfully"}
        )

    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_OLD_PASSWORD"),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(str(e), "INVALID_NEW_PASSWORD"),
        )

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_response("Failed to change password", "PASSWORD_CHANGE_ERROR"),
        )


@router.post("/me/upload-photo", response_model=UploadPhotoResponse)
async def upload_profile_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload profile photo.

    Accepts JPEG and PNG files up to 10MB.
    Stores the file in the configured private VPS upload directory.

    Status Codes:
        - 200: Photo uploaded
        - 400: Invalid file type or size
        - 401: Unauthorized
    """
    # Validate file type
    if not file.content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response("File type not detected", "INVALID_FILE_TYPE"),
        )

    allowed_types = ["image/jpeg", "image/png", "image/jpg"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_response(
                f"Invalid file type '{file.content_type}'. Allowed: JPEG, PNG",
                "INVALID_FILE_TYPE"
            ),
        )

    # Read file and check size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)

    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=error_response(
                f"File size {size_mb:.1f}MB exceeds limit of {settings.max_upload_size_mb}MB",
                "FILE_SIZE_EXCEEDED"
            ),
        )

    filename = await local_storage.save_user_photo(
        current_user.id,
        contents,
        file.content_type,
    )
    photo_path = f"/api/v1/users/me/photo/{filename}"
    photo_url = f"{settings.public_api_url.rstrip('/')}{photo_path}"

    # Update user profile
    user_service = UserService(db)
    await user_service.update_photo(current_user.id, photo_url)

    return UploadPhotoResponse(photo_url=photo_url)


@router.get("/me/photo/{filename}", response_class=FileResponse)
async def get_profile_photo(
    filename: str,
    current_user: User = Depends(get_current_active_user),
):
    """Return only the authenticated user's current profile photo."""
    expected_url = f"{settings.public_api_url.rstrip('/')}/api/v1/users/me/photo/{filename}"
    if current_user.photo_url != expected_url:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    try:
        path = local_storage.user_photo_path(current_user.id, filename)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type)
