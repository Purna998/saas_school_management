import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PaymentDialog, ScholarshipDialog } from '../components/fees/FeeDialogs';
import { StudentFeePanel } from '../components/fees/FeeRegisters';
import { FeeBilling } from '../components/fees/FeeBilling';
import { academicYear, fromPaise, money, paise } from '../lib/api/fees';
import type { FeeBill, FeeStudent, FeeStructure } from '../lib/api/fees';
import { apiClient } from '../lib/api/client';

afterEach(cleanup);
const student: FeeStudent = { id: 'student-1', full_name_en: 'Synthetic Student', current_grade: 2, current_section: 'A', roll_number: 1, status: 'active' };
const bill: FeeBill = { id: 'bill-1', student_id: student.id, fee_head_id: 'head-1', fee_head_name: 'Tuition', academic_year_bs: '2083/084', month_bs: '2083-01', original_amount: '100.00', discount_amount: '0.00', amount_due: '100.00', amount_paid: '20.00', balance: '80.00', due_date_ad: '2026-04-24', due_date_bs: '2083-01-10', status: 'overdue', payments: [] };
function client() { return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } } }); }

test('NPR arithmetic and formatting retain paise even for large report totals', () => {
  assert.equal(fromPaise(paise('100.01') + paise('0.09')), '100.10');
  assert.ok(money('250000000000000.01').endsWith('.01'));
  assert.equal(academicYear('2083'), '2083/084');
  assert.throws(() => academicYear('2083/085'));
});

test('payment retry retains its request ID; editing an amount uses a new ID', async () => {
  const queryClient = client();
  const original = apiClient.fees.collect;
  const requests: Array<Record<string, unknown>> = [];
  apiClient.fees.collect = async (data) => {
    requests.push(data as Record<string, unknown>);
    return { success: false, data: null as never, error: { message: 'Temporary connection problem' } };
  };
  try {
    const view = render(<QueryClientProvider client={queryClient}><PaymentDialog student={student} bill={bill} onClose={() => undefined} onPaid={() => undefined} /></QueryClientProvider>);
    fireEvent.click(view.getByRole('button', { name: 'Record payment' }));
    await waitFor(() => assert.equal(requests.length, 1));
    await waitFor(() => assert.equal((view.getByRole('button', { name: 'Record payment' }) as HTMLButtonElement).disabled, false));
    fireEvent.click(view.getByRole('button', { name: 'Record payment' }));
    await waitFor(() => assert.equal(requests.length, 2));
    assert.equal(requests[0].request_id, requests[1].request_id);
    await waitFor(() => assert.equal((view.getByRole('button', { name: 'Record payment' }) as HTMLButtonElement).disabled, false));
    fireEvent.change(view.getByLabelText('Amount (NPR)'), { target: { value: '30.01' } });
    fireEvent.click(view.getByRole('button', { name: 'Record payment' }));
    await waitFor(() => assert.equal(requests.length, 3));
    assert.notEqual(requests[1].request_id, requests[2].request_id);
    assert.equal(requests[2].ledger_id, bill.id);
    assert.equal(requests[2].amount, '30.01');
  } finally { apiClient.fees.collect = original; queryClient.clear(); }
});

test('bank payments require a transaction reference in the form', () => {
  const queryClient = client();
  const view = render(<QueryClientProvider client={queryClient}><PaymentDialog student={student} bill={bill} onClose={() => undefined} onPaid={() => undefined} /></QueryClientProvider>);
  fireEvent.change(view.getByLabelText('Payment method'), { target: { value: 'bank_transfer' } });
  assert.equal((view.getByLabelText('Bank / cheque reference') as HTMLInputElement).required, true);
  assert.equal((view.getByLabelText('Bank / cheque reference') as HTMLInputElement).validity.valid, false);
  queryClient.clear();
});

test('read-only fee users can view statements without collection or concession actions', () => {
  const queryClient = client();
  queryClient.setQueryData(['fees', 'statement', '2083/084', student.id], { student_id: student.id, student_name: student.full_name_en,
    academic_year_bs: '2083/084', total_original: '100.00', total_discount: '0.00', total_due: '100.00', total_paid: '20.00', total_balance: '80.00', ledger_entries: [bill] });
  const view = render(<QueryClientProvider client={queryClient}><StudentFeePanel year="2083/084" student={student} canCollect={false} canCreate={false} onReceipt={() => undefined} /></QueryClientProvider>);
  assert.equal(view.queryByRole('button', { name: 'Collect' }), null);
  assert.equal(view.queryByRole('button', { name: 'Concession' }), null);
  assert.ok(view.getByText('2083-01-10 BS'));
  assert.ok(view.getByText('overdue'));
  queryClient.clear();
});

test('single-bill waiver sends only the selected ledger and preserves decimal strings', async () => {
  const queryClient = client();
  const original = apiClient.fees.award;
  let submitted: Record<string, unknown> | undefined;
  apiClient.fees.award = async (data) => { submitted = data as Record<string, unknown>; return { success: false, data: null as never, error: { message: 'Test validation response' } }; };
  try {
    const view = render(<QueryClientProvider client={queryClient}><ScholarshipDialog year="2083/084" student={student} outstanding="200.00" bill={bill} onClose={() => undefined} /></QueryClientProvider>);
    fireEvent.click(view.getByRole('button', { name: 'Apply concession' }));
    await waitFor(() => assert.ok(submitted));
    assert.deepEqual(submitted!.ledger_ids, ['bill-1']);
    assert.equal(submitted!.discount_value, '100');
    assert.equal(submitted!.discount_type, 'percentage');
  } finally { apiClient.fees.award = original; queryClient.clear(); }
});

test('billing shows all 125 students, and optional fees are excluded from the initial estimate', () => {
  const queryClient = client();
  const structure: FeeStructure = { id: 'plan-1', school_id: 'school-1', grade: '2', academic_year_bs: '2083/084', name: 'School fees', description: null, is_active: true,
    fee_heads: [ { id: 'head-1', fee_structure_id: 'plan-1', name: 'Tuition', amount: '100.00', frequency: 'monthly', is_optional: false, is_billed: false },
      { id: 'head-2', fee_structure_id: 'plan-1', name: 'Transport', amount: '20.00', frequency: 'monthly', is_optional: true, is_billed: false } ] };
  queryClient.setQueryData(['fees', 'structures', '2083/084', '', true], [structure]);
  queryClient.setQueryData(['students', 'roster', 2, undefined], { students: Array.from({ length: 125 }, (_, index) => ({ id: `student-${index}`, full_name_en: `Synthetic Student ${index}`, roll_number: index + 1, admission_number: null, emis_student_id: null })), total: 125 });
  const view = render(<QueryClientProvider client={queryClient}><FeeBilling year="2083/084" grade="" /></QueryClientProvider>);
  fireEvent.click(view.getByLabelText('Select all 125 students'));
  assert.ok(view.getByRole('button', { name: 'Generate 1500 bills' }));
  fireEvent.click(view.getByLabelText(/Transport/));
  assert.ok(view.getByRole('button', { name: 'Generate 3000 bills' }));
  queryClient.clear();
});
