import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LibraryCatalog } from '../components/library/LibraryCatalog';
import { BookEditor } from '../components/library/BookEditor';
import { AddCopiesForm } from '../components/library/LibraryInventory';
import { IssueBookDialog, LoanActionDialog } from '../components/library/LibraryCirculation';
import { LibraryLoans } from '../components/library/LibraryLoans';
import { canRenewLoan, dueDate, nepalDate } from '../lib/api/library';
import type { LibraryBook, LibraryLoan, LibraryPolicy } from '../lib/api/library';
import { apiClient } from '../lib/api/client';

afterEach(cleanup);
function client() { return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } } }); }
const noop = () => {};
const book: LibraryBook = { id: 'book-1', title: 'Synthetic Reader', author: 'Author', isbn: '9780306406157', category: 'textbook', publisher: null, edition: null, language: 'नेपाली', reading_level: 'Grades 1–3', shelf_location: 'A-1', total_copies: 2, available_copies: 1, is_active: true, is_lendable: true, added_date_ad: '2026-10-25', created_at: '2026-10-25T10:00:00Z' };
const policy: LibraryPolicy = { loan_days: 14, student_limit: 5, staff_limit: 10, max_renewals: 2, renewal_days: 14, allow_overdue_renewal: false, daily_fine: '0.00', fine_cap: '0.00' };
const loan: LibraryLoan = { id: 'loan-1', book_id: book.id, copy_id: 'copy-1', book_title: book.title, accession_number: 'LIB-000001', issued_to_id: 'student-1', issued_to_type: 'student', borrower_name: 'Synthetic Student', borrower_reference: 'ADM-1', issue_date_ad: '2026-10-01', issue_date_bs: '2083-06-15', due_date_ad: '2026-10-15', due_date_bs: '2083-06-29', return_date_ad: null, return_date_bs: null, status: 'overdue', renewal_count: 0, max_renewals: 2, renewal_days: 14, allow_overdue_renewal: false, overdue_days: 10, fine_amount: '0.00', estimated_fine: '5.00', return_condition: null, notes: null, created_at: '2026-10-01T10:00:00Z' };

test('Nepal civil dates cross UTC midnight and overdue renewals respect loan rules', () => {
  assert.equal(nepalDate(new Date('2026-10-25T18:20:00Z')), '2026-10-26');
  assert.equal(dueDate(0), ''); assert.equal(dueDate(91), '');
  assert.equal(canRenewLoan(loan), false);
  assert.equal(canRenewLoan({ ...loan, allow_overdue_renewal: true }), true);
  assert.equal(canRenewLoan({ ...loan, status: 'issued', renewal_count: 2 }), false);
});

test('catalog-only accounts see metadata without stock history or mutation actions', () => {
  const queryClient = client();
  queryClient.setQueryData(['library', 'books', { search: '', is_active: true, available_only: false }, 1], { books: [book], total: 1 });
  const view = render(<QueryClientProvider client={queryClient}><LibraryCatalog canCreate={false} canEdit={false} canIssue={false} privateAccess={false} onEdit={noop} onInventory={noop} onIssue={noop} /></QueryClientProvider>);
  assert.ok(view.getByText(book.title)); assert.ok(view.getByText('नेपाली · Grades 1–3'));
  for (const name of ['Edit', 'Add title', 'Issue', 'Archive', 'Copies & history', 'Export catalog']) assert.equal(view.queryByRole('button', { name }), null);
  queryClient.clear();
});

test('catalog editor clears optional ISBN and reference categories default to shelf use', async () => {
  const queryClient = client(); const original = apiClient.library.books.update;
  let payload: Record<string, unknown> | undefined;
  apiClient.library.books.update = async (_id, value) => { payload = value as Record<string, unknown>; return { success: false, data: null as never, error: { message: 'Test response' } }; };
  try {
    const view = render(<QueryClientProvider client={queryClient}><BookEditor book={book} onClose={noop} /></QueryClientProvider>);
    fireEvent.change(view.getByLabelText('ISBN (optional)'), { target: { value: '' } });
    fireEvent.change(view.getByLabelText('Category'), { target: { value: 'reference' } });
    assert.equal((view.getByLabelText('Allow borrowing outside the library') as HTMLInputElement).checked, false);
    fireEvent.click(view.getByRole('button', { name: 'Save catalog entry' }));
    await waitFor(() => assert.ok(payload)); assert.equal(payload!.isbn, null); assert.equal(payload!.is_lendable, false);
  } finally { apiClient.library.books.update = original; queryClient.clear(); }
});

test('copy additions retain retry identity and rotate it when stock intent changes', async () => {
  const queryClient = client(); const original = apiClient.library.addCopies; const requests: Array<Record<string, unknown>> = [];
  apiClient.library.addCopies = async (_id, data) => { requests.push(data as Record<string, unknown>); return { success: false, data: null as never, error: { message: 'Temporary connection failure' } }; };
  try {
    const view = render(<QueryClientProvider client={queryClient}><AddCopiesForm bookId={book.id} onClose={noop} onBusy={noop} /></QueryClientProvider>);
    const submit = async (count: number) => { fireEvent.click(view.getByRole('button', { name: 'Add copies' })); await waitFor(() => assert.equal(requests.length, count)); await waitFor(() => assert.ok(view.getByRole('button', { name: 'Add copies' }))); };
    await submit(1); await submit(2); assert.equal(requests[0].request_id, requests[1].request_id);
    fireEvent.change(view.getByLabelText('Number of copies'), { target: { value: '2' } });
    fireEvent.change(view.getByLabelText('Existing accession numbers (optional, one per line)'), { target: { value: 'नेपाली-१\nनेपाली-२' } });
    await submit(3); assert.notEqual(requests[1].request_id, requests[2].request_id); assert.deepEqual(requests[2].accession_numbers, ['नेपाली-१', 'नेपाली-२']);
  } finally { apiClient.library.addCopies = original; queryClient.clear(); }
});

test('issuing a selected copy uses the selected borrower and school policy, preserving retries', async () => {
  const queryClient = client(); queryClient.setQueryData(['library', 'policy'], policy);
  queryClient.setQueryData(['library', 'borrowers', 'student', '', 1], { borrowers: [{ id: 'student-1', type: 'student', name: 'Synthetic Student', reference: 'ADM-1', active_loans: 0, grade: 2, section: 'A', roll_number: 3 }], total: 1 });
  const original = apiClient.library.issue; const requests: Array<Record<string, unknown>> = [];
  apiClient.library.issue = async (data) => { requests.push(data as Record<string, unknown>); return { success: false, data: null as never, error: { message: 'Temporary connection failure' } }; };
  try {
    const view = render(<QueryClientProvider client={queryClient}><IssueBookDialog book={book} copyId="copy-2" accession="LIB-000002" onClose={noop} onLoan={noop} /></QueryClientProvider>);
    assert.equal((view.getByRole('button', { name: 'Issue book' }) as HTMLButtonElement).disabled, true);
    fireEvent.click(view.getByRole('button', { name: /Synthetic Student.*Grade 2 A.*Roll 3/ }));
    const submit = async (count: number) => { fireEvent.click(view.getByRole('button', { name: 'Issue book' })); await waitFor(() => assert.equal(requests.length, count)); await waitFor(() => assert.equal((view.getByRole('button', { name: 'Issue book' }) as HTMLButtonElement).disabled, false)); };
    await submit(1); await submit(2);
    assert.equal(requests[0].request_id, requests[1].request_id); assert.equal(requests[0].due_days, 14); assert.equal(requests[0].copy_id, 'copy-2'); assert.equal(requests[0].issued_to_id, 'student-1');
  } finally { apiClient.library.issue = original; queryClient.clear(); }
});

test('return waivers require a reason and a failed submission leaves the dialog closable', async () => {
  const queryClient = client(); const originalLoan = apiClient.library.loan; const originalReturn = apiClient.library.return;
  apiClient.library.loan = async () => ({ success: true, data: loan });
  let payload: Record<string, unknown> | undefined; let closed = false;
  apiClient.library.return = async (value) => { payload = value as Record<string, unknown>; return { success: false, data: null as never, error: { message: 'Temporary connection failure' } }; };
  try {
    const view = render(<QueryClientProvider client={queryClient}><LoanActionDialog loanId={loan.id} action="return" onClose={() => { closed = true; }} onLoan={noop} /></QueryClientProvider>);
    const amount = await view.findByLabelText('Assessed fine (NPR)'); fireEvent.change(amount, { target: { value: '0.00' } });
    const reason = view.getByLabelText('Reason / notes (required)') as HTMLInputElement; assert.equal(reason.required, true);
    fireEvent.change(reason, { target: { value: 'School-approved waiver' } }); fireEvent.click(view.getByRole('button', { name: 'Record return' }));
    await waitFor(() => assert.ok(payload)); await waitFor(() => assert.equal((view.getByRole('button', { name: 'Cancel' }) as HTMLButtonElement).disabled, false));
    assert.equal(payload!.fine_amount, '0.00'); assert.equal(payload!.book_issue_id, loan.id);
    fireEvent.click(view.getByRole('button', { name: 'Close' })); assert.equal(closed, true);
  } finally { apiClient.library.loan = originalLoan; apiClient.library.return = originalReturn; queryClient.clear(); }
});

test('read-only circulation shows BS/AD dates without return, renew, or lost controls', () => {
  const queryClient = client(); queryClient.setQueryData(['library', 'loans', { search: '', status: 'active' }, 1], { issues: [loan], total: 1 });
  const view = render(<QueryClientProvider client={queryClient}><LibraryLoans canIssue={false} canReturn={false} onLoan={noop} onAction={noop} /></QueryClientProvider>);
  assert.ok(view.getByText(`${loan.due_date_bs} BS`)); assert.ok(view.getByText(`${loan.due_date_ad} AD`));
  for (const name of ['Return', 'Renew', 'Mark lost']) assert.equal(view.queryByRole('button', { name }), null);
  queryClient.clear();
});

test('CSV downloads retain blobs while server failures retain error messages', async () => {
  const original = globalThis.fetch;
  try {
    globalThis.fetch = async () => new Response('\ufeffTitle,Author\r\nनेपाली,Author\r\n', { status: 200, headers: { 'Content-Type': 'text/csv; charset=utf-8' } });
    const response = await apiClient.library.export({ report: 'catalog' }); assert.equal(response.success, true); assert.ok(response.data instanceof Blob); assert.ok((await response.data.text()).includes('नेपाली'));
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: { success: false, data: null, error: { message: 'Narrow the report filters' } } }), { status: 400 });
    const rejected = await apiClient.library.export({ report: 'loans' }); assert.equal(rejected.success, false); assert.equal(rejected.error?.message, 'Narrow the report filters');
  } finally { globalThis.fetch = original; }
});
