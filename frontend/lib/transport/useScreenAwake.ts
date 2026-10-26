'use client';
import { useEffect, useState } from 'react';

/** Best-effort visible-screen lock; never claims locked/background GPS support. */
export function useScreenAwake(active: boolean) {
  const [status, setStatus] = useState('Screen wake protection is off.');
  useEffect(() => {
    let alive = true, pending = false;
    let lock: WakeLockSentinel | null = null;
    const release = () => { if (lock) { void lock.release().catch(() => {}); lock = null; } };
    const acquire = async () => {
      if (!active) { if (alive) setStatus('Screen wake protection is off.'); return; }
      if (document.hidden || pending || lock) return;
      if (!('wakeLock' in navigator)) { if (alive) setStatus('This browser cannot keep the screen awake. Adjust the phone’s screen timeout.'); return; }
      pending = true;
      try {
        const sentinel = await navigator.wakeLock.request('screen');
        if (!alive || document.hidden) { await sentinel.release(); return; }
        lock = sentinel;
        setStatus('Keeping this screen awake while sharing.');
        sentinel.addEventListener('release', () => { if (lock === sentinel) lock = null; if (alive) setStatus('Screen wake protection was released. Keep this page open and awake.'); });
      } catch { if (alive) setStatus('Screen wake protection unavailable. Keep this page open and awake.'); }
      finally { pending = false; }
    };
    const visibility = () => { if (document.hidden) release(); else void acquire(); };
    // Deferral also makes the cleanup guard effective during StrictMode remounts.
    void Promise.resolve().then(() => { if (alive) return acquire(); });
    document.addEventListener('visibilitychange', visibility);
    return () => { alive = false; document.removeEventListener('visibilitychange', visibility); release(); };
  }, [active]);
  return status;
}
