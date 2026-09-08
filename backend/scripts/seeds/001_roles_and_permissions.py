"""
Nepal School Management System - Seed Roles and Permissions
Creates default roles and permissions for the system
"""

import asyncio
import uuid
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy import select
from sqlalchemy.orm import selectinload, sessionmaker

from shared.config.settings import settings
from services.auth.models.role import Role, Permission


# Define default roles
DEFAULT_ROLES = [
    {
        "code": "super_admin",
        "name_en": "Super Administrator",
        "name_np": "प्रमुख प्रशासक",
        "description": "Full system access across all tenants",
        "is_system_role": True,
        "requires_mfa": True,
        "priority": 100,
    },
    {
        "code": "school_admin",
        "name_en": "School Administrator",
        "name_np": "विद्यालय प्रशासक",
        "description": "School-level administrator with full tenant access",
        "is_system_role": True,
        "requires_mfa": True,
        "priority": 90,
    },
    {
        "code": "principal",
        "name_en": "Principal",
        "name_np": "प्रधानाध्यापक",
        "description": "School principal with academic oversight",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 80,
    },
    {
        "code": "vice_principal",
        "name_en": "Vice Principal",
        "name_np": "उप-प्रधानाध्यापक",
        "description": "Assistant principal",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 75,
    },
    {
        "code": "teacher",
        "name_en": "Teacher",
        "name_np": "शिक्षक",
        "description": "Teaching staff with student and academic management",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 50,
    },
    {
        "code": "accountant",
        "name_en": "Accountant",
        "name_np": "लेखाकार",
        "description": "Financial management and fee collection",
        "is_system_role": True,
        "requires_mfa": True,
        "priority": 60,
    },
    {
        "code": "librarian",
        "name_en": "Librarian",
        "name_np": "पुस्तकालयाध्यक्ष",
        "description": "Library management",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 40,
    },
    {
        "code": "receptionist",
        "name_en": "Receptionist",
        "name_np": "स्वागतकर्ता",
        "description": "Front desk and visitor management",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 30,
    },
    {
        "code": "transport_manager",
        "name_en": "Transport Manager",
        "description": "School transport management",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 40,
    },
    {
        "code": "hostel_manager",
        "name_en": "Hostel Manager",
        "description": "School hostel management",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 40,
    },
    {
        "code": "inventory_manager",
        "name_en": "Inventory Manager",
        "description": "School inventory management",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 40,
    },
    {
        "code": "parent",
        "name_en": "Parent",
        "name_np": "अभिभावक",
        "description": "Parent/guardian with read-only access to own child data",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 10,
    },
    {
        "code": "student",
        "name_en": "Student",
        "name_np": "विद्यार्थी",
        "description": "Student with read-only access to own data",
        "is_system_role": True,
        "requires_mfa": False,
        "priority": 5,
    },
]


# Define default permissions
DEFAULT_PERMISSIONS = [
    # System permissions
    {"code": "*:*", "name_en": "Super Admin", "name_np": "सुपर एडमिन", "resource": "system", "action": "all"},

    # Tenant/School permissions
    {"code": "tenant:create", "name_en": "Create School", "name_np": "विद्यालय बनाउनुहोस्", "resource": "tenant", "action": "create"},
    {"code": "tenant:read", "name_en": "View School", "name_np": "विद्यालय हेर्नुहोस्", "resource": "tenant", "action": "read"},
    {"code": "tenant:update", "name_en": "Update School", "name_np": "विद्यालय अद्यावधिक गर्नुहोस्", "resource": "tenant", "action": "update"},
    {"code": "tenant:delete", "name_en": "Delete School", "name_np": "विद्यालय मेटाउनुहोस्", "resource": "tenant", "action": "delete"},
    {"code": "tenant:hs_toggle", "name_en": "Toggle Grade 11-12", "name_np": "कक्षा ११-१२ टगल गर्नुहोस्", "resource": "tenant", "action": "hs_toggle"},

    # Student permissions
    {"code": "student:create", "name_en": "Add Student", "name_np": "विद्यार्थी थप्नुहोस्", "resource": "student", "action": "create"},
    {"code": "student:read", "name_en": "View Student", "name_np": "विद्यार्थी हेर्नुहोस्", "resource": "student", "action": "read"},
    {"code": "student:update", "name_en": "Update Student", "name_np": "विद्यार्थी अद्यावधिक गर्नुहोस्", "resource": "student", "action": "update"},
    {"code": "student:delete", "name_en": "Delete Student", "name_np": "विद्यार्थी मेटाउनुहोस्", "resource": "student", "action": "delete"},
    {"code": "student:import", "name_en": "Import Students", "name_np": "विद्यार्थीहरू आयात गर्नुहोस्", "resource": "student", "action": "import"},
    {"code": "student:export", "name_en": "Export Students", "name_np": "विद्यार्थीहरू निर्यात गर्नुहोस्", "resource": "student", "action": "export"},

    # Attendance permissions
    {"code": "attendance:create", "name_en": "Mark Attendance", "name_np": "उपस्थिति चिन्ह लगाउनुहोस्", "resource": "attendance", "action": "create"},
    {"code": "attendance:read", "name_en": "View Attendance", "name_np": "उपस्थिति हेर्नुहोस्", "resource": "attendance", "action": "read"},
    {"code": "attendance:update", "name_en": "Update Attendance", "name_np": "उपस्थिति अद्यावधिक गर्नुहोस्", "resource": "attendance", "action": "update"},
    {"code": "attendance:report", "name_en": "Attendance Reports", "name_np": "उपस्थिति रिपोर्टहरू", "resource": "attendance", "action": "report"},

    # Exam permissions
    {"code": "exam:create", "name_en": "Create Exam", "name_np": "परीक्षा सिर्जना गर्नुहोस्", "resource": "exam", "action": "create"},
    {"code": "exam:read", "name_en": "View Exam", "name_np": "परीक्षा हेर्नुहोस्", "resource": "exam", "action": "read"},
    {"code": "exam:update", "name_en": "Update Exam", "name_np": "परीक्षा अद्यावधिक गर्नुहोस्", "resource": "exam", "action": "update"},
    {"code": "exam:delete", "name_en": "Delete Exam", "name_np": "परीक्षा मेटाउनुहोस्", "resource": "exam", "action": "delete"},
    {"code": "exam:publish", "name_en": "Publish Results", "name_np": "नतिजा प्रकाशित गर्नुहोस्", "resource": "exam", "action": "publish"},
    {"code": "exam:lock", "name_en": "Lock Exam", "name_np": "परीक्षा लक गर्नुहोस्", "resource": "exam", "action": "lock"},

    # Marks permissions
    {"code": "marks:create", "name_en": "Enter Marks", "name_np": "अंक प्रविष्ट गर्नुहोस्", "resource": "marks", "action": "create"},
    {"code": "marks:read", "name_en": "View Marks", "name_np": "अंक हेर्नुहोस्", "resource": "marks", "action": "read"},
    {"code": "marks:update", "name_en": "Update Marks", "name_np": "अंक अद्यावधिक गर्नुहोस्", "resource": "marks", "action": "update"},

    # Fee permissions
    {"code": "fee:create", "name_en": "Setup Fees", "name_np": "शुल्क सेटअप गर्नुहोस्", "resource": "fee", "action": "create"},
    {"code": "fee:read", "name_en": "View Fees", "name_np": "शुल्क हेर्नुहोस्", "resource": "fee", "action": "read"},
    {"code": "fee:collect", "name_en": "Collect Fees", "name_np": "शुल्क सङ्कलन गर्नुहोस्", "resource": "fee", "action": "collect"},
    {"code": "fee:refund", "name_en": "Refund Fees", "name_np": "शुल्क फिर्ता गर्नुहोस्", "resource": "fee", "action": "refund"},
    {"code": "fee:report", "name_en": "Fee Reports", "name_np": "शुल्क रिपोर्टहरू", "resource": "fee", "action": "report"},

    # Staff permissions
    {"code": "staff:create", "name_en": "Add Staff", "name_np": "कर्मचारी थप्नुहोस्", "resource": "staff", "action": "create"},
    {"code": "staff:read", "name_en": "View Staff", "name_np": "कर्मचारी हेर्नुहोस्", "resource": "staff", "action": "read"},
    {"code": "staff:update", "name_en": "Update Staff", "name_np": "कर्मचारी अद्यावधिक गर्नुहोस्", "resource": "staff", "action": "update"},
    {"code": "staff:delete", "name_en": "Delete Staff", "name_np": "कर्मचारी मेटाउनुहोस्", "resource": "staff", "action": "delete"},

    # Library permissions
    {"code": "library:create", "name_en": "Add Books", "name_np": "पुस्तक थप्नुहोस्", "resource": "library", "action": "create"},
    {"code": "library:read", "name_en": "View Books", "name_np": "पुस्तक हेर्नुहोस्", "resource": "library", "action": "read"},
    {"code": "library:update", "name_en": "Update Books", "name_np": "पुस्तक अद्यावधिक गर्नुहोस्", "resource": "library", "action": "update"},
    {"code": "library:issue", "name_en": "Issue Books", "name_np": "पुस्तक जारी गर्नुहोस्", "resource": "library", "action": "issue"},
    {"code": "library:return", "name_en": "Return Books", "name_np": "पुस्तक फिर्ता गर्नुहोस्", "resource": "library", "action": "return"},

    # Report permissions
    {"code": "report:generate", "name_en": "Generate Reports", "name_np": "रिपोर्ट उत्पन्न गर्नुहोस्", "resource": "report", "action": "generate"},
    {"code": "report:export", "name_en": "Export Reports", "name_np": "रिपोर्ट निर्यात गर्नुहोस्", "resource": "report", "action": "export"},
    {"code": "report:emis", "name_en": "EMIS Reports", "name_np": "EMIS रिपोर्टहरू", "resource": "report", "action": "emis"},
    # Permissions used by the remaining school-management services
    {"code": "academic:create", "name_en": "Manage Academic Structure", "resource": "academic", "action": "create"},
    {"code": "academic:read", "name_en": "View Academic Structure", "resource": "academic", "action": "read"},
    {"code": "staff:leave:create", "name_en": "Request Staff Leave", "resource": "staff", "action": "leave_create"},
    {"code": "staff:leave:approve", "name_en": "Approve Staff Leave", "resource": "staff", "action": "leave_approve"},
    {"code": "staff:attendance:mark", "name_en": "Mark Staff Attendance", "resource": "staff", "action": "attendance_mark"},
    {"code": "staff:attendance:read", "name_en": "View Staff Attendance", "resource": "staff", "action": "attendance_read"},
    {"code": "transport:create", "name_en": "Manage Transport", "resource": "transport", "action": "create"},
    {"code": "transport:read", "name_en": "View Transport", "resource": "transport", "action": "read"},
    {"code": "transport:delete", "name_en": "Remove Transport Assignments", "resource": "transport", "action": "delete"},
    {"code": "hostel:create", "name_en": "Manage Hostel Rooms", "resource": "hostel", "action": "create"},
    {"code": "hostel:read", "name_en": "View Hostel", "resource": "hostel", "action": "read"},
    {"code": "hostel:allocate", "name_en": "Allocate Hostel Rooms", "resource": "hostel", "action": "allocate"},
    {"code": "inventory:create", "name_en": "Add Inventory", "resource": "inventory", "action": "create"},
    {"code": "inventory:read", "name_en": "View Inventory", "resource": "inventory", "action": "read"},
    {"code": "inventory:update", "name_en": "Update Inventory", "resource": "inventory", "action": "update"},
    {"code": "report:read", "name_en": "View Reports", "resource": "report", "action": "read"},
    {"code": "report:delete", "name_en": "Delete Reports", "resource": "report", "action": "delete"},
    {"code": "communication:read", "name_en": "View Communications", "resource": "communication", "action": "read"},
    {"code": "communication:email:send", "name_en": "Send Email", "resource": "communication", "action": "email_send"},
    {"code": "communication:sms:send", "name_en": "Send SMS", "resource": "communication", "action": "sms_send"},
    {"code": "communication:sms:bulk", "name_en": "Send Bulk SMS", "resource": "communication", "action": "sms_bulk"},
    {"code": "calendar:read", "name_en": "View Calendar", "resource": "calendar", "action": "read"},
    {"code": "calendar:update", "name_en": "Manage Calendar", "resource": "calendar", "action": "update"},
]


# Role-Permission mappings
ROLE_PERMISSIONS = {
    "super_admin": ["*:*"],  # All permissions

    "school_admin": [
        "tenant:read", "tenant:update", "tenant:hs_toggle",
        "student:create", "student:read", "student:update", "student:delete", "student:import", "student:export",
        "attendance:create", "attendance:read", "attendance:update", "attendance:report",
        "exam:create", "exam:read", "exam:update", "exam:delete", "exam:publish", "exam:lock",
        "marks:create", "marks:read", "marks:update",
        "fee:create", "fee:read", "fee:collect", "fee:refund", "fee:report",
        "staff:create", "staff:read", "staff:update", "staff:delete",
        "staff:leave:create", "staff:leave:approve", "staff:attendance:mark", "staff:attendance:read",
        "academic:create", "academic:read",
        "library:create", "library:read", "library:update", "library:issue", "library:return",
        "transport:create", "transport:read", "transport:delete",
        "hostel:create", "hostel:read", "hostel:allocate",
        "inventory:create", "inventory:read", "inventory:update",
        "report:generate", "report:read", "report:delete", "report:export", "report:emis",
        "communication:read", "communication:email:send", "communication:sms:send", "communication:sms:bulk",
        "calendar:read", "calendar:update",
    ],

    "principal": [
        "tenant:read",
        "student:create", "student:read", "student:update", "student:import", "student:export",
        "attendance:read", "attendance:report",
        "exam:create", "exam:read", "exam:update", "exam:publish", "exam:lock",
        "marks:read",
        "fee:read", "fee:report",
        "staff:read",
        "academic:create", "academic:read",
        "communication:read", "communication:email:send", "communication:sms:send",
        "calendar:read", "calendar:update",
        "report:generate", "report:read", "report:export", "report:emis",
    ],

    "vice_principal": [
        "tenant:read",
        "student:read", "student:update",
        "attendance:create", "attendance:read", "attendance:update", "attendance:report",
        "exam:read",
        "marks:read",
        "report:generate",
    ],

    "teacher": [
        "student:read",
        "attendance:create", "attendance:read", "attendance:update",
        "exam:read",
        "marks:create", "marks:read", "marks:update",
        "academic:read", "communication:read", "calendar:read",
    ],

    "accountant": [
        "student:read",
        "fee:create", "fee:read", "fee:collect", "fee:refund", "fee:report",
        "report:generate",
    ],

    "librarian": [
        "student:read",
        "library:create", "library:read", "library:update", "library:issue", "library:return",
    ],

    "transport_manager": ["transport:create", "transport:read", "transport:delete"],
    "hostel_manager": ["hostel:create", "hostel:read", "hostel:allocate"],
    "inventory_manager": ["inventory:create", "inventory:read", "inventory:update"],

    "receptionist": [
        "student:read",
        "attendance:read",
    ],

    "parent": [
        "student:read",  # Own child only
        "attendance:read",  # Own child only
        "exam:read",  # Own child only
        "marks:read",  # Own child only
        "fee:read",  # Own child only
    ],

    "student": [
        "attendance:read",  # Own only
        "exam:read",  # Own only
        "marks:read",  # Own only
    ],
}


async def seed_roles_and_permissions():
    """Seed roles and permissions"""
    print("Seeding roles and permissions...")

    # Create async engine and session
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Synchronize instead of returning early so upgrades add newly
            # introduced roles and permissions to an existing database.
            print("Synchronizing permissions...")
            existing_permissions = (await session.execute(select(Permission))).scalars().all()
            permissions_map = {permission.code: permission for permission in existing_permissions}
            for perm_data in DEFAULT_PERMISSIONS:
                permission = permissions_map.get(perm_data["code"])
                if permission is None:
                    permission = Permission(id=uuid.uuid4(), code=perm_data["code"])
                    session.add(permission)
                    permissions_map[perm_data["code"]] = permission
                permission.name_en = perm_data["name_en"]
                permission.name_np = perm_data.get("name_np")
                permission.description = perm_data.get("description")
                permission.resource = perm_data["resource"]
                permission.action = perm_data["action"]
                permission.is_active = True

            await session.flush()
            print(f"[OK] Synchronized {len(DEFAULT_PERMISSIONS)} permissions")

            print("\nSynchronizing roles...")
            existing_roles = (
                await session.execute(select(Role).options(selectinload(Role.permissions)))
            ).scalars().unique().all()
            roles_map = {role.code: role for role in existing_roles}
            for role_data in DEFAULT_ROLES:
                role = roles_map.get(role_data["code"])
                if role is None:
                    role = Role(id=uuid.uuid4(), code=role_data["code"])
                    session.add(role)
                role.name_en = role_data["name_en"]
                role.name_np = role_data.get("name_np")
                role.description = role_data.get("description")
                role.is_system_role = role_data.get("is_system_role", False)
                role.is_active = True
                role.requires_mfa = role_data.get("requires_mfa", False)
                role.priority = role_data.get("priority", 0)
                role.permissions = [
                    permissions_map[permission_code]
                    for permission_code in ROLE_PERMISSIONS.get(role_data["code"], [])
                    if permission_code in permissions_map
                ]

            await session.flush()
            print(f"[OK] Synchronized {len(DEFAULT_ROLES)} roles")

            print("\nAssigning permissions to roles...")
            for role_code, permission_codes in ROLE_PERMISSIONS.items():
                print(f"  [OK] {role_code}: {len(permission_codes)} permissions")

            # Commit all changes
            await session.commit()
            print("\n[OK] All roles and permissions seeded successfully!")

        except Exception as e:
            await session.rollback()
            print(f"\n[ERROR] Error seeding data: {str(e)}")
            raise

        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_roles_and_permissions())
