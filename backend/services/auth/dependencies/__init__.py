"""
Nepal School Management System - Auth Dependencies
FastAPI dependencies for authentication and authorization
"""

from services.auth.dependencies.auth import (
    get_current_user,
    get_current_active_user,
    require_permission,
    require_role,
    require_any_role,
    require_all_permissions,
    oauth2_scheme,
)

__all__ = [
    "get_current_user",
    "get_current_active_user",
    "require_permission",
    "require_role",
    "require_any_role",
    "require_all_permissions",
    "oauth2_scheme",
]
