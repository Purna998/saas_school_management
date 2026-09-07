"""
Nepal School Management System - Seed Demo School and Super Admin
Creates a demo school tenant and super admin user for testing
"""

import asyncio
import uuid
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from shared.config.settings import settings
from services.auth.models.user import User, UserStatus
from services.auth.models.role import Role
from services.auth.utils.password import hash_password


# Demo school data (mock tenant - actual tenant table will be created later)
DEMO_SCHOOL_ID = uuid.UUID("12345678-1234-1234-1234-123456789012")

# Demo super admin
SUPER_ADMIN = {
    "email": "admin@nepalsms.com",
    "password": "Admin@123!",  # Change this in production!
    "full_name_en": "System Administrator",
    "full_name_np": "प्रणाली प्रशासक",
    "phone": "+977-9841234567",
    "school_id": DEMO_SCHOOL_ID,
    "role_code": "super_admin",
}

# Demo school admin
DEMO_SCHOOL_ADMIN = {
    "email": "principal@demo.school.np",
    "password": "School@123!",
    "full_name_en": "Ram Prasad Sharma",
    "full_name_np": "राम प्रसाद शर्मा",
    "phone": "+977-9851234567",
    "school_id": DEMO_SCHOOL_ID,
    "role_code": "school_admin",
}

# Demo teacher
DEMO_TEACHER = {
    "email": "teacher@demo.school.np",
    "password": "Teacher@123!",
    "full_name_en": "Sita Devi Thapa",
    "full_name_np": "सीता देवी थापा",
    "phone": "+977-9861234567",
    "school_id": DEMO_SCHOOL_ID,
    "role_code": "teacher",
}


async def seed_demo_users():
    """Seed demo users"""
    print("Seeding demo school and users...")

    # Create async engine and session
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            # Get roles
            result = await session.execute(select(Role))
            roles = {role.code: role for role in result.scalars().all()}

            if not roles:
                print("✗ No roles found. Please run 001_roles_and_permissions.py first!")
                return

            # Create users
            users_data = [SUPER_ADMIN, DEMO_SCHOOL_ADMIN, DEMO_TEACHER]

            for user_data in users_data:
                # Check if user already exists
                result = await session.execute(
                    select(User).where(User.email == user_data["email"])
                )
                existing_user = result.scalar_one_or_none()

                if existing_user:
                    print(f"  ⊗ User already exists: {user_data['email']}")
                    continue

                # Create user
                user = User(
                    id=uuid.uuid4(),
                    email=user_data["email"],
                    password_hash=hash_password(user_data["password"]),
                    full_name_en=user_data["full_name_en"],
                    full_name_np=user_data.get("full_name_np"),
                    phone=user_data.get("phone"),
                    school_id=user_data["school_id"],
                    status=UserStatus.ACTIVE,
                    email_verified=True,  # Pre-verified for demo
                    mfa_enabled=False,  # Disabled for demo
                )

                # Assign role
                role_code = user_data.get("role_code")
                if role_code and role_code in roles:
                    user.roles.append(roles[role_code])

                session.add(user)
                print(f"  ✓ Created user: {user_data['email']} ({role_code})")

            # Commit all changes
            await session.commit()
            print("\n✓ Demo users seeded successfully!")
            print("\n" + "="*60)
            print("DEMO LOGIN CREDENTIALS:")
            print("="*60)
            print("\n1. Super Admin:")
            print(f"   Email:    {SUPER_ADMIN['email']}")
            print(f"   Password: {SUPER_ADMIN['password']}")
            print("\n2. School Admin:")
            print(f"   Email:    {DEMO_SCHOOL_ADMIN['email']}")
            print(f"   Password: {DEMO_SCHOOL_ADMIN['password']}")
            print("\n3. Teacher:")
            print(f"   Email:    {DEMO_TEACHER['email']}")
            print(f"   Password: {DEMO_TEACHER['password']}")
            print("\n" + "="*60)
            print("⚠️  IMPORTANT: Change these passwords in production!")
            print("="*60 + "\n")

        except Exception as e:
            await session.rollback()
            print(f"\n✗ Error seeding users: {str(e)}")
            raise

        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_demo_users())
