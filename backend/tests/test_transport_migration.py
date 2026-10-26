"""Legacy assignment reconciliation and tenant guards use disposable schemas."""

import importlib.util
import os
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
    reason="Opt-in local PostgreSQL migration tests",
)


@pytest.mark.asyncio
@pytest.mark.parametrize("cross_school", [False, True])
async def test_legacy_transport_backfill_preserves_unknown_schedules(cross_school):
    schema = f"transport_migration_test_{uuid4().hex}"
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    spec = importlib.util.spec_from_file_location(
        "transport_migration_under_test",
        Path(__file__).parents[1]
        / "migrations/versions/20261026_0930_transport_operations.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    school, vehicle, route, stop, student = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()

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
                    "CREATE TABLE vehicles (id uuid PRIMARY KEY,school_id uuid,vehicle_number varchar(30),capacity integer)"
                )
            )
            await db.execute(
                text(
                    "CREATE TABLE routes (id uuid PRIMARY KEY,school_id uuid,name varchar(200),distance_km numeric(6,2),estimated_time_minutes integer)"
                )
            )
            await db.execute(
                text(
                    "CREATE TABLE route_stops (id uuid PRIMARY KEY,route_id uuid CONSTRAINT route_stops_route_id_fkey REFERENCES routes(id) ON DELETE CASCADE,stop_name varchar(200),stop_order integer,latitude numeric(10,7),longitude numeric(10,7))"
                )
            )
            await db.execute(
                text(
                    """CREATE TABLE student_transport (id uuid PRIMARY KEY,school_id uuid,student_id uuid,route_id uuid REFERENCES routes(id),stop_id uuid REFERENCES route_stops(id),vehicle_id uuid REFERENCES vehicles(id),transport_type varchar(20),monthly_fee numeric(10,2),is_active boolean,created_at timestamptz DEFAULT now())"""
                )
            )
            await db.execute(
                text(
                    "INSERT INTO students VALUES (:student,:school,'Synthetic Legacy Rider','ADM-1',NULL)"
                ),
                {"student": student, "school": school},
            )
            await db.execute(
                text("INSERT INTO vehicles VALUES (:vehicle,:school,'बा २ ख १२३४',20)"),
                {"vehicle": vehicle, "school": uuid4() if cross_school else school},
            )
            await db.execute(
                text(
                    "INSERT INTO routes VALUES (:route,:school,'Legacy route',NULL,NULL)"
                ),
                {"route": route, "school": school},
            )
            await db.execute(
                text("INSERT INTO route_stops VALUES (:stop,:route,'चोक',1,NULL,NULL)"),
                {"stop": stop, "route": route},
            )
            await db.execute(
                text(
                    "INSERT INTO student_transport VALUES (:id,:school,:student,:route,:stop,:vehicle,'BOTH',1500,true,now())"
                ),
                {
                    "id": uuid4(),
                    "school": school,
                    "student": student,
                    "route": route,
                    "stop": stop,
                    "vehicle": vehicle,
                },
            )

            def upgrade(connection):
                migration.op = Operations(MigrationContext.configure(connection))
                migration.upgrade()

            await db.run_sync(upgrade)
            row = (
                (
                    await db.execute(
                        text(
                            "SELECT needs_setup,snapshot,pickup_run_id,drop_run_id,monthly_fee FROM student_transport"
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert (
                row["needs_setup"]
                and row["pickup_run_id"] is None
                and row["drop_run_id"] is None
            )
            assert (
                row["snapshot"]["student_name"] == "Synthetic Legacy Rider"
                and row["snapshot"]["stop_name"] == "चोक"
            )
            assert (
                row["snapshot"]["vehicle_number"] == "बा 2 ख 1234"
                and str(row["monthly_fee"]) == "1500.00"
            )
            assert await db.scalar(text("SELECT count(*) FROM transport_runs")) == 0
            assert await db.scalar(text("SELECT school_id FROM route_stops")) == school

    try:
        if cross_school:
            with pytest.raises(DBAPIError, match="Reconcile legacy transport"):
                await convert()
        else:
            await convert()
    finally:
        async with engine.begin() as db:
            await db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()
