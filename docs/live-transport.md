# Live school transport: driver/helper phones first

Parents and authorized staff use `/dashboard/transport/live`. The assigned trip
phone opens `/transport/share#code=...`, without an office login. The code is a
short-lived capability to send fixes and report stops for one dispatched journey.

This is a phone-first foreground web implementation, with roughly 10-second
updates when connected. It does not promise locked-screen/background GPS,
traffic-aware arrival times, SMS, WhatsApp or closed-app push delivery.

## School setup

1. Apply `alembic upgrade head`; revision `transport_live` follows
   `transport_operations`. Restart the API and build/restart the frontend.
2. Serve the application over **HTTPS**. A phone on a plain HTTP LAN address
   cannot use browser geolocation. Keep the browser and `/backend` proxy on the
   same public origin; forward the `X-Transport-Token` header. Do not log that
   header or whole response bodies at the proxy/APM layer. The fragment code is
   never sent in an HTTP URL or Referer and is removed from the sender address
   bar after reading it. The phone retains it only in memory; reloading needs
   the original private link again. Do not add third-party analytics/session
   replay to this sender page.
3. Record the school's actual stop coordinates in **Transport → Routes & stops**.
   Dispatch snapshots freeze stop names, coordinates and nominal NPT times;
   later master edits do not move an in-progress child's stop. Coordinates are
   optional, but nearby guidance needs them. Old dispatched trips are not
   backfilled with guessed historical coordinates; phone sharing is enabled
   from the next new dispatch.
4. Use existing parent accounts. Under **Live vehicles → Parent access**, select
   the current student, enter the exact existing parent login email, record the
   school's verification note and confirm the relationship. The API verifies an
   active same-school parent role. It never automatically grants access from a
   matching name, phone, email or guardian record. A student can have multiple
   verified parent accounts and a parent can have multiple children.
5. Teachers, principals/vice-principals, school administrators and receptionists
   receive the new `transport:track` permission through migration/seeding. Other
   staff can receive this permission through existing role administration.
   Existing staff with `transport:read` can also view the live school fleet.
   `transport:track` does not expose fees, parent contacts or boarding rosters.
   Parent/student roles never get fleet access from track/read permission alone.
6. Dispatch normally. In **Live vehicles**, select the vehicle and **Connect /
   manage phone**. Create a labelled helper/driver link and copy it privately to
   that assigned person. One link is active per trip. A replacement revokes the
   previous link; **Revoke trip phone access** ends it immediately. Codes expire
   after eight hours and stop working when the trip is completed/cancelled.
   They are shown only on creation, hashed in PostgreSQL, excluded from command
   audit payloads and not persisted in frontend login/local storage.
7. On the phone, review the assigned vehicle/run, confirm consent and tap
   **Start sharing**. Allow precise GPS. Keep the phone in that vehicle with the
   page visible. The default screen-awake option requests a browser wake lock
   while sharing; devices can refuse/release it (including battery saving).
   Its state is shown. Hidden/offline screens pause sending; returning resumes
   only if sharing was already started. **Stop**, closing the page or losing
   permission ends phone sending. A helper may report approaching/at-stop/
   departed only while safe to operate the phone. Drivers use it while parked.

## Parent and staff experience

Parents see only linked current students' dispatched journeys. The feed includes
their child's staff-recorded boarding state, their own frozen stop and the
assigned vehicle's GPS. It does not expose other children, full route stop lists,
driver licence/contact records, handover contacts/receiving adult names, finances
or office audit history. After a child is absent, alighted, cancelled, or the trip
ends, that child's response no longer contains vehicle coordinates. Today's
completed/cancelled journeys remain as status cards; open journeys remain visible
across dates until resolved. Revoking the family link removes its journeys on the
next authorized refresh. Account status is checked by normal authentication.

Staff see the school's open trips and frozen stop references, without a child
roster in this feed. Existing transport office permissions still govern dispatch,
boarding, handover, assignments and finance. Administrators manage phone and
family links; teachers with tracking permission see a read-only map and cards.

The map and accessible journey cards distinguish:

| State | Meaning |
| --- | --- |
| Waiting for GPS | This trip has no phone fix yet |
| Live location | Fix is at most 30 seconds old, with reported accuracy within 100 m |
| GPS signal imprecise | Recent fix with accuracy worse than 100 m; nearby advice suppressed |
| GPS delayed | Fix is 31–120 seconds old |
| GPS offline / last known | Fix is older than 120 seconds |
| Connection interrupted | Viewer could not refresh or is offline; last known position stays grey |

Freshness advances between requests and is aligned to the API server clock.
The UI shows fix time in NPT, age and reported accuracy, never a fabricated live
position. No marker is extrapolated along a road. Maps update existing markers;
they do not recreate the whole map or reset its zoom every poll. Users can turn
off following and recenter. If tiles fail, the cards, coordinates/map links and
GPS state remain usable. Map tooltip text is DOM text, not untrusted HTML.

A parent with a child waiting for pickup or on the vehicle for home drop gets
nearby guidance when a **fresh, sufficiently precise** fix is within 300 m of
their stop in a straight line. The banner explains this distance is not a road
ETA or guarantee. Stale, inaccurate, offline, absent/alighted or ended journeys
do not produce nearby advice. A recent helper stop report can show assigned
stops ahead, approaching/at-stop/departed, or that a stop was passed; these are
explicit reports, not automatic boarding. Reports older than five minutes are
not used for parent stop guidance. Stop updates use versions, reject backwards
progress, and replay an identical last update without advancing twice.

Parents can explicitly enable supported browser notifications. A given journey
notifies at most once per open page session when it becomes nearby. The in-page
banner remains the fallback on unsupported mobile browsers. **Alerts require this
screen to stay open**; there is no Web Push/SMS/background delivery integration.
Notifications are never presented as actual guardian handover or proof a child
is aboard.

## Performance and integrity

- One compact feed per viewer, paginated at 20 journeys; count + data use two
  SQL queries with no per-child/vehicle location query. Normal authentication
  adds its existing authorization queries. Parent links, child-trip lookup and
  active fleet reads have indexes. Hidden/offline viewers stop polling; failures
  back off to 30 seconds. Private query keys include the user ID and are removed
  when unobserved. Tracking responses use `Cache-Control: no-store, private`.
- One replaceable `transport_live_positions` row per vehicle bounds GPS storage.
  Every fix does not append a permanent location trail or office audit event.
  Trip/session locks serialize sender writes, replacement/revocation and trip
  completion. GPS ingestion does not acquire the school-wide office command lock.
- The phone samples a new GPS fix, then sends a single request, about every ten
  seconds after completion. It never overlaps uploads, replays an offline trail
  or converts an old cached fix into a new timestamp. Requests time out; temporary
  failures retry fresh fixes with a bounded backoff. Late callbacks after Stop
  are ignored. Permission denial and expired/revoked codes stop retries.
- The API accepts only the code's school/trip/vehicle, not IDs supplied in a GPS
  payload. It rejects naive timestamps, fixes more than two minutes old or more
  than 15 seconds into the future, invalid coordinates/speed/accuracy and extra
  fields. Older/identical fixes do not overwrite a newer fix. Changing fixes
  faster than five seconds receives HTTP 429 with `Retry-After`.
- Family access changes, link issue/revocation and helper stop reports have
  append-only actor/session-labelled history. Secret plaintext codes are never
  stored in that history. Revocation, rotation and closure are checked in the
  same database transaction as each accepted fix.
- The public phone endpoints rely on a random 48-byte capability plus per-trip
  throttling, not an office JWT. Production ingress should additionally limit
  unauthenticated requests per IP (including bad-code attempts), cap body sizes
  and enforce HTTPS. There is no new dependency on an in-memory worker-local
  location cache, sticky sessions or long-lived DB-held socket connections.

## Map provider and deployment

Leaflet 1.9.4 is lazy loaded only for the live view. The initial raster provider
is `https://tile.openstreetmap.org/{z}/{x}/{y}.png` with visible attribution.
It follows browser caching and requests only visible tiles. Do not prefetch maps
or strip Referer on tile requests. OSM's service is best-effort; choose a suitable
commercial/self-hosted provider for production fleet volume. Set these frontend
build-time environment variables to switch providers and retain their required
attribution (no dotfiles need to be committed):

```
NEXT_PUBLIC_TRANSPORT_TILE_URL=https://your-provider.example/{z}/{x}/{y}.png
NEXT_PUBLIC_TRANSPORT_TILE_ATTRIBUTION=Your provider attribution
```

Basemap requests go to that provider. No parent/student names, trip IDs or tokens
are included, but normal map-tile/IP metadata is visible to it. Do not put secret
provider API keys in `NEXT_PUBLIC_*`; only browser-approved public map keys belong
there. No geocoding/routing service, installed-tracker forwarding or hardware
device credentials are connected in this phone-first release.

## Verification and references

Backend tests use isolated temporary tables for two-child privacy, school/role
boundaries, codes and secret-free audit records, expiry/rotation/revocation,
GPS validation/throttling, bounded storage, frozen stops, stop versions, closure
and two-query feed reads. Frontend tests cover location freshness, nearby advice,
staff-vs-family navigation, retry UUIDs, safe token transport, phone pause/stop/
late callbacks and nonoverlapping uploads. Run the complete backend suite with
`RUN_DATABASE_TESTS=1`, frontend tests, lint and a production build.

No connected browser surface was available in this session. Before school rollout,
test on actual intended Android/iOS phones over HTTPS: GPS consent and permission
denial, screen wake/lock and tab changes, Nepal cellular disconnect/reconnect,
wrong/replaced code, two parent accounts/children, handover closure, and map/nearby
accuracy at actual school stops. Automated tests do not establish road GPS
accuracy, battery life or production fleet load capacity.

Nepal product reference: [OrbitTrack](https://orbitbustrack.com/) publishes live
bus/parent/driver views, stop updates and BS-calendar workflows. This release
implements original phone sharing, private parent journeys and explicit nearby
guidance; it does not copy interfaces or claim OrbitTrack integration/OTP.

Technical references: [MDN geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation/watchPosition),
[visibility](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API),
[screen wake lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API),
[notifications](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API/Using_the_Notifications_API),
[Leaflet](https://leafletjs.com/reference) and [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).
