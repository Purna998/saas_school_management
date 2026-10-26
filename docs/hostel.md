# School hostel operations

The completed boarding-office workspace is `/dashboard/hostel`. It replaces the
placeholder with school records for hostels, rooms, physical beds, residents,
leave/returns, visitors, attendance/meals, fee posting, reports and activity.
Its Nepal product references are recorded in
[nepal-product-references.md](nepal-product-references.md).

## Set up and admit

1. In **Hostels & rooms**, create each hostel, choose boys/girls/mixed type, and
   record the warden's name, phone and address/block. Names are school-unique
   ignoring case and surrounding whitespace. Totals come from room/bed records.
2. Add rooms with a label, floor (`0` is the ground floor), room type, initial
   bed count and the school's monthly NPR charge. Initial beds get `B-0001`
   labels. More beds can be added with automatic or existing labels, including
   Nepali labels. Room and bed labels remain unique within their parent.
3. Use **Bed register → Condition** for maintenance, repairs or retirement.
   Maintenance beds remain registered but cannot be allocated. Retired beds
   leave capacity and retain their identity/history. Occupied beds cannot be
   blocked or retired before the resident is transferred or checked out.
4. Admit an active student from this school's directory, identified by name,
   admission/EMIS number, class, section and roll. Choose a room, or allocate an
   exact bed from the bed register. Boys/girls hostels validate student gender;
   mixed hostels use the school's arrangements. One student can have only one
   active hostel stay, and one bed can have only one active resident.
5. Admission records today's Nepal civil date and current BS academic year. The
   stay snapshots the student reference, hostel, room, bed and agreed monthly
   charge. Later edits do not rewrite these snapshots. Print the stay record
   from **View stay**; it is not a financial receipt.
6. Transfer creates a new stay and closes the old one atomically. An unavailable
   or invalid destination leaves the original stay intact. The new stay takes
   the destination room's current rate. Checkout releases the bed once, with a
   reason. Existing financial bills and collections remain in the fee ledger.

Rooms can register up to 500 nonretired beds, in batches of up to 100; these are
application limits rather than a prescribed hostel arrangement. Occupied rooms
and hostels cannot be archived. Restore an archived hostel before activating its
rooms. There is no destructive room, bed, stay or activity deletion API.

## Leave, return and visitors

Open a current resident and record a departure after the school's existing
guardian/warden approval process. Capture the expected BS return date, destination,
responsible person, contact phone and reason. The validated AD conversion is
shown alongside BS entry; Devanagari digits are accepted. The bed remains
reserved while the student is away.

**Leave & returns** lists current departures, past-expected-return records and
completed returns. Record the actual return with a confirmation note. Expected
returns are date-based, not a configurable hourly curfew. The interface does not
claim to send approval requests or alerts.

**Visitors** records who arrived, the resident being visited, relationship,
contact and purpose. Record departure separately. These times use the server's
clock and display in NPT. Close open leave and visitor records before checkout or
transfer so whereabouts history remains consistent. Checkout/return retries with
the same request UUID are safe; a new attempt against an already closed record
conflicts rather than changing occupancy again.

## Warden attendance and mess meals

**Attendance & meals** provides morning/evening roll call and breakfast, lunch,
snacks and dinner sessions. This is separate from classroom attendance. Select a
BS date and apply it; AD is displayed for verification. Future dates are rejected.

Each session starts unmarked. Staff explicitly record attendance or meals taken/
skipped. Absence and excused entries need a reason/follow-up note. “Mark visible”
affects only the displayed page, not all residents. Save sends changed rows only.
Date, session, page, hostel tabs and refresh controls protect unsaved edits.
Browser reload warns while the register has unsaved changes; navigation outside
this workspace should be preceded by saving or discarding the draft.

Row versions prevent one warden silently overwriting another's marks. After a
conflict, discard/reload and review the other entry before recording a change.
Matching request retries do not increment versions twice. Register history retains
the recorded changes and appears under the resident's activity as well.

On a transfer or readmission date, the dated roster uses the student's latest
stay covering that date. Previously recorded marks remain in activity and saved
register exports. The meal register tracks service, not dietary requirements,
menu plans, a cashless canteen, or meal-by-meal charges.

## Monthly hostel billing

The room's monthly rate defaults to **NPR 0**, meaning free accommodation. The
school chooses whether an agreed boarding charge includes mess costs. There is
no inferred national rate or automatic partial-month calculation.

1. In **Fees & Payments**, set up an optional monthly hostel fee head for the
   student's current grade and selected BS year. It must match the stay's agreed
   monthly amount exactly. Different boarding rates can use distinct optional
   heads. Choose the school's hostel head explicitly; the system does not guess
   its purpose from an English or Nepali name.
2. Open a stay and choose **Post monthly hostel bill**. Choose the BS year/month,
   matching fee head and due day, then confirm the school's full-month charge.
   The student must have stayed in that room during the month. Future-month
   hostel billing is rejected.
3. The charge enters the existing student fee ledger. If that exact optional
   fee/period was already billed through the fee workspace, it is linked without
   creating another bill. The hostel module additionally allows only one linked
   hostel charge per student/BS month, including after a transfer. A different
   rate/head for an already linked month conflicts for office review.
4. Collect cash, bank or cheque payments, issue receipts, apply concessions and
   process refunds in **Fees & Payments**. Hostel checkout does not erase debt or
   automatically refund/adjust an approved monthly charge. Partial-month relief
   is an explicit fee concession. Payment collection was tested against a
   hostel-created bill.

Posting is an explicit authorized office action. It does not collect money or
send a wallet transaction. Hostel posting checks the student's current grade;
historical reclassification and billing adjustments belong to the fee office.
Unrelated heads manually selected in the fee workspace remain that office's
responsibility; the hostel uniqueness rule protects charges linked through this
hostel workflow.

## Access, reports and consistency

| Permission | Capability |
| --- | --- |
| `hostel:read` | Staff access to resident, room, movement, register, report and activity records |
| `hostel:create` | Create/edit/archive hostels and rooms, add beds, record bed condition |
| `hostel:allocate` | Admit, transfer, check out, record leave/returns, visitors, attendance and meals |
| `fee:create` plus hostel access | Post agreed monthly hostel charges |

Action routes also require `hostel:read` and a school context. Parent/student
accounts with only residential read permission cannot access private records;
this release provides no self-service residential portal. Directory lookup
returns identification fields without contact, guardian, demographic or financial
profiles beyond the gender needed for configured hostel eligibility.

Reports show operational capacity, occupancy, vacant beds, maintenance beds,
current leave and overdue returns. Operational totals exclude maintenance and
retired beds and archived rooms/hostels. Leave reserves occupancy. Setup capacity
counts nonretired registered beds, including maintenance. Financial collection and
balance reports remain in the fee module.

Registers paginate 20 rows. Resident CSV export uses the applied search/status
filters across all pages. Session export includes saved marks for the selected
date/session/search, including retained earlier-stay records. Exports reject more
than 50,000 matches, preserve Nepali UTF-8 text and escape formula-like cells.

Short hostel mutations serialize within a school transaction. Unique active-bed,
active-student and billing-period indexes add database guards. Request UUIDs and
immutable command results prevent replay from adding beds, releasing occupancy,
creating stays or posting charges twice. A reused UUID with a different intent
conflicts. Aggregate counters are recomputed from physical beds and active stays.
The request boundary commits all changes together or rolls them back on error.

The service batches resident/leave lookups and uses school, room, student/date,
register and history indexes. Nondefault screens and dialogs load on demand;
register rows are memoized to keep edits local to the changed row.

## Migration and checks

Run `alembic upgrade head` before starting the updated API. `hostel_operations`
follows `library_circulation`. Legacy occupancy must match active allocations;
cross-school references, duplicate active residents, inconsistent checkout dates,
or occupied archived rooms/hostels require reconciliation before conversion.
Duplicate hostel/room names also need resolution before unique indexes can be
created. The migration does not silently repair residential history.

Legacy capacity becomes labelled physical beds, with newly assigned bed identities
for active stays. Old checked-out stays retain an unknown bed. Existing room
names/rates are assigned as migration snapshots and labelled as such; these are
not assertions about unrecorded historical prices or bed numbers. Downgrade
refuses to discard newly recorded hostel operational/billing history.

Verification includes validation/privacy checks, school isolation, maintenance and
derived capacity, repeated and concurrent admission/checkout, atomic transfers,
same-day readmission, leave/visitor completion, register versions, CSV safety,
legacy migration guards, fee posting, existing payment collection and duplicate
monthly charges after transfer. All PostgreSQL scenarios use synthetic temporary
tables or disposable schemas.

Frontend checks cover read-only controls, decimal charges, physical bed retries,
exact-bed/student selection, BS conversion, unsaved register edits/versions and
billing approval. Run the full backend suite with `RUN_DATABASE_TESTS=1`, then
frontend tests, lint and production build. Browser/print visual review remains
necessary; no browser surface was available in this session.

Transport remains on hold. This release does not add online checkout, SMS delivery,
biometric hardware integration, medical records or a canteen inventory system.
