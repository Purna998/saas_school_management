import type { ApiResponse } from './client';

export interface TrackingStop {
  id: string; name: string; order: number; latitude: string | null; longitude: string | null;
  scheduled_time: string | null;
}
export interface TrackingFix {
  latitude: string; longitude: string; accuracy_m: string; speed_mps: string | null; heading: string | null;
  recorded_at: string; received_at: string;
}
export interface TrackingProgress {
  stop_id?: string; name?: string; order?: number; stage?: 'arriving' | 'at_stop' | 'departed';
  version?: number; updated_at?: string;
}
export interface TrackingJourney {
  id: string; trip_id: string; run_name: string; route_name: string; vehicle_number: string;
  direction: 'pickup' | 'drop'; status: 'in_progress' | 'completed' | 'cancelled'; date_bs: string;
  started_at: string; position: TrackingFix | null; progress: TrackingProgress | null; stops: TrackingStop[];
  child: { id: string; name: string; status: string; boarded_at: string | null; alighted_at: string | null } | null;
  stop: TrackingStop | null;
  guidance: { nearby: boolean; distance_m: number | null; stops_away: number | null; stop_state: string | null };
}
export interface TrackingFeed {
  audience: 'staff' | 'family'; journeys: TrackingJourney[]; total: number; page: number;
  server_time: string; refresh_seconds: number;
}
export interface FamilyAccess {
  id: string; student_id: string; student_name: string; parent_email: string; notes: string; created_at: string;
}
export interface PhoneContext {
  trip_id: string; vehicle_number: string; run_name: string; direction: string; sender_label: string;
  expires_at: string; stops: TrackingStop[]; progress: TrackingProgress; send_interval_seconds: number;
}
export interface PhoneGrant { id: string; label: string; expires_at: string; token: string }
export interface PhoneFix {
  latitude: string; longitude: string; accuracy_m: string; speed_mps: string | null; heading: string | null;
  recorded_at: string;
}

export function locationState(fix: TrackingFix | null, time = Date.now(), connected = true) {
  if (!fix) return { label: 'Waiting for GPS', age: null, live: false, tone: 'muted' };
  const seconds = Math.max(0, Math.floor((time - Date.parse(fix.recorded_at)) / 1000));
  if (!Number.isFinite(seconds)) return { label: 'Location unavailable', age: null, live: false, tone: 'muted' };
  if (!connected) return { label: 'Connection interrupted', age: seconds, live: false, tone: 'muted' };
  if (seconds > 120) return { label: 'GPS offline · last known', age: seconds, live: false, tone: 'muted' };
  if (seconds > 30) return { label: 'GPS delayed', age: seconds, live: false, tone: 'amber' };
  if (Number(fix.accuracy_m) > 100) return { label: 'GPS signal imprecise', age: seconds, live: false, tone: 'amber' };
  return { label: 'Live location', age: seconds, live: true, tone: 'green' };
}
export function nearbyMessage(journey: TrackingJourney, time = Date.now(), connected = true) {
  const state = locationState(journey.position, time, connected);
  if (!state.live || !journey.guidance.nearby || journey.status !== 'in_progress') return null;
  if (journey.direction === 'drop' && journey.child?.status === 'boarded') return 'The vehicle is near your stop. Please be ready to receive your child.';
  if (journey.direction === 'pickup' && journey.child?.status === 'pending') return 'The vehicle is near your pickup stop. Please be ready with your child.';
  return null;
}

const base = (process.env.NEXT_PUBLIC_API_URL ?? '/backend').replace(/\/$/, '');
// A trip capability never enters login storage, a query string, analytics or a Referer.
export async function phoneRequest<T>(token: string, path: 'context' | 'position' | 'progress', data?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${base}/api/v1/transport/phone/${path}`, {
    method: data === undefined ? 'GET' : 'POST', cache: 'no-store', credentials: 'omit', referrerPolicy: 'no-referrer',
    headers: { 'X-Transport-Token': token, ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: data === undefined ? undefined : JSON.stringify(data), signal,
  });
  const payload = await response.json();
  if (!response.ok) {
    const error = new Error(typeof payload.detail === 'string' ? payload.detail : payload.detail?.error?.message ?? 'Unable to send the trip update') as Error & { status: number };
    error.status = response.status;
    throw error;
  }
  return (payload as ApiResponse<T>).data;
}
