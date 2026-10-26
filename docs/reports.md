# School reports

The reporting workspace is `/dashboard/reports`. It reads school data for an
explicit filtered preview, then saves an immutable snapshot for review, export
and printing. The previous sample-row generator has been removed.

## Available reports

| Report | Scope and source |
| --- | --- |
| Student directory | Current non-deleted student records, bilingual names, admission/EMIS IDs, grade/section/roll and status |
| Yearly enrollment | Latest recorded enrollment for each student in the selected BS year, using that enrollment's grade/section/status |
| Recorded dropout | Latest yearly enrollment explicitly marked dropped; no invented dropout date or inferred dropout from absence |
| EMIS preparation | Yearly enrollment plus recorded demographics, birth BS date and missing-data flags; requires `report:emis` |
| Student transfer record | One student's retained directory/previous-school details for manual document preparation |
| Monthly attendance | Actual marks in one BS month, daily register or exactly one selected HS period |
| Exam result register | Stored total marks, percentage/GPA, rank and result for a chosen school exam, with its publication state |
| Collection register | Cash/bank/cheque receipt and refund movements by their own Nepal civil dates; optional BS academic year and current-class filters |
| Outstanding balances | Current ledger totals by student, including overdue balance; optional year/current class filters |
| Staff directory | Current non-deleted staff type, designation, department, qualification and joining BS date; excludes salary, DOB and private contacts |
| Library lending | Retained book/borrower/accession snapshots, issue/due/return BS dates, state at generation and recorded assessed fines |
| Hostel residents | Retained room/bed/student allocation snapshots, dates, state and agreed monthly charges |
| Transport agreements | Retained student pickup/drop agreement snapshots, dates, setup state and agreed monthly fare |
| Transport trips | Date-filtered frozen run/vehicle/driver details, dispatch state, passenger-state counts and empty-vehicle check |

The report catalog labels unavailable sources without querying their data. It does
not claim to provide a balance sheet, payroll/TDS calculation, traffic ETA, live
GPS trail or other workflow that these source records do not establish.

## Office workflow

1. Choose an authorized report. Fill only the filters shown for it. BS date entry
   accepts English and Devanagari digits and shows the AD equivalent for date
   ranges. Year inputs normalize to the existing `2083/084` convention. Yearly
   enrollment queries also recognize the existing four-digit/full-year aliases.
2. Click **Apply filters & preview**. Changing ordinary filter fields does not
   continuously query the database. The preview is paginated at 20 rows; totals
   cover all matching rows. It shows its read timestamp, parameters and scope.
   Changed filters are clearly marked until applied again.
3. Authorized generators can choose a title and CSV/Excel preference, then **Save
   all matching rows**. Generation reads the full filtered source again, so a
   concurrent source change may make the saved values differ from the earlier
   preview. The snapshot contains its own generation time, school name/EMIS code,
   generator, parameters, columns, notes, totals, rows and data checksum.
4. Open the saved record from history. Review its pages and scope notes. **Download
   CSV/Excel** exports every saved row, irrespective of the currently visible
   page. **Full print / PDF view** fetches the entire verified snapshot before
   enabling browser print/save-to-PDF. It never prints just one register page.
5. Archive with a reason when a report is superseded. Archived reports and their
   data/activity remain accessible to currently authorized staff in the archived
   history view. There is no destructive row/file delete operation.

Current student/enrollment models use numeric grade records. Blank or unassigned
grades are retained as unrecorded; no nursery/KG or government EMIS grade mapping
is fabricated. Ordinary class filters are the existing Grade 1–12 values.

## Interpreting the numbers

- Attendance reports use actual recorded rows, not an assumed 22-day month or a
  present default. Present and late count in the numerator; present, late,
  absent and leave count in recorded non-holiday days. Holidays are excluded.
  Unmarked days/students are not inferred absent. Daily and period registers
  are separate. Grade/section come from the attendance record for that period.
- Latest enrollment is selected before class filtering, so duplicate yearly
  enrollment history does not double-count a student or choose an old class.
  Enrollment time is not a dropout date. Students without a recorded enrollment
  in the requested year do not appear in a yearly enrollment/EMIS report.
- Result reports show the exam's actual publication state and stored results.
  They do not silently recalculate ranks/GPA or turn an unpublished exam into an
  official published result. Student names/sections are the current directory
  values when this snapshot is generated.
- Collections are movements, not billed revenue. Gross receipts minus refunds
  equals net movement for the selected dates. A refund in this period can relate
  to a receipt before the period. Payments and refunds are not joined in a way
  that multiplies the receipt amount. Concessions are not cash movements.
- Dues use current net ledger balances, not a backdated reconstructed account.
  Ledger bills are grouped without multiplying by payment rows. Finance class
  filters refer to the current student directory, not historical grade labels.
- Hostel/transport rates are agreed monthly service charges, not fee collection.
  Library fines are recorded assessed amounts, not payment evidence or newly
  accrued estimates. Live bus coordinates, family links and phone sharing codes
  never enter the transport report.
- A transfer record is preparation data for school review. This report does not
  create an outgoing certificate number, financial clearance, approval, stamp
  or signature, and does not reinterpret an incoming transfer certificate field
  as a newly issued outgoing certificate.
- EMIS output is a preparation/reconciliation register. No verified current
  official IEMIS upload template was supplied. Review the latest CEHRD/municipal
  requirements before official entry; no government submission occurs. A blank
  disability field means unrecorded, not a certified absence of disability.

## Formats, performance and integrity

Saved reports support up to **10,000 rows**. A larger result is rejected before
saving; staff must narrow filters. Browser print/PDF is limited to **2,000 rows**
to bound DOM/layout cost; use CSV/Excel or narrower filters for larger reports.
Date-range reports accept inclusive ranges of at most 366 days. Nothing silently
truncates an export or substitutes sample rows for an empty report.

CSV is a standard header/row dataset with a UTF-8 BOM for Nepali text. Spreadsheet
formula-like cells are escaped. The workbook is an actual `.xlsx` ZIP/XML file,
with frozen headers, filters, widths and a separate **About this report** sheet
containing provenance, scope notes, parameters and totals. Identifier, NPR and
decimal values are written as exact text; integer counts are numeric. This
preserves leading zeros and paise even beyond spreadsheet floating-point
precision. Automatic formulas and URL conversion are disabled.

PDF uses the browser's **Print / Save PDF** workflow, including its Nepali font
support. The API does not disguise CSV as PDF or Excel. Requests for a server PDF
artifact return a clear validation message directing staff to the print view.
Select suitable print orientation/margins for wide registers.

Live previews use a grouped count/total query plus a 20-row query, with separate
school-scoped lookup validation where an exam/student is chosen. No per-row
student/parent lookup is performed. Generation reads a bounded full source set,
formats it and batch-inserts snapshot rows. CSV/workbook generation runs outside
the async request event loop. Source school predicates and report/snapshot/history
indexes keep queries bounded to the school; nondefault dialogs load on demand.

The request transaction owns commit/rollback. Per-school/request advisory locks
and unique request IDs make identical generation retries return one complete
snapshot. Changed intent cannot reuse the ID. Archive commands also retain their
request identity. Report rows have ordered immutable identities; source edits do
not rewrite them. Full export/print checks row count and the SHA256 of the stored
structured snapshot before returning it. This is a data integrity checksum, not
a digital signature or the hash of the downloaded PDF/XLSX bytes.

Generated/download/print-view/archive activity retains actor name, time and
reason/format where applicable. The detail view shows the latest 20 activity
entries. No mutation endpoint edits snapshot rows or the report's provenance.
No generated files are exposed from a public uploads directory.

## Access and migration

All endpoints require a school-scoped staff account with `report:read`. Parent
and student roles use their own existing views and cannot use this office export
workspace. Each catalog report additionally requires its source permission:
student read, attendance report, exam+marks read, fee report, staff read, library
read, hostel read or transport read; EMIS also requires `report:emis`.

`report:generate` saves snapshots; `report:export` downloads/opens full print;
`report:delete` archives with a reason. Source permissions are rechecked for
saved detail/export/archive access. History counts and rows include only
currently permitted report types. Reporting permission alone does not bypass
financial or sensitive demographic permissions.

Revision `report_workspace` follows `transport_live`. Apply `alembic upgrade head`
before restarting the API. Install the updated runtime dependencies (`uv sync
--extra dev --inexact` in the existing development environment, or the updated
requirements for deployment). XlsxWriter 3.2.9 is pinned in project/requirements/
lock metadata. Existing generating roles accountant and vice-principal receive
report-read/export through migration/seeding; source permissions remain separate.
Existing users may need to sign in again to refresh frontend permission menus.

Prior report rows came from the old placeholder generator. Migration retains
their metadata, marks them expired/unverified and clears their file path. It
neither opens nor deletes those arbitrary paths. Old output cannot be downloaded
as trusted data; generate it again from school records. Downgrade refuses to
discard newly generated version-2 snapshots or recorded report activity.

## Verification

Backend tests use temporary tables and disposable schemas for all 14 sources,
BS/month/register validation, latest-year enrollment, refund date boundaries,
NPR totals, source/school permissions, snapshot retries, two simultaneous save
requests, CSV formula handling, actual XLSX contents, post-save source edits,
integrity failure, archive retention, row limits and legacy artifact quarantine.
Frontend tests cover explicit previews, dirty filters, permissions, exact large
NPR values with Nepali grouping, retry identity, full multi-page printing, empty
states, row limits and archive reasons. Run backend tests with
`RUN_DATABASE_TESTS=1`, frontend tests, lint and the production build.

No enabled browser surface was available for interactive visual/print review in
this session. Check wide and multi-page registers in the school's intended
browser/printer/PDF settings before external use. The implementation does not
claim production load measurements or statutory/government approval.

Nepal product/workflow references and their limits are recorded in
[nepal-product-references.md](nepal-product-references.md).
