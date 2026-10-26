"""Quarantine placeholder artifacts without reading/removing their old paths."""

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


@pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="Opt-in PostgreSQL migration test",
)
@pytest.mark.asyncio
async def test_report_migration_quarantines_samples_and_preserves_metadata():
    schema = f"report_migration_{uuid4().hex}"
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    spec = importlib.util.spec_from_file_location(
        "report_migration_under_test",
        Path(__file__).parents[1]
        / "migrations/versions/20261026_1730_report_workspace.py",
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    record, school = uuid4(), uuid4()
    try:
        async with engine.begin() as db:
            await db.execute(text(f"CREATE SCHEMA {schema}"))
            await db.execute(text(f"SET LOCAL search_path TO {schema},public"))
            await db.execute(text("CREATE TYPE reporttype AS ENUM ('STUDENT_LIST')"))
            await db.execute(
                text(
                    "CREATE TABLE reports (id uuid PRIMARY KEY,school_id uuid,report_type reporttype,title varchar(255),status varchar(30),file_url varchar(500),error_message text,created_at timestamptz DEFAULT now())"
                )
            )
            await db.execute(text("CREATE TABLE roles (id uuid,code varchar(100))"))
            await db.execute(
                text("CREATE TABLE permissions (id uuid,code varchar(100))")
            )
            await db.execute(
                text(
                    "CREATE TABLE role_permissions (id uuid,role_id uuid,permission_id uuid)"
                )
            )
            await db.execute(
                text(
                    "INSERT INTO reports (id,school_id,report_type,title,status,file_url) VALUES (:id,:school,'STUDENT_LIST','Retained title','READY','C:/private/do-not-open.txt')"
                ),
                {"id": record, "school": school},
            )

            def upgrade(connection):
                with Operations.context(MigrationContext.configure(connection)):
                    migration.upgrade()

            await db.run_sync(upgrade)
            row = (await db.execute(text("SELECT * FROM reports"))).mappings().one()
            assert (
                row["id"] == record
                and row["title"] == "Retained title"
                and row["report_type"] == "student_list"
            )
            assert (
                row["file_url"] is None
                and row["status"] == "EXPIRED"
                and row["snapshot_version"] == 0
            )
            assert "unverified" in row["error_message"]
            await db.execute(
                text(
                    "INSERT INTO report_events (id,school_id,report_id,request_id,action,actor_id) VALUES (:id,:school,:report,:request,'archived',:actor)"
                ),
                {
                    "id": uuid4(),
                    "school": school,
                    "report": record,
                    "request": uuid4(),
                    "actor": uuid4(),
                },
            )

            def downgrade(connection):
                with Operations.context(MigrationContext.configure(connection)):
                    migration.downgrade()

            savepoint = await db.begin_nested()
            with pytest.raises(DBAPIError, match="Refusing to discard"):
                await db.run_sync(downgrade)
            await savepoint.rollback()
    finally:
        async with engine.begin() as db:
            await db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()
