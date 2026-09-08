"""
Nepal School Management System - Users API Routes
User profile management endpoints
"""

import asyncio
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.config.settings import settings
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import (
    InvalidCredentialsError,
    InvalidFileTypeError,
    FileSizeExceededError,
    NepalSMSException,
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

    except Exception as e:
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

    except Exception as e:
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

    except Exception as e:
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
    Stores locally in development, S3 in production.

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

    # Generate unique filename
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"photos/users/{current_user.id}/{uuid.uuid4().hex}.{ext}"

    if settings.s3_bucket_name and not settings.is_development:
        # Production: Upload to S3
        def upload_to_s3() -> None:
            import boto3
            s3_client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
            s3_client.put_object(
                Bucket=settings.s3_bucket_name,
                Key=filename,
                Body=contents,
                ContentType=file.content_type,
            )

        await asyncio.to_thread(upload_to_s3)

        if settings.cloudfront_domain:
            photo_url = f"https://{settings.cloudfront_domain}/{filename}"
        else:
            photo_url = f"https://{settings.s3_bucket_name}.s3.{settings.aws_region}.amazonaws.com/{filename}"
    else:
        # Development: Store locally
        import os
        upload_dir = os.path.join("uploads", "photos", "users", str(current_user.id))
        local_path = os.path.join(upload_dir, f"{uuid.uuid4().hex}.{ext}")
        def write_local_file() -> None:
            os.makedirs(upload_dir, exist_ok=True)
            with open(local_path, "wb") as destination:
                destination.write(contents)

        await asyncio.to_thread(write_local_file)

        photo_url = f"/uploads/{local_path.replace(os.sep, '/')}"

    # Update user profile
    user_service = UserService(db)
    await user_service.update_photo(current_user.id, photo_url)

    return UploadPhotoResponse(photo_url=photo_url)
