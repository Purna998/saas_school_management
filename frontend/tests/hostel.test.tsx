import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HostelSetup, RoomEditor } from '../components/hostel/HostelSetup';
import { BedStockForm } from '../components/hostel/HostelInventory';
import { HostelAdmission } from '../components/hostel/HostelAdmission';
import { HostelOperationDialog, HostelBillDialog } from '../components/hostel/HostelOperations';
import { HostelRegister } from '../components/hostel/HostelRegister';
import { HostelResidents } from '../components/hostel/HostelResidents';
import { apiClient } from '../lib/api/client';
import { nepalDate } from '../lib/api/library';
import { normalizeBsInput, registerChoices } from '../lib/api/hostel';
import type { Hostel, HostelRoom, Resident } from '../lib/api/hostel';

afterEach(cleanup);
const noop = () => {};
const day = nepalDate(); const bs = '2083-07-09';
const conversion = { bs_date: { year: 2083, month: 7, day: 9 }, ad_date: { iso_date: day } };
const hostel: Hostel = { id: 'hostel-1', name: 'Synthetic छात्रावास', hostel_type: 'mixed', warden_name: 'Synthetic Warden', warden_phone: '+9779800000000', address: 'Pokhara', notes: null, total_rooms: 1, capacity: 2, is_active: true };
const room: HostelRoom = { id: 'room-1', hostel_id: hostel.id, hostel_name: hostel.name, hostel_type: 'mixed', hostel_active: true, room_number: 'क-१०', floor: 0, capacity: 2, occupied: 1, available_beds: 1, room_type: 'double', monthly_fee: '2500.25', is_active: true, notes: null };
const resident: Resident = { id: 'stay-1', room_id: room.id, bed_id: 'bed-1', student_id: 'student-1', student_name: 'Synthetic Boarder', student_reference: 'ADM-1', hostel_name: hostel.name, room_number: room.room_number, bed_label: 'B-0001', monthly_fee: '2500.25', allocated_date_ad: day, allocated_date_bs: bs, vacated_date_ad: null, vacated_date_bs: null, academic_year_bs: '2083/084', notes: null, checkout_reason: null, previous_allocation_id: null, status: 'active', leave_id: null, expected_return_ad: null, expected_return_bs: null, return_overdue: false };
function client() { const value = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } } }); value.setQueryData(['calendar', 'nepal-date', day], conversion); value.setQueryData(['calendar', 'bs-ad', bs], conversion); return value; }
function rejected() { return { success: false, data: null as never, error: { message: 'Temporary connection failure' } }; }

test('hostel date inputs accept Nepali digits and meal statuses remain separate from roll call', () => {
  assert.equal(normalizeBsInput('२०८३-०७-०९'), bs);
  assert.deepEqual(registerChoices('dinner'), ['taken', 'skipped']);
  assert.deepEqual(registerChoices('evening'), ['present', 'absent', 'on_leave', 'excused']);
});

test('read-only hostel staff see configured rooms without editing or allocation controls', async () => {
  const queryClient = client(); queryClient.setQueryData(['hostel', 'hostels', 1, '', true], { hostels: [hostel], total: 1 }); queryClient.setQueryData(['hostel', 'hostel', hostel.id], hostel); queryClient.setQueryData(['hostel', 'rooms', hostel.id, 1, true, false], { rooms: [room], total: 1 });
  const view = render(<QueryClientProvider client={queryClient}><HostelSetup canEdit={false} canAllocate={false} onHostel={noop} onRoom={noop} onBeds={noop} onAllocate={noop} /></QueryClientProvider>);
  fireEvent.click(view.getByRole('button', { name: 'View rooms' })); await view.findByText(room.room_number);
  for (const name of ['Add hostel', 'Edit hostel', 'Add room', 'Edit room', 'Allocate bed']) assert.equal(view.queryByRole('button', { name }), null);
  assert.ok(view.getByRole('button', { name: 'Bed register' })); queryClient.clear();
});

test('editing a room preserves exact NPR input and manages capacity through beds', async () => {
  const queryClient = client(); const original = apiClient.hostel.updateRoom; let payload: Record<string, unknown> | undefined;
  apiClient.hostel.updateRoom = async (_id, value) => { payload = value as Record<string, unknown>; return rejected(); };
  try {
    const view = render(<QueryClientProvider client={queryClient}><RoomEditor hostel={hostel} room={room} onClose={noop} /></QueryClientProvider>);
    assert.equal(view.queryByLabelText('Initial beds'), null);
    fireEvent.change(view.getByLabelText('Monthly hostel charge (NPR)'), { target: { value: '3000.01' } }); fireEvent.click(view.getByRole('button', { name: 'Save room' }));
    await waitFor(() => assert.ok(payload)); assert.equal(payload!.monthly_fee, '3000.01'); assert.equal('capacity' in payload!, false);
  } finally { apiClient.hostel.updateRoom = original; queryClient.clear(); }
});

test('bed acquisition retries use one request UUID and edited labels create a new intent', async () => {
  const queryClient = client(); const original = apiClient.hostel.addBeds; const requests: Array<Record<string, unknown>> = [];
  apiClient.hostel.addBeds = async (_id, value) => { requests.push(value as Record<string, unknown>); return rejected(); };
  try {
    const view = render(<QueryClientProvider client={queryClient}><BedStockForm roomId={room.id} onClose={noop} onBusy={noop} /></QueryClientProvider>);
    const submit = async (count: number) => { fireEvent.click(view.getByRole('button', { name: 'Add beds' })); await waitFor(() => assert.equal(requests.length, count)); await waitFor(() => assert.ok(view.getByRole('button', { name: 'Add beds' }))); };
    await submit(1); await submit(2); assert.equal(requests[0].request_id, requests[1].request_id);
    fireEvent.change(view.getByLabelText('Existing bed labels (optional, one per line)'), { target: { value: 'शय्या-१' } }); await submit(3);
    assert.notEqual(requests[1].request_id, requests[2].request_id); assert.deepEqual(requests[2].labels, ['शय्या-१']);
  } finally { apiClient.hostel.addBeds = original; queryClient.clear(); }
});

test('admission selects the exact bed and eligible student while blocking an existing boarder', async () => {
  const queryClient = client(); const original = apiClient.hostel.allocate; const requests: Array<Record<string, unknown>> = [];
  queryClient.setQueryData(['hostel', 'students', '', 1], { students: [{ id: 'student-1', full_name_en: 'Synthetic Boarder', admission_number: 'ADM-1', current_grade: 2, current_section: 'A', roll_number: 3, gender: 'other', active_allocation_id: null }, { id: 'student-2', full_name_en: 'Already Boarding', admission_number: 'ADM-2', current_grade: 2, current_section: 'A', gender: 'other', active_allocation_id: 'stay-2' }], total: 2 });
  apiClient.hostel.allocate = async (value) => { requests.push(value as Record<string, unknown>); return rejected(); };
  try {
    const view = render(<QueryClientProvider client={queryClient}><HostelAdmission initialRoom={room} bedId="bed-2" bedLabel="शय्या-२" onClose={noop} onResident={noop} /></QueryClientProvider>);
    assert.equal((view.getByRole('button', { name: /Already Boarding/ }) as HTMLButtonElement).disabled, true);
    fireEvent.click(view.getByRole('button', { name: /Synthetic Boarder.*ADM-1/ }));
    const submit = async (count: number) => { fireEvent.click(view.getByRole('button', { name: 'Allocate bed' })); await waitFor(() => assert.equal(requests.length, count)); await waitFor(() => assert.ok(view.getByRole('button', { name: 'Allocate bed' }))); };
    await submit(1); await submit(2); assert.equal(requests[0].student_id, 'student-1'); assert.equal(requests[0].bed_id, 'bed-2'); assert.equal(requests[0].request_id, requests[1].request_id);
  } finally { apiClient.hostel.allocate = original; queryClient.clear(); }
});

test('approved leave accepts a BS return date and sends its validated AD conversion', async () => {
  const queryClient = client(); const original = apiClient.hostel.leave; let payload: Record<string, unknown> | undefined;
  apiClient.hostel.leave = async (_id, value) => { payload = value as Record<string, unknown>; return rejected(); };
  try {
    const view = render(<QueryClientProvider client={queryClient}><HostelOperationDialog action="leave" stay={resident} onClose={noop} onResident={noop} /></QueryClientProvider>);
    fireEvent.change(view.getByLabelText('Expected return date (BS)'), { target: { value: '२०८३-०७-०९' } });
    fireEvent.change(view.getByLabelText('Destination'), { target: { value: 'पोखरा' } }); fireEvent.change(view.getByLabelText('Responsible guardian / person'), { target: { value: 'Synthetic guardian' } }); fireEvent.change(view.getByLabelText('Approved leave reason'), { target: { value: 'School approved family visit' } });
    fireEvent.click(view.getByRole('button', { name: 'Record departure' })); await waitFor(() => assert.ok(payload)); assert.equal(payload!.expected_return_ad, day); assert.equal(payload!.responsible_person, 'Synthetic guardian');
  } finally { apiClient.hostel.leave = original; queryClient.clear(); }
});

test('register keeps unmarked residents unmarked, preserves versions and retains failed edits', async () => {
  const queryClient = client(); const original = apiClient.hostel.saveRegister; const requests: Array<Record<string, unknown>> = []; let dirty = false;
  queryClient.setQueryData(['hostel', 'register', day, 'evening', 1, ''], { entries: [{ ...resident, recorded_status: 'present', recorded_notes: null, version: 4 }, { ...resident, id: 'stay-2', student_name: 'Unmarked Boarder', recorded_status: null, recorded_notes: null, version: 0 }], total: 2, date_ad: day, date_bs: bs, session: 'evening' });
  apiClient.hostel.saveRegister = async (value) => { requests.push(value as Record<string, unknown>); return rejected(); };
  try {
    const view = render(<QueryClientProvider client={queryClient}><HostelRegister canAllocate onDirtyChange={(value) => { dirty = value; }} /></QueryClientProvider>);
    assert.equal((view.getByLabelText('Status for Unmarked Boarder') as HTMLSelectElement).value, '');
    fireEvent.change(view.getByLabelText('Status for Synthetic Boarder'), { target: { value: 'absent' } });
    const notes = view.getByLabelText('Notes for Synthetic Boarder') as HTMLInputElement; assert.equal(notes.required, true);
    fireEvent.change(notes, { target: { value: 'Warden checking with guardian' } }); assert.equal(dirty, true);
    const submit = async (count: number) => { fireEvent.click(view.getByRole('button', { name: 'Save 1 changes' })); await waitFor(() => assert.equal(requests.length, count)); await waitFor(() => assert.ok(view.getByRole('button', { name: 'Save 1 changes' }))); };
    await submit(1); await submit(2); assert.equal(requests[0].request_id, requests[1].request_id);
    assert.deepEqual(requests[0].entries, [{ allocation_id: resident.id, status: 'absent', notes: 'Warden checking with guardian', version: 4 }]);
    assert.equal((view.getByLabelText('Session / meal').closest('fieldset') as HTMLFieldSetElement).disabled, true);
  } finally { apiClient.hostel.saveRegister = original; queryClient.clear(); }
});

test('read-only resident registers hide admission and retain BS/AD records', () => {
  const queryClient = client(); queryClient.setQueryData(['hostel', 'residents', { search: '', status: 'active' }, 1], { residents: [resident], total: 1 });
  const view = render(<QueryClientProvider client={queryClient}><HostelResidents canAllocate={false} onAdmit={noop} onResident={noop} /></QueryClientProvider>);
  assert.equal(view.queryByRole('button', { name: 'Admit boarder' }), null); assert.ok(view.getByText(`${bs} BS`)); assert.ok(view.getByText(`${day} AD`)); queryClient.clear();
});

test('hostel bills require the matching fee head and explicit monthly approval', async () => {
  const queryClient = client(); const original = apiClient.hostel.bill; const requests: Array<Record<string, unknown>> = [];
  queryClient.setQueryData(['hostel', 'fee-options', resident.id, '2083-07'], { monthly_fee: '2500.25', academic_year_bs: '2083/084', options: [{ id: 'hostel-head', name: 'Hostel lodging & mess', amount: '2500.25', structure_name: 'Grade 2 fees' }, { id: 'wrong-price', name: 'Different charge', amount: '3000.00', structure_name: 'Grade 2 fees' }] });
  apiClient.hostel.bill = async (_id, value) => { requests.push(value as Record<string, unknown>); return rejected(); };
  try {
    const view = render(<QueryClientProvider client={queryClient}><HostelBillDialog stay={resident} onClose={noop} /></QueryClientProvider>);
    assert.equal(view.queryByRole('option', { name: /Different charge/ }), null);
    assert.equal((view.getByRole('button', { name: 'Post hostel bill' }) as HTMLButtonElement).disabled, true);
    fireEvent.change(view.getByLabelText('Hostel fee head'), { target: { value: 'hostel-head' } }); fireEvent.click(view.getByLabelText(/school has approved the full monthly charge/));
    fireEvent.click(view.getByRole('button', { name: 'Post hostel bill' })); await waitFor(() => assert.equal(requests.length, 1));
    assert.equal(requests[0].month_bs, '2083-07'); assert.equal(requests[0].fee_head_id, 'hostel-head'); assert.equal(requests[0].due_day_bs, 10);
  } finally { apiClient.hostel.bill = original; queryClient.clear(); }
});
