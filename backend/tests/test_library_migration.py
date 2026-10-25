"""Exercise legacy stock conversion in disposable schemas, never public data."""

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

pytestmark = pytest.mark.skipif(os.environ.get("RUN_DATABASE_TESTS") != "1", reason="Opt-in local PostgreSQL tests")


@pytest.mark.asyncio
@pytest.mark.parametrize("inconsistent_stock", [False, True])
async def test_legacy_accession_backfill_and_inconsistent_stock_guard(inconsistent_stock):
    schema = f"library_migration_test_{uuid4().hex}"
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    path = Path(__file__).parents[1] / "migrations/versions/20261025_1900_library_circulation.py"
    spec = importlib.util.spec_from_file_location("library_migration_under_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    school, book, borrower = uuid4(), uuid4(), uuid4()
    async def convert():
        async with engine.begin() as db:
            await db.execute(text(f"CREATE SCHEMA {schema}"))
            await db.execute(text(f"SET LOCAL search_path TO {schema},public"))
            await db.execute(text("""CREATE TABLE books (id uuid PRIMARY KEY, school_id uuid NOT NULL, title varchar(300),
                isbn varchar(20), is_active boolean DEFAULT true, total_copies integer, available_copies integer,
                added_date_ad date NOT NULL)"""))
            for table in ("students", "staff", "users"):
                await db.execute(text(f"CREATE TABLE {table} (id uuid PRIMARY KEY, school_id uuid NOT NULL, full_name_en varchar(200))"))
            await db.execute(text("""CREATE TABLE book_issues (id uuid PRIMARY KEY, school_id uuid NOT NULL,
                book_id uuid NOT NULL CONSTRAINT book_issues_book_id_fkey REFERENCES books(id) ON DELETE CASCADE,
                issued_to_id uuid NOT NULL, issued_to_type varchar(20) NOT NULL, status varchar(20) NOT NULL,
                issue_date_ad date NOT NULL, due_date_ad date NOT NULL, return_date_ad date,
                fine_amount numeric(10,2) NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now())"""))
            await db.execute(text("INSERT INTO books (id,school_id,title,total_copies,available_copies,added_date_ad) VALUES (:book,:school,'Legacy reader',4,:available,'2026-10-01')"), {"book": book, "school": school, "available": 3 if inconsistent_stock else 2})
            await db.execute(text("INSERT INTO students VALUES (:borrower,:school,'Synthetic Legacy Student')"), {"borrower": borrower, "school": school})
            for status in ("ISSUED", "LOST", "RETURNED"):
                await db.execute(text("""INSERT INTO book_issues (id,school_id,book_id,issued_to_id,issued_to_type,status,issue_date_ad,due_date_ad)
                    VALUES (:id,:school,:book,:borrower,'STUDENT',:status,'2026-10-01','2026-10-15')"""), {"id": uuid4(), "school": school, "book": book, "borrower": borrower, "status": status})
            def upgrade(connection):
                migration.op = Operations(MigrationContext.configure(connection))
                migration.upgrade()
            await db.run_sync(upgrade)
            states = dict((await db.execute(text("SELECT status,count(*) FROM book_copies GROUP BY status"))).all())
            assert states == {"available": 2, "issued": 1, "lost": 1}
            records = (await db.execute(text("""SELECT i.status,c.status AS copy_state,i.borrower_name,i.policy_snapshot->>'legacy' AS legacy
                FROM book_issues i LEFT JOIN book_copies c ON c.id=i.copy_id"""))).mappings().all()
            assert {record["status"]: record["copy_state"] for record in records} == {"ISSUED": "issued", "LOST": "lost", "RETURNED": None}
            assert all(record["borrower_name"] == "Synthetic Legacy Student" and record["legacy"] == "true" for record in records)
    try:
        if inconsistent_stock:
            with pytest.raises(DBAPIError, match="Reconcile legacy"):
                await convert()
        else:
            await convert()
    finally:
        async with engine.begin() as db:
            await db.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await engine.dispose()
