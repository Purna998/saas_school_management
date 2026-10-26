'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { Bell, Bus, MapPin, RefreshCw, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api/client';
import { transportData, positionMapUrl } from '@/lib/api/transport';
import { locationState, nearbyMessage } from '@/lib/api/tracking';
import type { TrackingJourney } from '@/lib/api/tracking';
import { useAuthStore } from '@/lib/store/auth';
import { TransportEmpty, TransportPagination, transportStamp } from './TransportCommon';

const TrackingMap = dynamic(() => import('./TrackingMap'), { ssr: false, loading: () => <div className="flex h-[380px] items-center justify-center rounded-2xl border text-sm text-muted-foreground">Loading vehicle map…</div> });
const FamilySetup = dynamic(() => import('./TrackingSetup').then((module) => module.FamilySetup));
const PhoneSetup = dynamic(() => import('./TrackingSetup').then((module) => module.PhoneSetup));

const childStates: Record<string, string> = { pending: 'Waiting to board', boarded: 'On the vehicle', alighted: 'Alighted · staff recorded', absent: 'Marked absent', cancelled: 'Trip cancelled' };
function ageLabel(seconds: number | null) { return seconds === null ? 'No fix received' : seconds < 60 ? `${seconds}s ago` : `${Math.floor(seconds / 60)}m ${seconds % 60}s ago`; }

export function JourneyCard({ journey, selected, onSelect, time, connected }: {
  journey: TrackingJourney; selected: boolean; onSelect: () => void; time: number; connected: boolean;
}) {
  const state = locationState(journey.position, time, connected);
  const near = nearbyMessage(journey, time, connected);
  const mapLink = journey.position && positionMapUrl(journey.position);
  const final = journey.status !== 'in_progress' || (journey.child && !['pending', 'boarded'].includes(journey.child.status));
  return <article className={`rounded-2xl border p-4 transition-colors ${selected ? 'border-primary bg-primary/5' : 'bg-card'}`}>
    <button type="button" onClick={onSelect} aria-pressed={selected} className="w-full text-left focus-visible:outline-2 focus-visible:outline-primary"><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">{journey.child?.name ?? journey.vehicle_number}</h2><p className="mt-1 text-sm text-muted-foreground">{journey.child && `${journey.vehicle_number} · `}{journey.direction === 'drop' ? 'Home drop' : 'School pickup'}</p></div><Bus size={20} className="shrink-0 text-primary"/></div><p className="mt-3 text-xs text-muted-foreground">{journey.run_name} · {journey.date_bs} BS</p></button>
    {journey.child && <p className="mt-3 rounded-lg bg-background px-3 py-2 text-sm font-medium">{childStates[journey.child.status] ?? journey.child.status}</p>}
    {final ? <p className="mt-3 text-xs leading-5 text-muted-foreground">{journey.status === 'completed' ? 'Journey completed. ' : ''}Vehicle location is no longer shared for this journey.</p> : <div className="mt-3 space-y-2"><div className="flex flex-wrap items-center gap-2 text-xs"><span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-medium ${state.tone === 'green' ? 'bg-emerald-50 text-emerald-800' : state.tone === 'amber' ? 'bg-amber-50 text-amber-900' : 'bg-muted text-muted-foreground'}`}><span className={`h-1.5 w-1.5 rounded-full ${state.live ? 'bg-emerald-600' : 'bg-current'}`}/>{state.label}</span><span className="text-muted-foreground">{ageLabel(state.age)}</span></div>
      {journey.position && <p className="text-xs text-muted-foreground">GPS ±{Math.round(Number(journey.position.accuracy_m))} m · {transportStamp.format(new Date(journey.position.recorded_at))} NPT</p>}
      {journey.stop && <p className="text-sm"><MapPin size={14} className="mr-1 inline"/>{journey.stop.name}{journey.stop.scheduled_time && <span className="mt-1 block text-xs text-muted-foreground">Scheduled reference {journey.stop.scheduled_time.slice(0, 5)} NPT · timing can vary</span>}</p>}
      {journey.child && (!journey.stop || journey.stop.latitude === null || journey.stop.longitude === null) && <p className="text-xs text-muted-foreground">Your stop has no mapped location yet. Ask the school to add it for nearby guidance.</p>}
      {near && <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm leading-6 text-emerald-950">{near}<span className="mt-1 block text-xs">Within approximately 300 m in a straight line. This is a nearby signal, not an arrival guarantee.</span></p>}
      {journey.child && connected && !near && journey.guidance.stops_away !== null && <p className="text-xs text-muted-foreground">{journey.guidance.stops_away === 0 ? `Helper reported your stop: ${journey.guidance.stop_state?.replace('_', ' ')}` : `${journey.guidance.stops_away} assigned stop(s) ahead · helper report`}</p>}
      {journey.child && connected && journey.guidance.stop_state === 'passed' && <p className="text-xs text-amber-900">Helper reports the vehicle has passed your stop. Contact the school if a handover is still pending.</p>}
      {!journey.child && journey.progress?.name && <p className="text-xs text-muted-foreground">Helper report: {journey.progress.name} · {journey.progress.stage?.replace('_', ' ')}{journey.progress.updated_at && ` · ${transportStamp.format(new Date(journey.progress.updated_at))} NPT`}</p>}
      {mapLink && <a className="inline-block pt-1 text-xs text-primary underline underline-offset-4" href={mapLink} target="_blank" rel="noopener noreferrer">Open last reported position in map</a>}
    </div>}
  </article>;
}

export default function LiveTransport() {
  const user = useAuthStore((state) => state.user);
  const permissions = new Set(user?.permissions ?? []);
  const canManage = permissions.has('transport:create') && permissions.has('transport:read');
  const canView = user?.role === 'parent' || canManage || ((user?.role !== 'student') && (permissions.has('transport:track') || permissions.has('transport:read') || permissions.has('*:*')));
  const [page, setPage] = useState(1), [selectedId, setSelectedId] = useState<string | null>(null);
  const [time, setTime] = useState(() => Date.now());
  const [visible, setVisible] = useState(true), [online, setOnline] = useState(true);
  const [familySetup, setFamilySetup] = useState(false), [phoneTrip, setPhoneTrip] = useState<TrackingJourney | null>(null);
  const [alerts, setAlerts] = useState(false), [alertNote, setAlertNote] = useState('');
  const notified = useRef(new Set<string>());
  const feed = useQuery({
    queryKey: ['tracking', 'live', user?.id, page], enabled: Boolean(user && canView && visible && online),
    queryFn: async () => transportData(await apiClient.tracking.live(page)), staleTime: 5000, gcTime: 0,
    refetchInterval: (query) => visible && online ? query.state.error ? 30000 : 10000 : false,
    refetchIntervalInBackground: false, refetchOnWindowFocus: true, retry: false,
  });
  useEffect(() => {
    const update = () => { setVisible(!document.hidden); setOnline(navigator.onLine); setTime(Date.now()); };
    update();
    const timer = window.setInterval(() => { if (!document.hidden) setTime(Date.now()); }, 5000);
    document.addEventListener('visibilitychange', update); window.addEventListener('online', update); window.addEventListener('offline', update);
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', update); window.removeEventListener('online', update); window.removeEventListener('offline', update); };
  }, []);
  const journeys = feed.data?.journeys ?? [];
  const selected = journeys.find((journey) => journey.id === selectedId) ?? journeys[0];
  const connected = online && !feed.error && Boolean(feed.data) && time - feed.dataUpdatedAt <= 30000;
  const serverTime = feed.data ? Date.parse(feed.data.server_time) + Math.max(0, time - feed.dataUpdatedAt) : time;
  useEffect(() => {
    if (!alerts || !visible || !connected || typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
    feed.data?.journeys.forEach((journey) => {
      const message = nearbyMessage(journey, serverTime, connected);
      if (!message || notified.current.has(journey.id)) return;
      notified.current.add(journey.id);
      try { new Notification(`School transport · ${journey.child?.name ?? journey.vehicle_number}`, { body: message, tag: journey.id }); } catch { /* In-app guidance always remains available. */ }
    });
  }, [alerts, visible, connected, feed.data, serverTime]);
  const enableAlerts = async () => {
    if (typeof Notification === 'undefined') { setAlertNote('Browser notifications are unavailable. Nearby guidance will appear on this screen.'); return; }
    try { const permission = await Notification.requestPermission(); setAlerts(permission === 'granted'); setAlertNote(permission === 'granted' ? 'Nearby alerts enabled while this screen is open.' : 'Notifications were not enabled. Keep this screen open for nearby guidance.'); } catch { setAlertNote('Keep this screen open for nearby guidance.'); }
  };

  if (!canView) return <TransportEmpty>Live transport requires a verified parent login or school tracking permission.</TransportEmpty>;
  return <div className="space-y-5">
    <header className="flex flex-wrap items-start justify-between gap-4"><div><div className="mb-2 inline-flex items-center gap-2 text-xs font-medium text-primary"><ShieldCheck size={15}/>Private school transport</div><h1 className="text-2xl font-semibold">{feed.data?.audience === 'family' || user?.role === 'parent' ? 'Your child’s journey' : 'Live vehicle tracking'}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{user?.role === 'parent' ? 'See your linked children’s trip, reported boarding state and vehicle position.' : 'A single view of active school vehicles, GPS freshness and reported stop progress.'}</p></div><div className="flex flex-wrap gap-2">{canManage && <Button variant="outline" onClick={() => setFamilySetup(true)}>Parent access</Button>}{user?.role === 'parent' && <Button variant="outline" onClick={enableAlerts} disabled={alerts}><Bell size={16}/>{alerts ? 'Nearby alerts enabled' : 'Enable nearby alerts'}</Button>}<Button variant="outline" disabled={feed.isFetching || !online} onClick={() => feed.refetch()}><RefreshCw size={16} className={feed.isFetching ? 'animate-spin' : ''}/>Refresh</Button></div></header>
    {alertNote && <p role="status" className="text-sm text-muted-foreground">{alertNote}</p>}
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3 text-xs"><p className="text-muted-foreground">{connected ? 'Updating about every 10 seconds while visible' : !online ? 'You are offline. Showing saved information; location guidance is paused.' : feed.error ? 'Connection interrupted. Showing last received information; retrying.' : 'Connecting to school transport…'}</p>{feed.data && <span>Last sync {transportStamp.format(new Date(feed.data.server_time))} NPT</span>}</div>
    {feed.error && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">{feed.error.message}</p>}
    {feed.isPending ? <TransportEmpty>Loading authorized journeys…</TransportEmpty> : !journeys.length ? <section className="rounded-2xl border bg-card p-8 text-center"><Bus size={36} className="mx-auto text-primary"/><h2 className="mt-4 font-semibold">{user?.role === 'parent' ? 'No current journey to show' : 'No vehicles dispatched yet'}</h2><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">{user?.role === 'parent' ? 'Journeys appear after the school verifies your parent account link and dispatches your child’s vehicle. Contact the transport office if a journey is missing.' : 'Start a scheduled trip in Transport, then connect the assigned helper’s phone. Real GPS updates will appear here.'}</p>{canManage && <Button asChild variant="outline" className="mt-4"><Link href="/dashboard/transport">Open dispatch & trips</Link></Button>}</section> : <>
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(280px,350px)_1fr]"><section aria-label="Authorized journeys" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">{journeys.map((journey) => <JourneyCard key={journey.id} journey={journey} selected={selected?.id === journey.id} onSelect={() => setSelectedId(journey.id)} time={serverTime} connected={connected}/>)}</section><div className="space-y-4 xl:sticky xl:top-5"><TrackingMap journeys={journeys} selectedId={selected?.id ?? null} onSelect={setSelectedId} time={serverTime} connected={connected}/>{canManage && selected && <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-4"><div><h2 className="text-sm font-semibold">{selected.vehicle_number} · trip phone</h2><p className="mt-1 text-xs text-muted-foreground">Create, replace or revoke the helper’s location-sharing link.</p></div><Button variant="outline" onClick={() => setPhoneTrip(selected)}>Connect / manage phone</Button></section>}</div></div>
      {feed.data && <TransportPagination page={page} total={feed.data.total} onPage={(value) => { setPage(value); setSelectedId(null); }} busy={feed.isFetching}/>}<p className="text-xs leading-5 text-muted-foreground">Location is a phone GPS report, not proof a child is on board. Boarding and handover come from staff records. Nearby signals need a fresh fix with accuracy within 100 m; traffic and road distance can change arrival time. Alerts require this page to remain open.</p>
    </>}
    {familySetup && canManage && <FamilySetup onClose={() => setFamilySetup(false)}/>}{phoneTrip && canManage && <PhoneSetup tripId={phoneTrip.trip_id} vehicle={phoneTrip.vehicle_number} onClose={() => setPhoneTrip(null)}/>}
  </div>;
}
