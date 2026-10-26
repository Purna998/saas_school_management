"""Legacy residential conversion is tested in disposable schemas."""

import importlib.util
import os
from datetime import date
from pathlib import Path
from uuid import uuid4
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from shared.config.settings import settings

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="Opt-in PostgreSQL migration tests",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("inconsistent", [False, True])
async def test_legacy_bed_assignment_and_occupancy_guard(inconsistent):
    schema = f"hostel_migration_test_{uuid4().hex}"
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    spec = importlib.util.spec_from_file_location(
        "hostel_migration_under_test",
        Path(__file__).parents[1]
        / "migrations/versions/20261026_0100_hostel_operations.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    school, hostel, room, student = uuid4(), uuid4(), uuid4(), uuid4()

    async def convert():
        async with engine.begin() as db:
            await db.execute(text(f"CREATE SCHEMA {schema}"))
            await db.execute(text(f"SET LOCAL search_path TO {schema},public"))
            await db.execute(
                text(
                    "CREATE TABLE students (id uuid PRIMARY KEY,school_id uuid,full_name_en varchar(200),admission_number varchar(30),emis_student_id varchar(30))"
                )
            )
            await db.execute(text("CREATE TABLE fee_ledger (id uuid PRIMARY KEY)"))
            await db.execute(
                text(
                    "CREATE TABLE hostels (id uuid PRIMARY KEY,school_id uuid,name varchar(200),is_active boolean,total_rooms integer,capacity integer)"
                )
            )
            await db.execute(
                text("""CREATE TABLE hostel_rooms (id uuid PRIMARY KEY,school_id uuid,hostel_id uuid CONSTRAINT hostel_rooms_hostel_id_fkey REFERENCES hostels(id) ON DELETE CASCADE,
                room_number varchar(20),capacity integer,occupied integer,monthly_fee numeric(10,2),is_active boolean)""")
            )
            await db.execute(
                text("""CREATE TABLE room_allocations (id uuid PRIMARY KEY,school_id uuid,room_id uuid CONSTRAINT room_allocations_room_id_fkey REFERENCES hostel_rooms(id) ON DELETE CASCADE,
                student_id uuid,status varchar(20),allocated_date_ad date,vacated_date_ad date,created_at timestamptz DEFAULT now())""")
            )
            await db.execute(
                text(
                    "INSERT INTO students VALUES (:student,:school,'Synthetic Legacy Boarder','ADM-1',NULL)"
                ),
                {"student": student, "school": school},
            )
            await db.execute(
                text(
                    "INSERT INTO hostels VALUES (:id,:school,'Legacy Hostel',true,1,2)"
                ),
                {"id": hostel, "school": school},
            )
            await db.execute(
                text(
                    "INSERT INTO hostel_rooms VALUES (:id,:school,:hostel,'101',2,:occupied,1000,true)"
                ),
                {
                    "id": room,
                    "school": school,
                    "hostel": hostel,
                    "occupied": 0 if inconsistent else 1,
                },
            )
            for status in ["ACTIVE", "VACATED"]:
                await db.execute(
                    text(
                        "INSERT INTO room_allocations VALUES (:id,:school,:room,:student,:status,'2026-10-01',:vacated,now())"
                    ),
                    {
                        "id": uuid4(),
                        "school": school,
                        "room": room,
                        "student": student,
                        "status": status,
                        "vacated": None if status == "ACTIVE" else date(2026, 10, 10),
                    },
                )

            def upgrade(connection):
                migration.op = Operations(MigrationContext.configure(connection))
                migration.upgrade()

            await db.run_sync(upgrade)
            assert await db.scalar(text("SELECT count(*) FROM hostel_beds")) == 2
            rows = (
                (
                    await db.execute(
                        text(
                            "SELECT status,bed_id,student_name,monthly_fee FROM room_allocations"
                        )
                    )
                )
                .mappings()
                .all()
            )
            assert {row["status"]: bool(row["bed_id"]) for row in rows} == {
                "ACTIVE": True,
                "VACATED": False,
            }
            assert all(
                row["student_name"] == "Synthetic Legacy Boarder"
                and str(row["monthly_fee"]) == "1000.00"
                for row in rows
            )

    try:
        if inconsistent:
            with pytest.raises(DBAPIError, match="Reconcile legacy hostel"):
                await convert()
        else:
            await convert()
    finally:
        async with engine.begin() as db:
            await db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()
