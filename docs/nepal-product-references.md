# Nepal product references

The product direction is Nepal school administration, from early years through
Grade 12. The user explicitly requested Nepal-made school-management products as
references on 26 October 2026. Continue researching relevant Nepal providers when
adding subsequent modules. Transport implementation is on hold at the user's
request; this hostel release makes no transport changes.

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
