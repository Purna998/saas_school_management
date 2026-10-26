import type { PhoneFix } from '../api/tracking';

export interface SenderState {
  phase: 'idle' | 'locating' | 'sharing' | 'paused' | 'error' | 'ended';
  message: string; lastSent?: string; accuracy?: number;
}
interface SenderOptions {
  locate: () => Promise<GeolocationPosition>;
  send: (fix: PhoneFix, signal: AbortSignal) => Promise<unknown>;
  onState: (state: SenderState) => void;
  interval?: number;
}

/** One request at a time; no retained offline trail and no late callback after stop. */
export class PhoneLocationSender {
  private wanted = false;
  private visible = true;
  private online = true;
  private generation = 0;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private controller: AbortController | undefined;
  private failures = 0;
  constructor(private readonly options: SenderOptions) {}

  start() { this.wanted = true; this.restart(); }
  stop() {
    this.wanted = false;
    this.cancel();
    this.options.onState({ phase: 'idle', message: 'Location sharing is stopped.' });
  }
  availability(visible: boolean, online: boolean) {
    if (visible === this.visible && online === this.online) return;
    this.visible = visible; this.online = online;
    if (this.wanted) this.restart();
  }
  dispose() { this.wanted = false; this.cancel(); }
  private cancel() {
    this.generation++;
    clearTimeout(this.timer);
    this.controller?.abort();
  }
  private restart() {
    this.cancel();
    if (!this.wanted) return;
    if (!this.visible || !this.online) {
      this.options.onState({ phase: 'paused', message: !this.visible ? 'Sharing paused. Return to this screen to resume.' : 'Phone is offline. Fresh GPS sharing will resume when connected.' });
      return;
    }
    void this.sample(this.generation);
  }
  private async sample(generation: number) {
    const current = () => this.wanted && generation === this.generation;
    this.options.onState({ phase: 'locating', message: 'Getting a fresh GPS fix…' });
    try {
      const position = await this.options.locate();
      if (!current()) return;
      const { latitude, longitude, accuracy, speed, heading } = position.coords;
      if (![latitude, longitude, accuracy, position.timestamp].every(Number.isFinite) || accuracy < 0 || accuracy > 10000) throw new Error('GPS fix is invalid. Move to an open area and try again.');
      const fix: PhoneFix = {
        latitude: latitude.toFixed(7), longitude: longitude.toFixed(7), accuracy_m: accuracy.toFixed(2),
        speed_mps: speed !== null && Number.isFinite(speed) && speed >= 0 && speed <= 60 ? speed.toFixed(2) : null,
        heading: heading !== null && Number.isFinite(heading) && heading >= 0 && heading <= 360 ? heading.toFixed(2) : null,
        recorded_at: new Date(position.timestamp).toISOString(),
      };
      const controller = new AbortController();
      this.controller = controller;
      const timeout = setTimeout(() => controller.abort(), 15000);
      try { await this.options.send(fix, controller.signal); } finally { clearTimeout(timeout); }
      if (!current()) return;
      this.failures = 0;
      this.options.onState({ phase: 'sharing', message: accuracy <= 100 ? 'Sharing this trip’s live location.' : 'Sharing, but GPS is imprecise. Move the phone closer to a window.', lastSent: new Date().toISOString(), accuracy });
    } catch (error) {
      if (!current()) return;
      const failure = error as Error & { code?: number; status?: number };
      if (failure.status === 410 || failure.status === 401) {
        this.wanted = false;
        this.options.onState({ phase: 'ended', message: failure.message });
        return;
      }
      if (failure.code === 1) {
        this.wanted = false;
        this.options.onState({ phase: 'error', message: 'Location permission was denied. Allow precise location in browser settings, then start again.' });
        return;
      }
      this.failures++;
      this.options.onState({ phase: 'error', message: `${failure.message || 'GPS or network unavailable'}. Retrying with a fresh fix…` });
    }
    if (current()) this.timer = setTimeout(() => void this.sample(generation), Math.min(60000, (this.options.interval ?? 10000) * Math.max(1, this.failures)));
  }
}
