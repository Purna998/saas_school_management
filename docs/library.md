# School library

The library workspace is available at `/dashboard/library`. Its catalog, physical
inventory, loans, policy, reports and activity history use school records.
The dashboard's issued-book count also uses this module's live totals.

## Office workflow

1. Add a title with its author, optional ISBN, category, publisher, edition,
   language, reading level and shelf. ISBN-10 and ISBN-13 checksums are validated;
   a supplied ISBN is unique within the school. Reference and newspaper entries
   default to in-library use, with an explicit option to allow borrowing.
2. Each physical copy has a school-unique accession. Initial copies receive
   automatic `LIB-000001` style numbers. **Copies & history → Add copies** accepts
   more copies and optional existing accession numbers, one per line. Nepali
   letters, digits and combining marks are supported. A batch is atomic.
3. Issue any available copy or choose an exact accession from inventory. Search
   active students or employed staff by name or reference. Class, section, roll
   and staff designation help distinguish people with the same name. The service
   validates borrower eligibility and school membership before lending.
4. Use **Loans** or **Overdue** to return, renew or mark a loan lost. Lending slips
   retain the title, accession and borrower details at issuance, with BS and AD
   dates. They can be printed from the lending-record dialog.
5. Good returns restore availability. Damaged returns remain unavailable until
   staff record a repair through **Condition**. Lost loans retain their original
   accession and can be recovered through that same loan, including after stock
   withdrawal. Staff can separately record a copy missing from its shelf.
6. Archive unused titles rather than deleting their history. Existing loans can
   still be returned. Withdraw unusable physical copies with a reason; withdrawn
   copies stay in the register but are excluded from stock totals.

Reading levels are catalog labels, including Nursery–UKG and Grades 1–12. They do
not change the enrollment model or create early-years student records.

## Lending rules and fine assessments

Default policy: 14-day loans, five active loans per student, ten per staff member,
two 14-day renewals, no overdue renewals, and **zero late fines**. Staff with
`library:update` can change these school settings. Positive daily fine rates
require a positive cap. No statutory fine rate is assumed.

Renewal/fine policy is saved on each loan. Policy changes affect future loans;
the borrower limit uses the current school policy. A borrower can hold only one
active copy of a title. Overdue status is calculated using the Nepal civil date;
no scheduled job is required. Extensions run from the later of today and the old
due date. An allowed overdue renewal retains accrued fines and the per-loan cap.

Fine amounts are NPR decimal assessments, **not collections or fee balances**.
Staff must explain nonzero return assessments, waivers and lost-book decisions.
Assessments do not automatically create school-fee charges. Lost-book assessments
can be entered explicitly rather than assuming a book replacement price.
Online checkout, reservations and automated reminder delivery are not included.

## Permissions

| Permission | Access |
| --- | --- |
| `library:read` | Catalog; authorized staff can also read copies, borrowers, loans, policy, reports and history |
| `library:create` | Add titles and their initial physical stock |
| `library:update` | Edit/archive/restore titles, add copies, change copy condition, configure policy |
| `library:issue` | Issue and renew loans |
| `library:return` | Return/recover copies and record lost loans |

The workspace requires `library:read` as well as each action's permission.
Parent/student accounts with catalog-only access cannot open private borrower
registers, copy loan details, school totals, policy, history or exports. Borrower
search returns only identification fields and current loan counts, without
staff pay, contact information or unrelated profile data. Every query and
mutation is scoped to the authenticated school.

## Reports, performance and consistency

- Catalog filters cover title/author/ISBN/accession, category, active/archive
  status and availability. The loan register filters by status, borrower type,
  search and issue-date range. Search and filters are applied explicitly to avoid
  fetching records on each keystroke.
- Registers paginate 20 rows. Catalog and loan CSV exports use the applied
  filters and include all matches, rather than only the visible page. Exports
  reject more than 50,000 matches and ask staff to narrow filters. UTF-8 BOM
  preserves Nepali text in spreadsheet programs; formula-like cells are escaped.
- Reports show catalog categories, physical copy states, unresolved lost loans,
  returns and recorded assessments. Physical copy counts include archived titles;
  dashboard on-shelf totals include active titles. Recorded assessments include
  renewal accruals and do not represent outstanding payment obligations.
- Catalog, borrower, open-loan and history indexes support school-scoped lookups.
  Counts and borrower identification use grouped queries. Copies and their
  current loans are fetched in batches. Nondefault screens/dialogs load on demand.
- Issue/return/renew/lost/stock/policy commands carry request UUIDs. A matching
  retry returns the existing result without applying it twice; reusing a UUID
  for another intent conflicts. Edited forms generate a new UUID. PostgreSQL
  transaction locks serialize borrower and copy changes; an active-copy unique
  index provides an additional constraint. Stock counters are recomputed from
  accession rows within the same transaction.
- Catalog, copy, loan and policy changes append actor/time/reason/before/after
  activity entries. There is no API to edit or delete that history.

## Migration and verification

Run `alembic upgrade head` before starting the updated API. Revision
`library_circulation` follows `fee_accounting`.

The migration rejects inconsistent legacy stock counters or cross-school book
references. Reconcile those records before retrying; it does not silently repair
history. ISBN normalization can reveal duplicate existing ISBNs, which also need
reconciliation. Unresolved legacy loans receive newly assigned `MIG-…` accessions;
these are migration identities, not claims about historical accession numbers.
Old returned loans retain an unknown physical copy. Legacy borrower snapshots
use available same-school names or a clearly identified fallback. Downgrade
refuses to discard newly recorded library activity.

Backend tests cover input validation, school/privacy permissions, stock states,
fine/renewal policy, request retries, last-copy issue/return races, HTTP workflow,
CSV injection prevention, legacy conversion and migration reconciliation guards.
PostgreSQL tests use synthetic temporary tables or disposable schemas:

```powershell
cd backend
$env:RUN_DATABASE_TESTS='1'
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend tests cover catalog-only/read-only controls, metadata editing, copy and
issue retries, borrower/copy selection, return waivers, failed-dialog recovery,
Nepal dates, renewal eligibility and CSV responses. Run `npm --prefix frontend
test`, `npm --prefix frontend run lint`, and `npm --prefix frontend run build`.
Print layout and interactive browser appearance still require browser review;
no browser surface was available in this development session.
