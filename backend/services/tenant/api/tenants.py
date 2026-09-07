"""
Nepal School Management System - Tenant API Routes
School/tenant management endpoints
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.base import get_db
from shared.schemas.responses import success_response, error_response
from shared.utils.exceptions import (
    TenantNotFoundError,
    DuplicateRecordError,
    FeatureNotAvailableError,
)
from services.auth.dependencies.auth import (
    get_current_active_user,
    require_role,
    require_permission,
)
from services.auth.models.user import User
from services.tenant.schemas.tenant import (
    TenantCreate,
    TenantUpdate,
    TenantResponse,
    TenantListResponse,
    HSToggleRequest,
    HSToggleResponse,
    SubscriptionResponse,
)
from services.tenant.services.tenant_service import TenantService

router = APIRouter()


@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_data: TenantCreate,
    current_user: User = Depends(require_permission("tenant:create")),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new school (onboarding).

    Requires: tenant:create permission (super_admin)

    Status Codes:
        - 201: Tenant created
        - 409: EMIS code already exists
    """
    try:
        service = TenantService(db)
        tenant = await service.create_tenant(tenant_data, created_by=current_user.id)

        return TenantResponse(
            id=tenant.id,
            name_en=tenant.name_en,
            name_np=tenant.name_np,
            emis_code=tenant.emis_code,
            registration_number=tenant.registration_number,
            school_type=tenant.school_type.value,
            school_level=tenant.school_level.value,
            hs_enabled=tenant.hs_enabled,
            phone=tenant.phone,
            email=tenant.email,
            website=tenant.website,
            province=tenant.province.value if tenant.province else None,
            district=tenant.district,
            municipality=tenant.municipality,
            ward_no=tenant.ward_no,
            tole=tenant.tole,
            status=tenant.status.value,
            subscription_plan=tenant.subscription_plan.value,
            subscription_end=tenant.subscription_end,
            academic_year_bs=tenant.academic_year_bs,
            max_students=tenant.max_students,
            max_staff=tenant.max_staff,
            logo_url=tenant.logo_url,
            primary_color=tenant.primary_color,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    except DuplicateRecordError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_response(str(e), "DUPLICATE_EMIS_CODE"),
        )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get school/tenant details.

    Status Codes:
        - 200: Success
        - 404: Tenant not found
    """
    try:
        service = TenantService(db)
        tenant = await service.get_tenant(tenant_id)

        return TenantResponse(
            id=tenant.id,
            name_en=tenant.name_en,
            name_np=tenant.name_np,
            emis_code=tenant.emis_code,
            registration_number=tenant.registration_number,
            school_type=tenant.school_type.value,
            school_level=tenant.school_level.value,
            hs_enabled=tenant.hs_enabled,
            phone=tenant.phone,
            email=tenant.email,
            website=tenant.website,
            province=tenant.province.value if tenant.province else None,
            district=tenant.district,
            municipality=tenant.municipality,
            ward_no=tenant.ward_no,
            tole=tenant.tole,
            status=tenant.status.value,
            subscription_plan=tenant.subscription_plan.value,
            subscription_end=tenant.subscription_end,
            academic_year_bs=tenant.academic_year_bs,
            max_students=tenant.max_students,
            max_staff=tenant.max_staff,
            logo_url=tenant.logo_url,
            primary_color=tenant.primary_color,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    except TenantNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "TENANT_NOT_FOUND"),
        )


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID,
    tenant_data: TenantUpdate,
    current_user: User = Depends(require_permission("tenant:update")),
    db: AsyncSession = Depends(get_db)
):
    """
    Update school/tenant details.

    Requires: tenant:update permission

    Status Codes:
        - 200: Updated
        - 404: Tenant not found
    """
    try:
        service = TenantService(db)
        tenant = await service.update_tenant(tenant_id, tenant_data)

        return TenantResponse(
            id=tenant.id,
            name_en=tenant.name_en,
            name_np=tenant.name_np,
            emis_code=tenant.emis_code,
            registration_number=tenant.registration_number,
            school_type=tenant.school_type.value,
            school_level=tenant.school_level.value,
            hs_enabled=tenant.hs_enabled,
            phone=tenant.phone,
            email=tenant.email,
            website=tenant.website,
            province=tenant.province.value if tenant.province else None,
            district=tenant.district,
            municipality=tenant.municipality,
            ward_no=tenant.ward_no,
            tole=tenant.tole,
            status=tenant.status.value,
            subscription_plan=tenant.subscription_plan.value,
            subscription_end=tenant.subscription_end,
            academic_year_bs=tenant.academic_year_bs,
            max_students=tenant.max_students,
            max_staff=tenant.max_staff,
            logo_url=tenant.logo_url,
            primary_color=tenant.primary_color,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
        )

    except TenantNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "TENANT_NOT_FOUND"),
        )


@router.get("/", response_model=TenantListResponse)
async def list_tenants(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    province: Optional[str] = Query(default=None),
    current_user: User = Depends(require_role("super_admin")),
    db: AsyncSession = Depends(get_db)
):
    """
    List all schools/tenants (Super Admin only).

    Supports pagination, search, and filters.

    Status Codes:
        - 200: Success
        - 403: Not super admin
    """
    from services.tenant.models.tenant import TenantStatus as TS

    service = TenantService(db)
    status_enum = TS(status_filter) if status_filter else None

    tenants, total = await service.list_tenants(
        page=page,
        limit=limit,
        search=search,
        status_filter=status_enum,
        province=province,
    )

    return TenantListResponse(
        tenants=[
            TenantResponse(
                id=t.id,
                name_en=t.name_en,
                name_np=t.name_np,
                emis_code=t.emis_code,
                registration_number=t.registration_number,
                school_type=t.school_type.value,
                school_level=t.school_level.value,
                hs_enabled=t.hs_enabled,
                phone=t.phone,
                email=t.email,
                website=t.website,
                province=t.province.value if t.province else None,
                district=t.district,
                municipality=t.municipality,
                ward_no=t.ward_no,
                tole=t.tole,
                status=t.status.value,
                subscription_plan=t.subscription_plan.value,
                subscription_end=t.subscription_end,
                academic_year_bs=t.academic_year_bs,
                max_students=t.max_students,
                max_staff=t.max_staff,
                logo_url=t.logo_url,
                primary_color=t.primary_color,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tenants
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.patch("/{tenant_id}/settings/higher-secondary", response_model=HSToggleResponse)
async def toggle_higher_secondary(
    tenant_id: uuid.UUID,
    hs_data: HSToggleRequest,
    current_user: User = Depends(require_permission("tenant:hs_toggle")),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggle Grade 11-12 (Higher Secondary) feature.

    Requires: tenant:hs_toggle permission

    Status Codes:
        - 200: HS toggled
        - 403: Feature not available in plan
        - 404: Tenant not found
    """
    try:
        service = TenantService(db)
        tenant = await service.toggle_higher_secondary(
            tenant_id=tenant_id,
            enable=hs_data.enable,
            faculties=hs_data.faculties
        )

        action = "enabled" if hs_data.enable else "disabled"
        return HSToggleResponse(
            hs_enabled=tenant.hs_enabled,
            message=f"Higher Secondary {action} successfully",
            faculties=hs_data.faculties if hs_data.enable else None,
        )

    except TenantNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "TENANT_NOT_FOUND"),
        )

    except FeatureNotAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_response(str(e), "FEATURE_NOT_AVAILABLE"),
        )


@router.get("/{tenant_id}/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    tenant_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get subscription details for a school.

    Status Codes:
        - 200: Success
        - 404: Tenant not found
    """
    try:
        service = TenantService(db)
        details = await service.get_subscription_details(tenant_id)

        return SubscriptionResponse(**details)

    except TenantNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_response(str(e), "TENANT_NOT_FOUND"),
        )
