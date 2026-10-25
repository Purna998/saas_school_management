"""
Nepal School Management System - Database Setup Script
Master script to setup database, run migrations, and seed data
"""

import asyncio
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import inspect, text

from shared.config.settings import settings
from shared.database.base import Base, engine as default_engine

# Register every domain model with the shared metadata. This helper is intended
# for local bootstrap; production schema changes use Alembic.
from shared.database.models import MODEL_MODULES


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
            print(f"[OK] Database '{db_name}' created successfully")
        else:
            print(f"[OK] Database '{db_name}' already exists")

    await engine.dispose()


async def get_table_names() -> set[str]:
    async with default_engine.connect() as connection:
        return set(
            await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
        )


def run_alembic(command: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", command, "head"],
        cwd=Path(__file__).parent.parent,
        check=True,
    )


async def prepare_schema():
    """Migrate a new database or adopt a complete legacy local schema."""
    print("\nStep 2: Applying database migrations...")
    assert MODEL_MODULES
    tables = await get_table_names()

    if tables and "alembic_version" not in tables:
        missing_tables = set(Base.metadata.tables) - tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise RuntimeError(
                "Existing unversioned database is incomplete; refusing to stamp it. "
                f"Missing tables: {missing}"
            )
        run_alembic("stamp")
        print("[OK] Adopted complete legacy schema at the current migration revision")
        return

    run_alembic("upgrade")
    print("[OK] Database migrations applied")


async def seed_data():
    """Run seed scripts"""
    print("\nStep 3: Seeding data...")

    print("\n  -> Running: 001_roles_and_permissions.py")
    sys.path.insert(0, str(Path(__file__).parent / "seeds"))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "seed_roles",
        Path(__file__).parent / "seeds" / "001_roles_and_permissions.py"
    )
    seed_roles_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_roles_module)
    await seed_roles_module.seed_roles_and_permissions()

    print("\n  -> Running: 002_demo_school_and_admin.py")
    spec = importlib.util.spec_from_file_location(
        "seed_users",
        Path(__file__).parent / "seeds" / "002_demo_school_and_admin.py"
    )
    seed_users_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_users_module)
    await seed_users_module.seed_demo_users()


async def verify_setup():
    """Verify database setup"""
    print("\nStep 4: Verifying setup...")

    async with default_engine.connect() as conn:
        # Count roles
        result = await conn.execute(text("SELECT COUNT(*) FROM roles"))
        role_count = result.scalar()
        print(f"  [OK] Roles: {role_count}")

        # Count permissions
        result = await conn.execute(text("SELECT COUNT(*) FROM permissions"))
        perm_count = result.scalar()
        print(f"  [OK] Permissions: {perm_count}")

        # Count users
        result = await conn.execute(text("SELECT COUNT(*) FROM users"))
        user_count = result.scalar()
        print(f"  [OK] Users: {user_count}")

    print("\n" + "="*60)
    print("[OK] Database setup completed successfully!")
    print("="*60)


async def main():
    """Main setup function"""
    try:
        await create_database()
        await prepare_schema()
        await seed_data()
        await verify_setup()

        print("\nNext steps:")
        print("  1. Ensure your local Redis service is running on port 6379")
        print("  2. Start the API: uvicorn main:app --reload --port 8000")
        print("  3. Access API Docs: http://localhost:8000/docs")
        print("  4. Try logging in with demo credentials")
        print()

    except Exception as e:
        print(f"\n[ERROR] Setup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await default_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
