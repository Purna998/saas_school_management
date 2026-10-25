# Fees and payments

The school accounting workspace is available at `/dashboard/fees`. It records
confirmed cash, bank-transfer and cheque collections and refunds. It does not
initiate bank transfers or provide eSewa/Khalti checkout.

## Office workflow

1. Select the BS academic year. Both `2083` and `2083/084` resolve to the same
   accounting year. The default comes from the Nepal calendar endpoint.
2. In **Fee setup**, create a structure for the grade and add fee heads. Supported
   frequencies are monthly, quarterly, annual and one-time within the year.
   Optional heads, such as transport, require explicit opt-in during billing.
3. In **Billing**, choose the structure, optional section, students, BS months,
   optional heads and due day. Review the estimated bill count and amount before
   confirming. Existing bills are skipped without resetting balances.
4. In **Student dues**, find the student and select the particular bill to
   collect. Record only payments already confirmed outside the system. Bank and
   cheque records require a reference. Partial collections are supported.
5. Open the receipt after collection or from **Payments & receipts**. It includes
   BS/AD dates, the bill period, method, reference and balance immediately after
   the payment. Print it using the browser's print/save-to-PDF dialog.
6. A staff member with refund permission can record a partial or full refund
   from the receipt. The student owes the refunded amount again. The original
   payment is retained, with refund number, reason, method, reference and actor.
7. Apply scholarships/concessions from the student statement. A fixed concession
   is a single total pool, allocated oldest bill first; it is not repeated on
   every bill. A percentage is applied proportionally to current unpaid dues,
   with exact total rounding to paise. A bill's Concession action limits the
   change to that bill. Existing paid money is not discounted.
8. In **Concessions**, an authorized staff member can reverse an award with a
   reason. Its original per-bill allocation and reversal history remain stored.
9. **Reports** shows net collections, refunds, concessions, overdue balances and
   paginated outstanding students. Open a statement directly from that report.

Quarterly charges occur in BS months 1, 4, 7 and 10. Annual/one-time charges are
included in billing batches that include Baisakh. Due dates use an exact
BS-to-AD conversion on the selected day of the billing month; they do not use
an approximate Gregorian month. Choose the student's actual enrollment months
when billing late admissions. Due days are limited to 1–28 so every BS month
can represent the date.

Only one structure can be active for a grade and year. A structure can be
archived while retaining all its bills. Once a head is billed, its financial
terms cannot be edited or deleted. A billed structure also cannot be replaced
by a new structure for the same grade/year; restore the existing structure or
use a new academic year. This prevents accidental rebilling under new head IDs.
Additional fee heads may be added intentionally to an active structure.

Awards apply once to existing unpaid bills. Future bills are not automatically
discounted; apply another explicit award if appropriate. An award's active state
means it remains applied, not that a recurring discount job will run.

## Accounting integrity

All financial arithmetic uses PostgreSQL Numeric and Python Decimal. Responses
send decimal strings. Browser estimates use integer paise, and currency formatting
retains paise even for large totals. No floating-point amount is sent as an
accounting calculation.

Student row locks serialize billing, collections, refunds and concessions for
the same student. PostgreSQL advisory locks and unique request IDs serialize
retries, including two concurrent requests using the same key. Changed payloads
cannot reuse a key. Different cashiers cannot exceed a bill's remaining balance.
Unique bill-period indexes protect monthly and NULL-period annual entries.

Ledger constraints require nonnegative values, `balance = amount_due -
amount_paid`, and `original_amount - discount_amount = amount_due`. Refunded
amounts cannot exceed their original payment. Concessions retain per-bill audit
allocations; reversals restore those bills without deleting their history.

The dashboard's fee chart and pending-fees figure now use school records.
Academic overview panels still use clearly labeled demo data. Fee totals are
grouped by the bill's academic year/month, not by the date cash changed hands.
This module does not claim tax-invoice or statutory accounting compliance.

## Permissions and scope

| Permission | Actions |
| --- | --- |
| `fee:read` | Structures, minimal student lookup, statements, payment register, receipts and award history |
| `fee:create` | Structure/head management, bill generation, concessions and reversals |
| `fee:collect` | Record confirmed collections |
| `fee:refund` | Record refunds |
| `fee:report` | School summary and outstanding reports |

All operations use the authenticated school's ID; an ID in the request cannot
switch the school. Fee staff can look up minimal student/roster data without
requiring access to full student profiles. Parent/student accounts with only
the legacy `fee:read` permission cannot browse the school financial register.
A self-service family portal needs a verified account-to-student link and is
outside this school-office workflow.

The UI follows the existing student enrollment model's numeric grades 1–12.
Nursery/LKG/UKG enrollment remains a separate academic-model gap described in
the performance review; it is not simulated by assigning arbitrary grade IDs.

## Database rollout and verification

Run `alembic upgrade head` from `backend`; the new revision is `fee_accounting`.
It adds bill snapshots, monetary checks, duplicate-billing/retry indexes, refunds
and concession allocations. Existing billed amounts are preserved. Historical
discounts that previously rewrote `amount_due` cannot be reconstructed; migration
snapshots use the existing due amount and do not invent missing history. Legacy
awards without complete allocations cannot be automatically reversed.

Constraint creation stops on inconsistent/duplicate legacy records rather than
merging invoices or rewriting paid balances. Downgrade is refused once new
payment, refund or concession audit records exist.

```powershell
$env:RUN_DATABASE_TESTS = '1'
backend/.venv/Scripts/python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
```

The opt-in database cases use synthetic temporary tables; concurrency cases use
a uniquely named disposable schema cleaned up after testing. Existing school
records are not changed. Coverage includes billing retries, exact BS dates,
optional fees, partial collections, receipt/refund reconciliation, concession
rounding/reversal, tenant/staff permissions, and simultaneous cashiers/retries.
Frontend tests cover actual forms, request-key reuse, references, restricted
actions and complete 125-student billing rosters.

No browser surface was connected during implementation. DOM/component checks
and production compilation are automated; actual browser printing and visual
comparison still need a browser check.
