'use client';

import { useEffect, useRef, useState } from 'react';
import { MapPin, Navigation, ShieldCheck, Square } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { phoneRequest } from '@/lib/api/tracking';
import type { PhoneContext, TrackingProgress } from '@/lib/api/tracking';
import { PhoneLocationSender } from '@/lib/transport/phone-sender';
import type { SenderState } from '@/lib/transport/phone-sender';
import { useScreenAwake } from '@/lib/transport/useScreenAwake';

export default function TripPhonePage() {
  const token = useRef('');
  const sender = useRef<PhoneLocationSender | null>(null);
  const [context, setContext] = useState<PhoneContext | null>(null);
  const [error, setError] = useState('');
  const [state, setState] = useState<SenderState>({ phase: 'idle', message: 'Your location is not being shared.' });
  const [consent, setConsent] = useState(false);
  const [safeToTap, setSafeToTap] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [keepAwake, setKeepAwake] = useState(true);
  const [stopId, setStopId] = useState('');
  const [progress, setProgress] = useState<TrackingProgress>({});

  useEffect(() => {
    // Remove the fragment before any map/external link could be opened. Keep it in memory only.
    if (!token.current) token.current = new URLSearchParams(window.location.hash.slice(1)).get('code') ?? '';
    window.history.replaceState(null, '', window.location.pathname);
    if (!token.current) { setError('Open the trip sharing link supplied by the transport office. Reloading requires that link again.'); return; }
    let alive = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    void phoneRequest<PhoneContext>(token.current, 'context', undefined, controller.signal).then((data) => {
      if (!alive) return;
      setContext(data); setProgress(data.progress); setStopId(data.progress.stop_id ?? data.stops[0]?.id ?? '');
    }).catch((failure) => { if (alive) setError(failure.name === 'AbortError' ? 'The school connection timed out. Open the original trip link again when connected.' : failure.message); }).finally(() => clearTimeout(timeout));
    return () => { alive = false; clearTimeout(timeout); controller.abort(); };
  }, []);

  useEffect(() => {
    const instance = new PhoneLocationSender({
      locate: () => new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, maximumAge: 0, timeout: 12000 })),
      send: (fix, signal) => phoneRequest(token.current, 'position', fix, signal), onState: setState,
    });
    sender.current = instance;
    const availability = () => instance.availability(!document.hidden, navigator.onLine);
    availability();
    document.addEventListener('visibilitychange', availability);
    window.addEventListener('online', availability); window.addEventListener('offline', availability);
    return () => {
      instance.dispose(); sender.current = null;
      document.removeEventListener('visibilitychange', availability);
      window.removeEventListener('online', availability); window.removeEventListener('offline', availability);
    };
  }, []);

  const start = () => {
    if (!window.isSecureContext) { setError('Open this link over HTTPS to share GPS. Localhost is supported for development.'); return; }
    if (!navigator.geolocation) { setError('This browser does not support GPS location sharing.'); return; }
    setError(''); sender.current?.start();
  };
  const updateStop = async (stage: 'arriving' | 'at_stop' | 'departed') => {
    setUpdating(true); setError('');
    try {
      const value = await phoneRequest<TrackingProgress>(token.current, 'progress', { stop_id: stopId, stage, version: progress.version ?? 0 });
      setProgress(value);
    } catch (failure) {
      setError((failure as Error).message);
      try { const fresh = await phoneRequest<PhoneContext>(token.current, 'context'); setProgress(fresh.progress); } catch { /* Preserve the actionable original error. */ }
    } finally { setUpdating(false); }
  };
  const active = ['locating', 'sharing', 'paused'].includes(state.phase) || (state.phase === 'error' && state.message.includes('Retrying'));
  const wakeStatus = useScreenAwake(active && keepAwake);

  return <main className="mx-auto w-full max-w-lg space-y-6 px-5 py-8 sm:py-12">
    <header className="space-y-2"><div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-sm text-primary"><ShieldCheck size={16}/>School trip sharing</div><h1 className="text-2xl font-semibold">A clearer journey home.</h1><p className="text-sm leading-6 text-muted-foreground">For the assigned helper, or a driver while safely parked.</p></header>
    {error && <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm">{error}</p>}
    {!context && !error && <p role="status" className="rounded-xl border p-4 text-sm text-muted-foreground">Checking your private trip link…</p>}
    {context && <>
      <section className="rounded-2xl border bg-card p-5"><p className="text-2xl font-semibold">{context.vehicle_number}</p><p className="mt-1 text-sm">{context.run_name} · {context.direction === 'drop' ? 'Home drop' : 'School pickup'}</p><p className="mt-2 text-xs text-muted-foreground">Assigned phone: {context.sender_label} · Link expires {new Intl.DateTimeFormat('en-NP', { timeZone: 'Asia/Kathmandu', hour: '2-digit', minute: '2-digit' }).format(new Date(context.expires_at))} NPT</p></section>
      <section className="space-y-4 rounded-2xl border p-5">
        <div className="flex items-start gap-3"><MapPin className="mt-1 shrink-0 text-primary"/><div><h2 className="font-semibold">Share vehicle location</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">This shares the phone’s precise location during this trip. Keep it in the assigned vehicle, with this screen open and awake. Background or locked-screen tracking is not reliable in a browser.</p></div></div>
        <label className="flex items-start gap-3 text-sm leading-6"><input type="checkbox" checked={consent} disabled={active} onChange={(event) => setConsent(event.target.checked)} className="mt-1.5"/>I am the assigned helper/parked driver, and I agree to share this vehicle’s location for this trip.</label>
        <p role="status" className={`rounded-xl p-4 text-sm ${state.phase === 'sharing' ? 'bg-emerald-50 text-emerald-900' : 'bg-muted'}`}>{state.message}{state.lastSent && <span className="mt-1 block text-xs">Last delivered {new Date(state.lastSent).toLocaleTimeString('en-NP', { timeZone: 'Asia/Kathmandu' })} NPT · GPS ±{Math.round(state.accuracy ?? 0)} m</span>}</p>
        <div className="flex gap-3"><Button className="flex-1" disabled={!consent || active || state.phase === 'ended'} onClick={start}><Navigation size={16}/>Start sharing</Button><Button variant="outline" onClick={() => sender.current?.stop()} disabled={!active}><Square size={16}/>Stop</Button></div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={keepAwake} onChange={(event) => setKeepAwake(event.target.checked)}/>Keep screen awake while sharing</label><p className="text-xs text-muted-foreground">{wakeStatus}</p>
        <p className="text-xs leading-5 text-muted-foreground">Fresh fixes send about every 10 seconds. Hidden/offline screens pause; returning resumes only after you have started sharing. Stopping or closing this page ends phone sending. The office can revoke this link at any time.</p>
      </section>
      <section className="space-y-4 rounded-2xl border p-5"><h2 className="font-semibold">Update the stop</h2><p className="text-sm leading-6 text-muted-foreground">These are helper reports, separate from GPS and student boarding. Only update when safely stopped.</p>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={safeToTap} onChange={(event) => setSafeToTap(event.target.checked)}/>I am the helper or the vehicle is safely parked.</label>
        <label className="grid gap-2 text-sm">Trip stop<select className="min-h-11 rounded-lg border bg-background px-3" value={stopId} onChange={(event) => setStopId(event.target.value)}>{context.stops.map((stop) => <option key={stop.id} value={stop.id}>{stop.name}</option>)}</select></label>
        <div className="grid grid-cols-3 gap-2">{(['arriving', 'at_stop', 'departed'] as const).map((stage) => <Button key={stage} variant="outline" disabled={!safeToTap || updating || !stopId || state.phase === 'ended'} onClick={() => updateStop(stage)}>{stage === 'arriving' ? 'Approaching' : stage === 'at_stop' ? 'At stop' : 'Departed'}</Button>)}</div>
        {progress.name && <p role="status" className="text-sm text-muted-foreground">Last report: {progress.name} · {progress.stage?.replace('_', ' ')}</p>}
      </section>
    </>}
    <p className="text-center text-xs leading-5 text-muted-foreground">No passenger names, parent contacts or office records are available through this link.</p>
  </main>;
}
