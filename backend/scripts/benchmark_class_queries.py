"""Compare class indexes using synthetic, session-local PostgreSQL tables.

Run from backend: python scripts/benchmark_class_queries.py
No school records are read or changed. Temporary tables disappear on disconnect.
Results measure warm database execution, not network latency or browser INP.
"""

import argparse
import asyncio
import json
from pathlib import Path
from statistics import median
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shared.config.settings import settings


DIRECTORY = """
SELECT * FROM perf_students
WHERE school_id = md5('1')::uuid AND deleted_at IS NULL
ORDER BY current_grade, roll_number, full_name_en, id LIMIT 20
"""
ROSTER = """
SELECT id, full_name_en, roll_number, admission_number, emis_student_id
FROM perf_students WHERE school_id = md5('1')::uuid AND deleted_at IS NULL
AND current_grade = 2 AND current_section = 'A' AND status = 'ACTIVE'
ORDER BY roll_number, full_name_en, id
"""
REPORT = """
SELECT date_ad, date_bs, status, count(*)
FROM perf_attendances WHERE school_id = md5('1')::uuid
AND grade = '2' AND section = 'A' AND {month_filter}
GROUP BY date_ad, date_bs, status ORDER BY date_ad
"""


async def measure(connection, query):
    times, blocks = [], []
    for iteration in range(7):
        result = await connection.execute(text(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"))
        plan = result.scalar_one()[0]
        if iteration >= 2:
            times.append(plan["Execution Time"])
            root = plan["Plan"]
            blocks.append(root.get("Local Hit Blocks", 0) + root.get("Local Read Blocks", 0))
    return {"median_execution_ms": round(median(times), 3), "median_local_blocks": median(blocks)}


async def benchmark(student_rows, attendance_rows):
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("""
                CREATE TEMP TABLE perf_students AS SELECT
                    md5(n::text)::uuid AS id, md5((n % 20)::text)::uuid AS school_id,
                    ((n / 20) % 12 + 1)::int AS current_grade,
                    chr((65 + (n / 240) % 4)::int) AS current_section,
                    (n / 960 + 1)::int AS roll_number,
                    'Student ' || n AS full_name_en,
                    'ADM-' || n AS admission_number, NULL::text AS emis_student_id,
                    CASE WHEN n % 17 = 0 THEN 'INACTIVE' ELSE 'ACTIVE' END AS status,
                    CASE WHEN n % 29 = 0 THEN now() ELSE NULL END AS deleted_at
                FROM generate_series(1, CAST(:rows AS int)) AS n
            """), {"rows": student_rows})
            await connection.execute(text("""
                CREATE TEMP TABLE perf_attendances AS SELECT
                    md5((n % 20)::text)::uuid AS school_id,
                    ((n / 20) % 12 + 1)::text AS grade,
                    chr((65 + (n / 240) % 4)::int) AS section,
                    '2083-' || lpad(((n / 28800) % 12 + 1)::text, 2, '0') || '-' ||
                        lpad(((n / 960) % 30 + 1)::text, 2, '0') AS date_bs,
                    DATE '2026-04-14' + ((n / 960) % 360)::int AS date_ad,
                    CASE WHEN n % 13 = 0 THEN 'absent' ELSE 'present' END AS status
                FROM generate_series(1, CAST(:rows AS int)) AS n
            """), {"rows": attendance_rows})
            # Existing access paths before the new composite indexes.
            for sql in (
                "CREATE INDEX ON perf_students (school_id)",
                "CREATE INDEX ON perf_attendances (school_id, date_bs)",
                "ANALYZE perf_students", "ANALYZE perf_attendances",
            ):
                await connection.execute(text(sql))
            queries = {
                "directory": DIRECTORY,
                "roster": ROSTER,
                "bs_month_report": REPORT.format(month_filter="date_bs LIKE '2083-07%'"),
            }
            before = {name: await measure(connection, query) for name, query in queries.items()}
            for sql in (
                "CREATE INDEX ON perf_students (school_id, current_grade, roll_number, full_name_en, id) WHERE deleted_at IS NULL",
                "CREATE INDEX ON perf_students (school_id, current_grade, current_section, status, roll_number, full_name_en, id) WHERE deleted_at IS NULL",
                "CREATE INDEX ON perf_attendances (school_id, grade, section, date_bs) INCLUDE (date_ad, status)",
                "ANALYZE perf_students", "ANALYZE perf_attendances",
            ):
                await connection.execute(text(sql))
            queries["bs_month_report"] = REPORT.format(month_filter="date_bs >= '2083-07-01' AND date_bs < '2083-08-01'")
            after = {name: await measure(connection, query) for name, query in queries.items()}
            print(json.dumps({
                "synthetic_student_rows": student_rows,
                "synthetic_attendance_rows": attendance_rows,
                "measurements": {name: {"before": before[name], "after": after[name]} for name in queries},
            }, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--students", type=int, default=100_000)
    parser.add_argument("--attendance", type=int, default=600_000)
    args = parser.parse_args()
    if args.students < 1 or args.attendance < 1:
        parser.error("row counts must be positive")
    asyncio.run(benchmark(args.students, args.attendance))
