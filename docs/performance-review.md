# Performance and academic workflow review

Reviewed on 25 October 2026. Changes preserve the current screen layout, controls,
keyboard navigation and attendance/marks editing behavior.

## Interaction responsiveness

The supplied local INP was 120 ms: 0 ms input delay, 38 ms processing, and 82 ms
presentation delay. This is already below the 200 ms good threshold in Google's
[INP guidance](https://web.dev/articles/optimize-inp). A single local measurement
does not establish the field 75th percentile.

Attendance and marks previously rendered every table row on each keystroke. The
rows now use React memoization with stable callbacks and primitive editable
props. Component tests exercise the actual pages with 125 synthetic students:
typing in one row renders that row and skips the other 124. They also verify
that changing attendance status or toggling absence retains other edits.

The new roster query key is shared across attendance and marks, so an unchanged
class can reuse the existing React Query cache. Student mutations invalidate that
same cache. Login/logout clear the cache; concurrent GET deduplication also
includes the session identity to prevent data reuse across different logins in
the same school. School data is not added to Redis.

There was no available browser automation surface in this session. DOM component
checks and the production build are verified; a new browser INP or visual
comparison has not been measured. To compare INP, use the production preview on
the same device, viewport, class data and CPU settings, then repeat attendance
status changes, remark typing, marks entry, dialogs and sidebar navigation.
Inspect the slowest interaction in Chrome Performance, including rendering and
layout, and collect field p75 separately when real traffic is available.

## API and database changes

`GET /api/v1/students/roster?grade=2&section=A` returns only ID, name, roll number,
admission number and EMIS ID for active students in the authenticated school.
Section can be omitted for grade-wide name lookup. It uses one projection query
and returns the complete matching roster, avoiding the old first-page cap of
100 students and the full-profile response payload. The directory remains
paginated. Deterministic ID ordering resolves ties in directory/roster sorting.

Result calculation previously refreshed each newly inserted result separately.
SQLAlchemy already retrieves generated timestamps through PostgreSQL RETURNING,
and sessions retain values after commit. Removing the refresh loop saves one
SELECT per student. Real PostgreSQL regressions verify **four SELECTs for both
one student and 125 students**, with timestamps, grades and tied ranks intact.
At 125 students, the old calculation would have added 125 refresh SELECTs.

Monthly BS attendance filtering now uses inclusive month start and exclusive
next-month start, including Chaitra-to-Baisakh year rollover. This allows an
ordinary B-tree date range rather than relying on a text-prefix LIKE operation
and database collation. The aggregation still runs inside PostgreSQL.

The migration adds tenant-first partial indexes for live student directory and
class queries, plus a covering class/BS-month attendance index. These match the
leading equality columns and date range described in PostgreSQL's
[multicolumn index documentation](https://www.postgresql.org/docs/16/indexes-multicolumn.html).
Live-student predicates follow its
[partial-index guidance](https://www.postgresql.org/docs/16/indexes-partial.html).
Soft deletion now sets both deletion markers so existing modules agree on the
student's state.

## Reproducible synthetic benchmark

The included benchmark creates session-local temporary tables with 100,000
students and 600,000 attendance rows distributed across 20 schools. It compares
existing school-level access paths against the added composite indexes; the
monthly report also switches to the range predicate. Each result is the median
of five EXPLAIN ANALYZE executions after two warmups. No school data is read or
changed, and tables disappear when the connection closes.

| Query | Before (ms) | After (ms) | Local buffer blocks before / after |
| --- | ---: | ---: | ---: |
| Student directory, first page | 26.256 | 0.074 | 1,434 / 23 |
| Complete active class roster | 18.736 | 0.258 | 1,434 / 100 |
| BS monthly attendance aggregation | 84.172 | 0.323 | 5,637 / 64 |

These are synthetic warm database execution times on this computer. They exclude
authentication, network transfer and browser rendering, and are not production
latency or INP promises. Real table distributions, statistics, cache state and
write rates affect the benefit and index maintenance cost.

From `backend`:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_class_queries.py
$env:RUN_DATABASE_TESTS = '1'
.\.venv\Scripts\python.exe -m pytest tests -q
```

Ordinary tests skip the opt-in PostgreSQL cases unless `RUN_DATABASE_TESTS=1`.
Those cases clone the existing migrated schema into temporary tables and keep
all synthetic records inside an outer transaction. The configured database
must support temporary tables.

## Deployment and dependencies

The new migration is `class_query_indexes`; it has been applied to the local
database and verified at Alembic head. On another deployment, run:

```bash
cd backend
alembic upgrade head
```

Indexes build with PostgreSQL CONCURRENTLY, allowing existing reads/writes.
Concurrent index creation runs outside a transaction and can wait for existing
transactions; after an interrupted build, inspect for invalid indexes before
retrying. See [PostgreSQL CREATE INDEX](https://www.postgresql.org/docs/16/sql-createindex.html).
For rollback, `alembic downgrade exam_mark_absence` removes only these indexes.
Run schema changes through the application's normal deployment workflow.

Next.js and its ESLint configuration were updated from 16.2.9 to 16.4.3, with
compatible dependency fixes. The npm audit reports zero known vulnerabilities
for the resulting lockfile. The update includes upstream fixes for advisories
such as [GHSA-673q-mjm6-r5xr](https://github.com/advisories/GHSA-673q-mjm6-r5xr);
the [16.4.3 release](https://github.com/vercel/next.js/releases/tag/v16.4.3)
also backports bug fixes. New test tooling is development-only.

## Nepal nursery-to-grade-12 findings

This performance pass does not establish national grading compliance. The
current schema and form validation support numeric grades 1–12; nursery, LKG,
UKG and other school-specific early-years labels need a separate academic-level
identity and ordering model. Mapping them to arbitrary negative numbers or
renaming grade 1 would corrupt existing grade-based enrollment/report logic.

The CDC catalog distinguishes basic classes 1–8 and secondary curricula 9–12:
see the [CDC curriculum catalog](https://lib.moecdc.gov.np/elibrary/pages/search.php?search=grade).
Grade 11–12 optional subject groups are already modeled, but the existing
hard-coded split of GPA for grades 1–10 and division for 11–12 must be reviewed
against the applicable curriculum and assessment directive. CDC publishes a
[Letter Grading Directive 2078](https://lib.moecdc.gov.np/catalog/opac_css/index.php?id_rubrique=99&lvl=cmspage&pageid=6).
Policies should be versioned by academic year, grade, assessment type and school,
with separate theory/practical requirements and an explicit NG state before
claiming current NEB/SEE compliance. Historical report cards must retain the
policy used when their results were published.

This pass fixes the mechanical decimal-boundary bug in the existing grading
policy: 89.5%, 79.5% and similar values previously fell between inclusive integer
bands and returned zero. The existing thresholds themselves are retained.

Additional priorities identified during review are Nepal-time school-day
defaults for users abroad, explicit separation of daily and period attendance
in reports, and savepoint/batch handling for partial CSV imports. These require
their own behavior and migration design; they are not represented as completed
by the performance changes above.
