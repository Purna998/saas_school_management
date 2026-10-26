# Nepal school transport

The completed transport-office workspace is `/dashboard/transport`. It uses
school records for fleet/crew, route stops and fares, scheduled runs, student
agreements, dispatch, boarding/handover, upkeep, location reports, fee posting and
activity reports. Nepal references and their feature mapping are in
[nepal-product-references.md](nepal-product-references.md).

Phone-first live tracking is now a separate minimal parent/staff surface at
`/dashboard/transport/live`. See [live-transport.md](live-transport.md) for verified
parent links, one-trip helper phone sharing, maps, nearby guidance and HTTPS setup.
The office permissions and manual position record below continue to apply.

## Setup and student agreements

1. **Fleet & crew:** add each vehicle with its actual student passenger capacity,
   registration, driver and helper contacts. Nepal and English registration text
   is supported. Devanagari digits normalize to ASCII for duplicate detection;
   case, spaces and hyphens do not create a second registration in the school.
   Driver licence/device references are school-held records, not verified IDs.
2. Record insurance, vehicle tax/bluebook renewal, fitness/inspection, route permit
   and driver licence expiry dates where available. Forms accept BS dates and
   show the validated AD equivalent. Missing dates remain visibly unrecorded.
   Mark an unavailable vehicle as under maintenance with a reason. Upkeep logs
   record completed work, next due date, odometer, workshop and exact NPR cost;
   these do not automatically renew documents or post expense/cash vouchers.
3. **Routes & stops:** define local corridor endpoints, reference distance/duration
   and separate pickup-only, drop-only and both-way monthly rates. Rates default
   to zero, meaning free service. Add ordered named stops, landmarks, optional
   map coordinates and nominal pickup/drop times in NPT. A blank stop-rate
   override inherits the route rate; explicit zero is free. Stops retain their
   identities when archived. Reorder with the arrows, then apply; competing
   order changes require a reload instead of silently replacing another edit.
4. **Scheduled runs:** choose a route, vehicle, direction, same-day NPT start/end
   window and operating days. Default days are Sunday–Friday and remain school
   configurable, including Saturday. Route reference stop times are not dynamic
   arrival predictions. A vehicle can serve separate nonoverlapping runs. The
   server rejects overlapping windows on shared operating days for the same
   vehicle or matching recorded driver licence. Update seasonal timing explicitly.
5. **Students & agreements:** choose an active student from this school's
   directory and the actual run/stop for each direction. Both legs can use
   different routes/stops. The server verifies school, direction, stop membership,
   active resources and seat availability. One student has one current agreement;
   each requested leg reserves one seat on its own run.
6. A same-stop both-way agreement uses the configured both-way rate, rather than
   an assumed one-way multiplier. Different pickup/drop stops require an explicit
   agreed combined charge and reason. Overrides also require a reason. Amounts
   stay exact NPR decimals. New agreements start on today's Nepal civil date and
   retain student/reference, run, route, stop and fare snapshots.
7. Home-drop receiving-adult recording defaults on and is school configurable.
   Record the usual receiving contact when known. Disabling the requirement needs
   a note explaining the school arrangement. This is a staff handover record, not
   automatic guardian consent or an OTP/identity check.
8. Change service from the current agreement: the old agreement ends and the new
   one is created atomically. Invalid/full destinations leave the old agreement
   intact. End service with a reason to release seats. Existing bills and
   collections remain in the fee account. Agreements involved in an open trip
   cannot be changed or ended until that trip is resolved.

Archiving a route requires resolving its active runs and assignments; occupied
stops/runs require reassignment or ending agreements first. A vehicle cannot be
archived while active runs use it. Replacing a run's vehicle checks existing
reserved seats and schedule conflicts. Capacity reductions cannot strand assigned
run seats. Stops, agreements, trips and activity have no destructive delete API.
The legacy assignment DELETE endpoint is a reasoned, audited end-service command.

## Daily dispatch and boarding

Start today's trip from its scheduled run. The transport office confirms its
review and can record dispatch notes. The server rechecks the operating day,
active run/route, available vehicle, driver name, recorded expiry dates and seats.
A recorded expired document blocks dispatch. Missing records do not certify
roadworthiness; staff still apply the school's real checks and responsibilities.

Only eligible active enrolled students are copied into the frozen roster.
Reservations belonging to students no longer enrolled remain reserved until the
office ends/reconciles their agreement; those students are not silently boarded.
The trip retains the actual vehicle and crew snapshot used at dispatch.

One vehicle can have only one open trip. Matching recorded driver licences also
prevent a second dispatch while the driver still has an open trip, even if the
planned time windows do not overlap. Actual dispatch can differ from its nominal
window; there is no invented traffic ETA or automatic late-departure rule.

The boarding checklist starts **pending**, never automatically present:

- Record boarding explicitly. A retry retains its UUID and passenger version.
- Mark an absence from pending with a reason/follow-up note.
- Record alighting after boarding. Home drops configured for handover require the
  name of the adult who actually receives the child. School arrivals can be
  recorded directly. These are authorized staff attestations.
- Passenger row versions reject stale changes by a second staff member. Refresh
  and review before another action. Final/absent marks cannot be applied again.
- Complete only after every passenger is alighted or absent, with a note and a
  driver/helper confirmation that the vehicle was physically checked empty.
- Cancel only before any passenger has boarded. Pending entries are retained as
  cancelled. A cancelled pre-boarding run can be dispatched again with a new
  request; completed/open runs cannot be duplicated for that same day.

Open trips are shown across all dates by default, so an unfinished prior-day trip
is not hidden. Apply a BS date to browse that day's trip register. The boarding
grid paginates 20 passengers. **Full manifest** fetches the entire bounded roster
(up to the 200-seat application limit) and enables printing only when every row
has loaded. CSV export also includes every passenger, not just the visible page.
The print view and agreement slip are operational records, not payment receipts.

## Position reporting and maps

Vehicle records show their last submitted coordinate with capture timestamp,
source, accuracy when supplied and age. Reports older than two minutes are
labelled stale; this is a display threshold, not a transport regulation.

Authorized staff can enter a verified coordinate or explicitly request the
browser device's position while accompanying that vehicle. Coordinates are
previewed and staff confirm the selected vehicle before posting. No browser
geolocation is requested automatically. Reports must include a timezone-aware
capture time, be within the last 15 minutes, and not be over 30 seconds in the
future. Matching retries do not add duplicate reports.

The same authenticated endpoint can accept configured device-client reports:
`POST /api/v1/transport/vehicles/{vehicle_id}/location`, with latitude, longitude,
capture time, optional accuracy, source and request UUID. A provider needs a
properly authorized school integration; the current permissions are transport
office permissions, not per-driver/per-vehicle mobile scopes. No hardware provider
API credentials or GPS tracker connection was supplied here. Automatic phone
sharing uses the separate scoped endpoints in [live-transport.md](live-transport.md).
Storing a `gps_device_id` does not enable such a feed.

The map link opens the recorded coordinate in OpenStreetMap on user action.
It does not embed third-party map tiles or transmit positions on page load.
This office record does not infer movement or calculate an ETA. The separate live
view embeds a basemap and displays fresh phone fixes plus explicit nearby guidance;
it does not send SMS or closed-app push notifications.

## Transport fee integration

The school configures its own fares. No national price, mandatory fine, deposit,
both-way discount or partial-month formula is assumed.

1. Set up an optional monthly transport fee head for the student's current grade
   and selected BS year in **Fees & Payments**, matching the agreement amount.
2. From an agreement, authorized fee staff choose that head, BS billing month and
   due day and explicitly approve the full-month charge. The agreement must cover
   the month. Future-month posting and unreconciled legacy agreements are rejected.
3. The charge is inserted into the existing fee ledger or links the same existing
   optional fee/period bill without duplicating it. One transport link per
   student/BS month also prevents repeat charges after an agreement change.
   A conflicting head/amount for an already linked month requires office review.
4. Collect cash, bank or cheque payments, print receipts, apply concessions and
   handle refunds in the existing fee workspace. Ending transport does not erase
   debt or create an automatic refund. Partial-month relief is a fee concession.

Posting does not collect money or initiate a wallet payment. The user's deferred
online-checkout decision remains in effect. Historical grade reclassification and
unrelated optional heads manually billed in the fee workspace remain the fee
office's responsibility. The transport link's uniqueness protects this workflow.

## Permissions, reports and data handling

| Permission | Office capability |
| --- | --- |
| `transport:read` | Staff access to fleet, routes, schedules, agreements, trip rosters, location reports and history |
| `transport:create` | Configure fleet/routes/runs; assign students; dispatch and record boarding/handover; upkeep and position reports |
| `transport:delete` | End assignments; changing an existing agreement requires this plus create permission |
| `fee:create` plus transport access | Explicitly post/link the agreed monthly transport bill |

Every route also requires transport read access and an authenticated school
context. Parent/student accounts with read permission alone cannot open office
registers or office vehicle locations. This release is the transport-office
workspace, with a separate scoped parent live view and helper phone sender.
Student lookup returns minimal
identification/class/reference fields, not unrelated contacts, demographics or
fee profiles.

Registers paginate 20 rows. Run counts use grouped queries and metadata is fetched
in batches. Trip rosters are frozen; master edits do not rewrite earlier journeys.
Nondefault screens/dialogs load on demand. Short commands serialize per school;
database unique indexes additionally guard current students, daily runs, open
vehicle trips and monthly charges. The request transaction owns commit/rollback.
Matching request UUIDs replay an immutable command result; a reused UUID with a
different intent conflicts. All accepted changes append actor/time/payload/result
activity without an edit/delete history endpoint.

Reports show actual fleet state, recorded expired documents, current agreements,
legacy setup needs, scheduled runs and today's/all-date open trip totals. They do
not imply missing documents are valid or mix configured fares with collections.
Assignment exports use applied search/status/run filters across all pages; trip
exports use the complete frozen roster. CSV preserves UTF-8 Nepali text, escapes
formula-like cells and rejects more than 50,000 matches.

## Migration and verification

Run `alembic upgrade head` before restarting the updated API. Revision
`transport_operations` follows `hostel_operations`.

The migration checks school references, active duplicate student assignments,
capacity bounds, negative charges and incomplete/out-of-range stop coordinates.
Duplicate normalized registration/route names or stop ordinals also need
reconciliation before unique indexes can be created. It does not silently delete,
reprice or merge existing school records.

Old stops receive their parent route's school ID. Old agreements retain their
recorded route/stop/vehicle/fare and a clearly flagged legacy snapshot. Their
original creation date is retained as a migration start-date reference; an unknown
end date remains unknown. They are marked **needs setup**, with no invented run,
operating day or departure time. The office must change/reconcile them before
dispatch or posting a transport bill through this workflow. Downgrade refuses to
discard newly recorded transport activity.

Backend verification uses synthetic temporary tables/disposable schemas for school
privacy, input validation, route/stop membership, prices, stop ordering, seat and
schedule conflicts, concurrent last-seat/dispatch/end retries, trip snapshots,
boarding/handover/sweeps, cancellation/restart, document/maintenance checks, reported
positions, complete manifests, fee-ledger collection and duplicate monthly billing.
Migration tests verify tenant guards and preservation of unknown legacy schedules.

Frontend tests cover read-only controls, BS dates, rates, configurable Saturdays,
request retries, passenger versions/handover, full manifests, stale location labels
and billing approval. Run backend tests with `RUN_DATABASE_TESTS=1`, frontend
tests, lint and production build. No browser surface was available for interactive
visual/print review in this session; that review remains necessary.
