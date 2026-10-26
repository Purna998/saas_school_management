# Nepal product references

The product direction is Nepal school administration, from early years through
Grade 12. The user explicitly requested Nepal-made school-management products as
references on 26 October 2026. Continue researching relevant Nepal providers when
adding subsequent modules. Transport was held during the hostel release and was
subsequently authorized by the user. Its implementation is documented in
[transport.md](transport.md).

## Sources reviewed for hostel

These are the providers' public descriptions, reviewed on 26 October 2026. They
establish product/workflow references, not independently verified capabilities,
legal requirements, government approval or access to their private applications.

| Nepal provider | Public reference | Application in this repository |
| --- | --- | --- |
| Web Zone, inSchoolERP | [School/College ERP](https://webzonenepal.com/schoolerp/) describes multiple hostels, room types and charges, vacancy searches, financial integration and hostel reports. | Multiple school-scoped hostels; labelled rooms/beds; configured NPR charges; vacancy lookup; hostel-to-fee-ledger posting; occupancy and resident reports. |
| A.N. Tech Solution, Easy School | [Easy School](https://antechsolution.com.np/easy-school-software) describes configurable rooms, repair/maintenance, hostel attendance and visitor logs, with accounting and mess capabilities. | Blocked/retired bed inventory, warden roll call, visitor check-in/out and fee integration. Its wider menu planning, hygiene and mess-accounting descriptions are separate product references, not claims about this release. |
| NepTechPal | [School management software](https://neptechpal.com.np/services/school-management-software) describes hostel allocation, hostel billing, check-in/out, meal tracking and warden reports; its calendar description emphasizes BS dates with AD conversion. | Admission/checkout and preserved transfers; meal sessions; BS date entry with AD conversion; monthly BS billing periods and warden reports. |
| Fossa Technology | [School management software Nepal](https://fossatechnology.com.np/school-management-software-nepal) emphasizes a BS calendar, local academic-year handling and role-specific school screens. | BS-first hostel records and billing, Nepal civil dates/times, English/Nepali identifiers, and staff-only residential records. |

## Implementation decisions

- Use BS dates and named Nepali months in the office workflow, retain AD dates for
  database sorting, and display timestamps in `Asia/Kathmandu`. Date entry accepts
  Devanagari digits. Keep dates from the existing Nepal calendar conversion code.
- Retain exact NPR decimal amounts. The school configures its charge and fee
  heads; no national hostel price, mandatory fine, deposit or proration formula
  is assumed. Monthly billing is an explicit office action.
- Identify students through the existing school directory, admission/EMIS
  reference, class/section and roll number. Nepali and English names are
  searchable. Do not infer a new enrollment grade model from a vendor's marketing
  description: this repository's current enrollment grades remain unchanged.
- Use the existing fee ledger for hostel billing, collections, concessions,
  refunds and receipts. The user previously deferred eSewa/Khalti checkout; this
  release keeps that decision.
- Record the responsible contact and a staff-approved leave departure. School
  staff apply their own guardian/warden approval process. Do not present a log
  entry as automated guardian consent, an SMS delivery or a statutory approval.
- Retain the application's current visual language. Use published workflows as
  references without copying vendor code, branding, screenshots or proprietary
  interfaces. The hostel screens are original components in this repository.
- Keep residential information private to authorized school staff. The present
  hostel module is an office workspace, not a parent/student portal.

The detailed operational scope, constraints and verification are in
[hostel.md](hostel.md). These references do not imply affiliation with the vendors.

## Sources reviewed for transport

The transport pass also reviewed these public pages on 26 October 2026:

| Reference | Published workflow | Implementation here |
| --- | --- | --- |
| [Web Zone inSchoolERP](https://webzonenepal.com/schoolerp/) | Route-wise bus operations, pickup/destination points, transport fee integration and route/student reports. | Ordered route stops, separate pickup/drop runs, student agreements, BS-month fee posting and full-register/manifest exports. Parent alerts and driver payroll remain separate communication/HR integrations. |
| [A.N. Tech Solution Easy School](https://antechsolution.com.np/easy-school-software) | Route-based prices, driver information, vehicle upkeep, insurance/renewal records and GPS integration. | Route/stop fare configuration, vehicle/driver/helper records, maintenance logs, recorded expiry dates, authenticated position reporting and age-labelled map links. A GPS device reference alone does not establish an automatic feed. |
| [United Universal School transportation](https://universal.united.edu.np/transportation) | A real Nepal school publishes local route corridors and bus identifiers, distinguishes home-to-school and school-to-home timing, and asks for a receiving adult for junior home drops. | Nepali locality/registration text, NPT schedules in both directions, and a school-configurable adult-handover requirement with the receiving name logged by staff. No vendor schedule, contacts or student records are copied into the school database. |

The public descriptions are product references, not proof of statutory fares,
licensing rules, mandatory service intervals, government approval or independent
verification of a device location. This release does not copy vendor code or
interfaces or invent route optimization/ETAs. The later phone-first tracking pass
adds in-page nearby guidance and opt-in supported browser notifications while the
parent screen is open; it does not claim background push/SMS delivery.

The live-tracking extension also reviewed [OrbitTrack](https://orbitbustrack.com/),
a Nepal school-bus platform publishing GPS maps, parent/driver views, stop updates
and BS-calendar workflows. The original implementation here uses explicit trip
phone consent, verified family links, freshness-labelled maps and nearby-stop
guidance. OTP boarding, traffic ETA, hardware tracker integration and closed-app
push remain outside this phone-first release. See [live-transport.md](live-transport.md).
