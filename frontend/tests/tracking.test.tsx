import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { locationState, nearbyMessage, phoneRequest } from '../lib/api/tracking';
import type { TrackingJourney } from '../lib/api/tracking';
import { PhoneLocationSender } from '../lib/transport/phone-sender';
import type { SenderState } from '../lib/transport/phone-sender';
import { useScreenAwake } from '../lib/transport/useScreenAwake';
import { JourneyCard } from '../components/transport/LiveTransport';
import { FamilySetup, PhoneSetup } from '../components/transport/TrackingSetup';
import { apiClient } from '../lib/api/client';
import { getNavigation, isNavigationActive } from '../components/layout/navigation';
import type { User } from '../lib/store/auth';

afterEach(cleanup);
const clock = Date.parse('2026-10-26T10:00:00+05:45');
const journey: TrackingJourney = {
  id: 'journey-1', trip_id: 'trip-1', run_name: 'Home route', route_name: 'Local route', vehicle_number: 'बा 2 ख 1234',
  direction: 'drop', status: 'in_progress', date_bs: '2083-07-09', started_at: new Date(clock - 600000).toISOString(),
  position: { latitude: '28.20', longitude: '83.98', accuracy_m: '8.5', speed_mps: null, heading: null, recorded_at: new Date(clock).toISOString(), received_at: new Date(clock).toISOString() },
  progress: null, stops: [], child: { id: 'student-1', name: 'Synthetic Child', status: 'boarded', boarded_at: new Date(clock - 500000).toISOString(), alighted_at: null },
  stop: { id: 'stop-1', name: 'टोल चौक', order: 1, latitude: '28.20', longitude: '83.98', scheduled_time: '15:10:00' },
  guidance: { nearby: true, distance_m: 5, stops_away: 0, stop_state: 'arriving' },
};
const gps = { coords: { latitude: 28.2, longitude: 83.98, accuracy: 8.25, altitude: null, altitudeAccuracy: null, heading: null, speed: null }, timestamp: clock } as GeolocationPosition;
const noop = () => {};
function queries() { return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity }, mutations: { retry: false, gcTime: 0 } } }); }
async function flush() { await new Promise<void>((resolve) => setImmediate(resolve)); }

test('GPS freshness never labels stale, imprecise or disconnected coordinates live', () => {
  assert.equal(locationState(journey.position, clock).live, true);
  assert.equal(locationState(journey.position, clock + 31000).label, 'GPS delayed');
  assert.equal(locationState(journey.position, clock + 121000).label, 'GPS offline · last known');
  assert.equal(locationState({ ...journey.position!, accuracy_m: '101' }, clock).live, false);
  assert.equal(locationState(journey.position, clock, false).live, false);
  assert.equal(locationState(null, clock).label, 'Waiting for GPS');
});

test('nearby handover guidance disappears for stale GPS, absence and finished journeys', () => {
  assert.match(nearbyMessage(journey, clock)!, /receive your child/);
  assert.equal(nearbyMessage(journey, clock + 31000), null);
  assert.equal(nearbyMessage(journey, clock, false), null);
  assert.equal(nearbyMessage({ ...journey, child: { ...journey.child!, status: 'absent' } }, clock), null);
  assert.equal(nearbyMessage({ ...journey, status: 'completed' }, clock), null);
  assert.match(nearbyMessage({ ...journey, direction: 'pickup', child: { ...journey.child!, status: 'pending' } }, clock)!, /pickup stop/);
});

test('parent journey card distinguishes staff boarding from fresh nearby location', () => {
  const view = render(<JourneyCard journey={journey} selected onSelect={noop} time={clock} connected/>);
  assert.ok(view.getByText('On the vehicle'));
  assert.ok(view.getByText(/Please be ready to receive your child/));
  view.rerender(<JourneyCard journey={journey} selected onSelect={noop} time={clock + 121000} connected/>);
  assert.ok(view.getByText('GPS offline · last known'));
  assert.equal(view.queryByText(/Please be ready to receive your child/), null);
  view.rerender(<JourneyCard journey={{ ...journey, stop: { ...journey.stop!, latitude: null, longitude: null }, guidance: { ...journey.guidance, nearby: false } }} selected onSelect={noop} time={clock} connected/>);
  assert.ok(view.getByText(/Your stop has no mapped location yet/));
  view.rerender(<JourneyCard journey={{ ...journey, position: null, child: { ...journey.child!, status: 'alighted' } }} selected onSelect={noop} time={clock} connected/>);
  assert.ok(view.getByText(/Vehicle location is no longer shared/));
  assert.equal(view.queryByRole('link'), null);
});

test('phone sender ignores a late GPS callback after stopping', async () => {
  let locate!: (position: GeolocationPosition) => void;
  let sends = 0;
  const states: SenderState[] = [];
  const sender = new PhoneLocationSender({ locate: () => new Promise((resolve) => { locate = resolve; }), send: async () => { sends++; }, onState: (state) => states.push(state), interval: 5 });
  sender.start(); sender.stop(); locate(gps); await flush();
  assert.equal(sends, 0);
  assert.equal(states.at(-1)?.phase, 'idle');
  sender.dispose();
});

test('phone sender pauses hidden/offline and resumes only after prior consent to start', async () => {
  let sends = 0;
  const states: SenderState[] = [];
  const sender = new PhoneLocationSender({ locate: async () => gps, send: async (fix) => { sends++; assert.equal(fix.recorded_at, new Date(clock).toISOString()); }, onState: (state) => states.push(state), interval: 100000 });
  sender.availability(false, true); sender.availability(true, true); await flush();
  assert.equal(sends, 0);
  sender.start(); await flush(); assert.equal(sends, 1);
  sender.availability(false, true); assert.equal(states.at(-1)?.phase, 'paused');
  sender.availability(true, false); await flush(); assert.equal(sends, 1);
  sender.availability(true, true); await flush(); assert.equal(sends, 2);
  sender.stop(); sender.availability(false, true); sender.availability(true, true); await flush(); assert.equal(sends, 2);
  sender.dispose();
});

test('revoked phone code is terminal and no overlapping GPS upload starts', async () => {
  let reject!: (error: Error) => void, sends = 0;
  const states: SenderState[] = [];
  const sender = new PhoneLocationSender({ locate: async () => gps, send: () => { sends++; return new Promise((_resolve, fail) => { reject = fail; }); }, onState: (state) => states.push(state), interval: 1 });
  sender.start(); await flush(); assert.equal(sends, 1);
  await new Promise((resolve) => setTimeout(resolve, 10)); assert.equal(sends, 1);
  reject(Object.assign(new Error('Trip link revoked'), { status: 410 })); await flush();
  assert.equal(states.at(-1)?.phase, 'ended');
  await new Promise((resolve) => setTimeout(resolve, 10)); assert.equal(sends, 1);
  sender.dispose();
});

test('phone API uses a header, omits credentials and never puts the code in its URL', async () => {
  const original = globalThis.fetch;
  let called = '';
  globalThis.fetch = async (url, init) => {
    called = String(url);
    assert.equal((init?.headers as Record<string, string>)['X-Transport-Token'], 'private-trip-token');
    assert.equal(init?.credentials, 'omit'); assert.equal(init?.cache, 'no-store'); assert.equal(init?.referrerPolicy, 'no-referrer');
    return new Response(JSON.stringify({ success: true, data: { accepted: true } }), { status: 200 });
  };
  try { await phoneRequest('private-trip-token', 'position', { latitude: '28.2' }); assert.equal(called.includes('private-trip-token'), false); }
  finally { globalThis.fetch = original; }
});

function WakeProbe({active}: {active: boolean}) { return <p>{useScreenAwake(active)}</p>; }
test('screen wake protection releases when phone sharing stops', async () => {
  let requested = 0, released = 0;
  Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: { request: async () => { requested++; return { release: async () => { released++; }, addEventListener: noop }; } } });
  try {
    const view = render(<WakeProbe active={false}/>);
    await flush(); assert.equal(requested, 0);
    view.rerender(<WakeProbe active/>);
    await waitFor(() => assert.ok(view.getByText('Keeping this screen awake while sharing.')));
    assert.equal(requested, 1);
    view.rerender(<WakeProbe active={false}/>);
    await waitFor(() => assert.equal(released, 1));
  } finally { delete (navigator as unknown as { wakeLock?: unknown }).wakeLock; }
});

test('parent account navigation exposes child journeys without office transport access', () => {
  const user: User = { id: 'parent-1', email: 'parent@example.com', full_name: 'Parent', role: 'parent', tenant_id: 'school-1', permissions: [] };
  const menu = getNavigation(user);
  assert.ok(menu.some((item) => item.href === '/dashboard/transport/live'));
  assert.equal(menu.some((item) => item.href === '/dashboard/transport'), false);
  assert.equal(isNavigationActive('/dashboard/transport/live', '/dashboard/transport'), false);
  assert.ok(getNavigation({ ...user, role: 'teacher', permissions: ['transport:track'] }).some((item) => item.href === '/dashboard/transport/live'));
});

test('verified parent linking requires office confirmation and retains request UUID on retry', async () => {
  const q = queries(), original = apiClient.tracking.link;
  const student = { id: 'student-1', full_name_en: 'Synthetic Child', full_name_np: null, admission_number: 'ADM-1', emis_student_id: null, current_grade: 2, current_section: 'A', roll_number: 1, active_assignment_id: null };
  q.setQueryData(['transport', 'picker', 'tracking-students', '', 1], { items: [student], total: 1 });
  q.setQueryData(['tracking', 'families', 1], { links: [], total: 0 });
  const requests: Array<Record<string, unknown>> = [];
  apiClient.tracking.link = async (payload) => { requests.push(payload as Record<string, unknown>); return { success: false, data: null as never, error: { message: 'Retry later' } }; };
  try {
    const view = render(<QueryClientProvider client={q}><FamilySetup onClose={noop}/></QueryClientProvider>);
    assert.equal((view.getByRole('button', { name: 'Enable parent journey access' }) as HTMLButtonElement).disabled, true);
    fireEvent.click(view.getByRole('button', { name: /Synthetic Child/ }));
    fireEvent.change(view.getByLabelText('Existing parent account email'), { target: { value: 'parent@example.com' } });
    fireEvent.change(view.getByLabelText('School verification note'), { target: { value: 'School verified guardian record' } });
    fireEvent.click(view.getByRole('checkbox'));
    fireEvent.click(view.getByRole('button', { name: 'Enable parent journey access' }));
    await waitFor(() => assert.equal(requests.length, 1));
    await waitFor(() => assert.ok(view.getByText('Retry later')));
    fireEvent.click(view.getByRole('button', { name: 'Enable parent journey access' }));
    await waitFor(() => assert.equal(requests.length, 2));
    assert.deepEqual(requests[0], requests[1]); assert.equal(requests[0].student_id, student.id);
  } finally { apiClient.tracking.link = original; q.clear(); }
});

test('sharing link keeps a fragment secret and can be revoked immediately', async () => {
  const q = queries(), issue = apiClient.tracking.issuePhone, revoke = apiClient.tracking.revokePhone;
  let revoked = false;
  apiClient.tracking.issuePhone = async () => ({ success: true, data: { id: 'grant-1', label: 'Helper', expires_at: new Date(clock + 3600000).toISOString(), token: 'opaque-private-token' } });
  apiClient.tracking.revokePhone = async () => { revoked = true; return { success: true, data: { status: 'revoked' } }; };
  try {
    const view = render(<QueryClientProvider client={q}><PhoneSetup tripId="trip-1" vehicle="Bus" onClose={noop}/></QueryClientProvider>);
    fireEvent.click(view.getByRole('button', { name: 'Create / replace sharing link' }));
    await waitFor(() => assert.equal((view.getByLabelText('Private trip sharing link') as HTMLInputElement).value, 'http://localhost:3001/transport/share#code=opaque-private-token'));
    fireEvent.click(view.getByRole('button', { name: 'Revoke trip phone access' }));
    await waitFor(() => assert.equal(revoked, true));
    await waitFor(() => assert.equal(view.queryByLabelText('Private trip sharing link'), null));
  } finally { apiClient.tracking.issuePhone = issue; apiClient.tracking.revokePhone = revoke; q.clear(); }
});
