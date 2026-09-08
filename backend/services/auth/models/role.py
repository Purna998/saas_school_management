"""
Nepal School Management System - Role & Permission Models
RBAC (Role-Based Access Control) implementation
"""

import uuid

from sqlalchemy import Column, String, Boolean, Integer, Text, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from shared.database.base import Base
from shared.database.base_model import BaseModel, TimestampMixin


# Association table for many-to-many Role <-> Permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
)


class Role(Base, BaseModel, TimestampMixin):
    """
    Role model for RBAC.

    Predefined roles:
    - super_admin: Full system access (multi-tenant)
    - school_admin: School admin (tenant-scoped)
    - principal: Principal (academic oversight)
    - vice_principal: Vice Principal
    - teacher: Teacher (teaching, attendance, marks)
    - accountant: Accountant (fees, finance) - requires MFA
    - librarian: Librarian (library management)
    - receptionist: Receptionist (front desk)
    - parent: Parent (view-only access to own child data)
    - student: Student (view-only access to own data)
    """

    __tablename__ = "roles"

    # Role identification
    code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Role code (e.g., 'super_admin', 'teacher')"
    )
    name_en = Column(
        String(100),
        nullable=False,
        comment="Role name in English"
    )
    name_np = Column(
        String(100),
        nullable=True,
        comment="Role name in Nepali"
    )
    description = Column(
        Text,
        nullable=True,
        comment="Role description"
    )

    # Configuration
    is_system_role = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="System role (cannot be deleted/modified)"
    )
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Active status"
    )
    requires_mfa = Column(
        Boolean,
        default=False,
        nullable=False,
        comment="Requires MFA for this role (e.g., admin, accountant)"
    )

    # Hierarchy & Priority
    priority = Column(
        Integer,
        default=0,
        nullable=False,
        comment="Role priority/hierarchy (higher = more privileged)"
    )

    # Relationships
    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin"
    )
    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles"
    )

    def __repr__(self):
        return f"<Role(code={self.code}, name={self.name_en})>"

    def get_permissions(self) -> set[str]:
        """Get all permission codes for this role"""
        return {perm.code for perm in self.permissions if perm.is_active}

    def has_permission(self, permission_code: str) -> bool:
        """Check if role has specific permission"""
        return permission_code in self.get_permissions()


class Permission(Base, BaseModel, TimestampMixin):
    """
    Permission model for fine-grained access control.

    Permission naming convention:
    - Format: <resource>:<action>
    - Examples:
        * student:create, student:read, student:update, student:delete
        * exam:create, exam:read, exam:update, exam:delete, exam:publish
        * fee:create, fee:read, fee:collect, fee:refund
        * attendance:create, attendance:read
        * report:generate, report:export
        * tenant:create, tenant:update, tenant:hs_toggle

    Special permissions:
    - *:* (super admin - all permissions)
    - tenant:hs_toggle (enable/disable Grade 11-12)
    """

    __tablename__ = "permissions"

    # Permission identification
    code = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Permission code (e.g., 'student:create')"
    )
    name_en = Column(
        String(100),
        nullable=False,
        comment="Permission name in English"
    )
    name_np = Column(
        String(100),
        nullable=True,
        comment="Permission name in Nepali"
    )
    description = Column(
        Text,
        nullable=True,
        comment="Permission description"
    )

    # Categorization
    resource = Column(
        String(50),
        nullable=False,
        index=True,
        comment="Resource name (e.g., 'student', 'exam', 'fee')"
    )
    action = Column(
        String(50),
        nullable=False,
        comment="Action name (e.g., 'create', 'read', 'update', 'delete')"
    )

    # Configuration
    is_active = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Active status"
    )

    # Relationships
    roles = relationship(
        "Role",
        secondary=role_permissions,
        back_populates="permissions"
    )

    def __repr__(self):
        return f"<Permission(code={self.code})>"


# For backwards compatibility
RolePermission = role_permissions
