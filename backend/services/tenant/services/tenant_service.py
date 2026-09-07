"""
Nepal School Management System - Tenant Service
School/tenant management business logic
"""

import uuid
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from shared.utils.exceptions import (
    RecordNotFoundError,
    DuplicateRecordError,
    TenantNotFoundError,
    TenantInactiveError,
    HSNotEnabledError,
    FeatureNotAvailableError,
)
from services.tenant.models.tenant import (
    Tenant,
    TenantStatus,
    SubscriptionPlan,
    SchoolType,
    SchoolLevel,
    Province,
)
from services.tenant.schemas.tenant import TenantCreate, TenantUpdate

logger = logging.getLogger(__name__)

PLAN_FEATURES = {
    SubscriptionPlan.FREE: {
        "max_students": 100,
        "max_staff": 10,
        "max_storage_gb": 1,
        "features": ["basic_attendance", "basic_marks", "student_profiles"],
    },
    SubscriptionPlan.BASIC: {
        "max_students": 300,
        "max_staff": 30,
        "max_storage_gb": 5,
        "features": ["attendance", "marks", "student_profiles", "sms_notifications", "fee_management"],
    },
    SubscriptionPlan.STANDARD: {
        "max_students": 500,
        "max_staff": 50,
        "max_storage_gb": 10,
        "features": ["attendance", "marks", "student_profiles", "sms_notifications",
                     "fee_management", "library", "reports", "hs_toggle"],
    },
    SubscriptionPlan.PREMIUM: {
        "max_students": 1500,
        "max_staff": 150,
        "max_storage_gb": 50,
        "features": ["attendance", "marks", "student_profiles", "sms_notifications",
                     "fee_management", "library", "reports", "hs_toggle",
                     "transport", "hostel", "inventory", "bulk_sms", "api_access"],
    },
    SubscriptionPlan.ENTERPRISE: {
        "max_students": 99999,
        "max_staff": 9999,
        "max_storage_gb": 500,
        "features": ["all"],
    },
}


class TenantService:
    """Tenant/school management service"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_tenant(self, data: TenantCreate, created_by: Optional[uuid.UUID] = None) -> Tenant:
        """
        Create a new school/tenant (onboarding).

        Args:
            data: Tenant creation data
            created_by: User ID who created the tenant

        Returns:
            Created Tenant object

        Raises:
            DuplicateRecordError: If EMIS code already exists
        """
        # Check duplicate EMIS code
        if data.emis_code:
            result = await self.db.execute(
                select(Tenant).where(Tenant.emis_code == data.emis_code)
            )
            if result.scalar_one_or_none():
                raise DuplicateRecordError("Tenant", "emis_code", data.emis_code)

        tenant = Tenant(
            id=uuid.uuid4(),
            name_en=data.name_en,
            name_np=data.name_np,
            emis_code=data.emis_code,
            registration_number=data.registration_number,
            school_type=SchoolType(data.school_type) if data.school_type else SchoolType.INSTITUTIONAL,
            school_level=SchoolLevel(data.school_level) if data.school_level else SchoolLevel.SECONDARY,
            phone=data.phone,
            email=data.email,
            website=data.website,
            province=Province(data.province) if data.province else None,
            district=data.district,
            municipality=data.municipality,
            ward_no=data.ward_no,
            tole=data.tole,
            status=TenantStatus.TRIAL,
            subscription_plan=SubscriptionPlan.FREE,
            trial_ends_at=datetime.utcnow() + timedelta(days=30),
            max_students=PLAN_FEATURES[SubscriptionPlan.FREE]["max_students"],
            max_staff=PLAN_FEATURES[SubscriptionPlan.FREE]["max_staff"],
            max_storage_gb=PLAN_FEATURES[SubscriptionPlan.FREE]["max_storage_gb"],
            onboarded_at=datetime.utcnow(),
            onboarded_by=created_by,
            settings_json={},
        )

        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)

        logger.info(f"Tenant created: {tenant.name_en} (ID: {tenant.id})")
        return tenant

    async def get_tenant(self, tenant_id: uuid.UUID) -> Tenant:
        """Get tenant by ID"""
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()

        if not tenant:
            raise TenantNotFoundError(str(tenant_id))

        return tenant

    async def update_tenant(self, tenant_id: uuid.UUID, data: TenantUpdate) -> Tenant:
        """Update tenant details"""
        tenant = await self.get_tenant(tenant_id)

        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            if value is not None:
                setattr(tenant, field, value)

        await self.db.commit()
        await self.db.refresh(tenant)

        logger.info(f"Tenant updated: {tenant.name_en}")
        return tenant

    async def list_tenants(
        self,
        page: int = 1,
        limit: int = 20,
        search: Optional[str] = None,
        status_filter: Optional[TenantStatus] = None,
        province: Optional[str] = None,
    ) -> Tuple[List[Tenant], int]:
        """List tenants with pagination and filters"""
        query = select(Tenant)

        if search:
            pattern = f"%{search}%"
            query = query.where(
                (Tenant.name_en.ilike(pattern)) |
                (Tenant.name_np.ilike(pattern)) |
                (Tenant.emis_code.ilike(pattern))
            )

        if status_filter:
            query = query.where(Tenant.status == status_filter)

        if province:
            query = query.where(Tenant.province == Province(province))

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Paginate
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(Tenant.created_at.desc())

        result = await self.db.execute(query)
        tenants = result.scalars().all()

        return tenants, total

    async def toggle_higher_secondary(
        self,
        tenant_id: uuid.UUID,
        enable: bool,
        faculties: Optional[List[str]] = None
    ) -> Tenant:
        """
        Enable or disable Grade 11-12 feature.

        Args:
            tenant_id: Tenant UUID
            enable: True to enable, False to disable
            faculties: List of faculty names to create

        Returns:
            Updated tenant

        Raises:
            TenantNotFoundError: If tenant not found
            FeatureNotAvailableError: If plan doesn't support HS
        """
        tenant = await self.get_tenant(tenant_id)

        # Check plan supports HS toggle
        plan_features = PLAN_FEATURES.get(tenant.subscription_plan, {})
        features = plan_features.get("features", [])
        if "hs_toggle" not in features and "all" not in features:
            raise FeatureNotAvailableError("higher_secondary", "standard")

        tenant.hs_enabled = enable
        if enable:
            tenant.hs_enabled_at = datetime.utcnow()
            tenant.school_level = SchoolLevel.HIGHER_SECONDARY
            # Store faculties in settings
            if faculties:
                settings = tenant.settings_json or {}
                settings["hs_faculties"] = faculties
                tenant.settings_json = settings
        else:
            tenant.hs_enabled_at = None
            if tenant.school_level == SchoolLevel.HIGHER_SECONDARY:
                tenant.school_level = SchoolLevel.SECONDARY

        await self.db.commit()
        await self.db.refresh(tenant)

        action = "enabled" if enable else "disabled"
        logger.info(f"Higher Secondary {action} for tenant: {tenant.name_en}")
        return tenant

    async def get_subscription_details(self, tenant_id: uuid.UUID) -> dict:
        """Get subscription details for a tenant"""
        tenant = await self.get_tenant(tenant_id)
        plan_info = PLAN_FEATURES.get(tenant.subscription_plan, PLAN_FEATURES[SubscriptionPlan.FREE])

        return {
            "plan": tenant.subscription_plan.value,
            "status": tenant.status.value,
            "start_date": tenant.subscription_start,
            "end_date": tenant.subscription_end,
            "max_students": tenant.max_students,
            "max_staff": tenant.max_staff,
            "max_storage_gb": tenant.max_storage_gb,
            "features": plan_info.get("features", []),
        }

    async def upgrade_plan(
        self,
        tenant_id: uuid.UUID,
        plan: SubscriptionPlan,
        duration_months: int = 12
    ) -> Tenant:
        """Upgrade tenant subscription plan"""
        tenant = await self.get_tenant(tenant_id)
        plan_info = PLAN_FEATURES[plan]

        tenant.subscription_plan = plan
        tenant.subscription_start = datetime.utcnow()
        tenant.subscription_end = datetime.utcnow() + timedelta(days=30 * duration_months)
        tenant.max_students = plan_info["max_students"]
        tenant.max_staff = plan_info["max_staff"]
        tenant.max_storage_gb = plan_info["max_storage_gb"]

        if tenant.status == TenantStatus.TRIAL:
            tenant.status = TenantStatus.ACTIVE

        await self.db.commit()
        await self.db.refresh(tenant)

        logger.info(f"Tenant {tenant.name_en} upgraded to {plan.value}")
        return tenant
