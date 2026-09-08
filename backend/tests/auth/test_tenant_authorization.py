import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from services.auth.dependencies.auth import require_tenant_permission


def make_user(*, school_id, permissions=(), roles=()):
    return SimpleNamespace(
        school_id=school_id,
        has_permission=lambda permission: permission in permissions or "*:*" in permissions,
        has_role=lambda role: role in roles,
    )


@pytest.mark.asyncio
async def test_school_user_can_access_own_tenant():
    school_id = uuid.uuid4()
    checker = require_tenant_permission("tenant:read")
    user = make_user(school_id=school_id, permissions={"tenant:read"}, roles={"school_admin"})

    assert await checker(tenant_id=school_id, current_user=user) is user


@pytest.mark.asyncio
async def test_school_user_cannot_access_another_tenant():
    checker = require_tenant_permission("tenant:read")
    user = make_user(
        school_id=uuid.uuid4(),
        permissions={"tenant:read"},
        roles={"school_admin"},
    )

    with pytest.raises(HTTPException) as error:
        await checker(tenant_id=uuid.uuid4(), current_user=user)

    assert error.value.status_code == 403
    assert error.value.detail["error"]["code"] == "TENANT_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_super_admin_can_access_any_tenant():
    checker = require_tenant_permission("tenant:read")
    user = make_user(
        school_id=uuid.uuid4(),
        permissions={"*:*"},
        roles={"super_admin"},
    )

    assert await checker(tenant_id=uuid.uuid4(), current_user=user) is user
