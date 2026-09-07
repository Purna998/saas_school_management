"""
Nepal School Management System - Database Setup Script
Master script to setup database, run migrations, and seed data
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from shared.config.settings import settings
from shared.database.base import Base, engine as default_engine

# Import all models to register them
from services.auth.models.user import User, user_roles
from services.auth.models.role import Role, Permission, role_permissions
from services.auth.models.mfa import MFASecret
from services.auth.models.session import UserSession, LoginAttempt


async def create_database():
    """Create database if it doesn't exist"""
    print("="*60)
    print("NEPAL SCHOOL MANAGEMENT SYSTEM - Database Setup")
    print("="*60)
    print("\nStep 1: Creating database...")

    # Extract database name from URL
    db_name = settings.database_url.split("/")[-1].split("?")[0]

    # Connect to postgres database to create our database
    postgres_url = settings.database_url.rsplit("/", 1)[0] + "/postgres"

    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        # Check if database exists
        result = await conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
        )
        exists = result.scalar()

        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"✓ Database '{db_name}' created successfully")
        else:
            print(f"⊗ Database '{db_name}' already exists")

    await engine.dispose()


async def create_tables():
    """Create all tables"""
    print("\nStep 2: Creating tables...")

    async with default_engine.begin() as conn:
        # Drop all tables (for fresh setup)
        # await conn.run_sync(Base.metadata.drop_all)
        # print("  - Dropped existing tables")

        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        print("✓ All tables created successfully")


async def seed_data():
    """Run seed scripts"""
    print("\nStep 3: Seeding data...")

    # Import and run seed scripts
    try:
        # Seed roles and permissions
        print("\n  → Running: 001_roles_and_permissions.py")
        sys.path.insert(0, str(Path(__file__).parent / "seeds"))
        import importlib.util

        # Load roles and permissions script
        spec = importlib.util.spec_from_file_location(
            "seed_roles",
            Path(__file__).parent / "seeds" / "001_roles_and_permissions.py"
        )
        seed_roles_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_roles_module)
        await seed_roles_module.seed_roles_and_permissions()

        # Load demo users script
        print("\n  → Running: 002_demo_school_and_admin.py")
        spec = importlib.util.spec_from_file_location(
            "seed_users",
            Path(__file__).parent / "seeds" / "002_demo_school_and_admin.py"
        )
        seed_users_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seed_users_module)
        await seed_users_module.seed_demo_users()

    except Exception as e:
        print(f"\n  ⚠️  Import method failed: {str(e)}")
        print("  Falling back to subprocess execution...")
        # Fallback: run seed scripts directly
        print("\n  ⚠️  Import failed, running seed scripts directly...")

        import subprocess
        import os

        # Run roles and permissions
        print("\n  → Running: 001_roles_and_permissions.py")
        result = subprocess.run(
            [sys.executable, "scripts/seeds/001_roles_and_permissions.py"],
            cwd=Path(__file__).parent.parent,
            capture_output=False
        )

        if result.returncode == 0:
            # Run demo users
            print("\n  → Running: 002_demo_school_and_admin.py")
            subprocess.run(
                [sys.executable, "scripts/seeds/002_demo_school_and_admin.py"],
                cwd=Path(__file__).parent.parent,
                capture_output=False
            )


async def verify_setup():
    """Verify database setup"""
    print("\nStep 4: Verifying setup...")

    from sqlalchemy import select

    async with default_engine.connect() as conn:
        # Count roles
        result = await conn.execute(text("SELECT COUNT(*) FROM roles"))
        role_count = result.scalar()
        print(f"  ✓ Roles: {role_count}")

        # Count permissions
        result = await conn.execute(text("SELECT COUNT(*) FROM permissions"))
        perm_count = result.scalar()
        print(f"  ✓ Permissions: {perm_count}")

        # Count users
        result = await conn.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()
        print(f"  ✓ Users: {user_count}")

    print("\n" + "="*60)
    print("✓ Database setup completed successfully!")
    print("="*60)


async def main():
    """Main setup function"""
    try:
        await create_database()
        await create_tables()
        await seed_data()
        await verify_setup()

        print("\n📝 Next Steps:")
        print("  1. Start Redis: docker-compose up -d redis")
        print("  2. Start Auth Service: uvicorn services.auth.main:app --reload --port 8001")
        print("  3. Access API Docs: http://localhost:8001/docs")
        print("  4. Try logging in with demo credentials")
        print()

    except Exception as e:
        print(f"\n✗ Setup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await default_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
