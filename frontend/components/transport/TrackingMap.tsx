'use client';

import { useEffect, useRef, useState } from 'react';
import * as L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Button } from '@/components/ui/button';
import type { TrackingJourney } from '@/lib/api/tracking';
import { locationState } from '@/lib/api/tracking';

const tileUrl = process.env.NEXT_PUBLIC_TRANSPORT_TILE_URL ?? 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const tileAttribution = process.env.NEXT_PUBLIC_TRANSPORT_TILE_ATTRIBUTION ?? '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>';

function point(latitude: string | null, longitude: string | null): L.LatLngTuple | null {
  if (latitude === null || longitude === null) return null;
  const lat = Number(latitude), lon = Number(longitude);
  return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? [lat, lon] : null;
}
function label(text: string) { const element = document.createElement('span'); element.textContent = text; return element; }

export default function TrackingMap({ journeys, selectedId, onSelect, time, connected }: {
  journeys: TrackingJourney[]; selectedId: string | null; onSelect: (id: string) => void; time: number; connected: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const markers = useRef(new Map<string, L.CircleMarker>());
  const stops = useRef<L.LayerGroup | null>(null);
  const select = useRef(onSelect);
  const firstFit = useRef('');
  const [follow, setFollow] = useState(true);
  const [tileError, setTileError] = useState(false);
  useEffect(() => { select.current = onSelect; }, [onSelect]);
  const selected = journeys.find((journey) => journey.id === selectedId);
  const stopData = JSON.stringify(selected?.child ? selected.stop ? [selected.stop] : [] : selected?.stops ?? []);

  useEffect(() => {
    if (!container.current) return;
    const instance = L.map(container.current, { center: [28.2, 84], zoom: 7, scrollWheelZoom: false, zoomControl: true });
    map.current = instance;
    L.tileLayer(tileUrl, { attribution: tileAttribution, maxZoom: 19 }).on('tileerror', () => setTileError(true)).addTo(instance);
    stops.current = L.layerGroup().addTo(instance);
    const vehicleMarkers = markers.current;
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => instance.invalidateSize({ pan: false })) : null;
    observer?.observe(container.current);
    return () => { observer?.disconnect(); vehicleMarkers.clear(); instance.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const wanted = new Set<string>();
    journeys.forEach((journey) => {
      const fix = journey.position;
      const coordinate = fix && point(fix.latitude, fix.longitude);
      if (!coordinate) return;
      wanted.add(journey.id);
      const state = locationState(fix, time, connected);
      const color = state.live ? '#059669' : '#78716c';
      let marker = markers.current.get(journey.id);
      if (!marker) {
        marker = L.circleMarker(coordinate, { radius: 10, fillOpacity: 0.95, weight: 3 }).addTo(instance);
        marker.on('click', () => select.current(journey.id));
        markers.current.set(journey.id, marker);
      }
      marker.setLatLng(coordinate).setRadius(journey.id === selectedId ? 13 : 9).setStyle({ color: journey.id === selectedId ? '#7c3aed' : '#ffffff', fillColor: color });
      marker.unbindTooltip().bindTooltip(label(`${journey.vehicle_number} · ${state.label}`));
    });
    markers.current.forEach((marker, id) => { if (!wanted.has(id)) { instance.removeLayer(marker); markers.current.delete(id); } });
    const active = selectedId ? markers.current.get(selectedId) : undefined;
    const fitKey = selectedId ?? 'fleet';
    const coordinates: L.LatLngExpression[] = active ? [active.getLatLng()] : Array.from(markers.current.values(), (marker) => marker.getLatLng());
    const relevantStops = JSON.parse(stopData) as Array<{latitude: string | null; longitude: string | null}>;
    relevantStops.forEach((stop) => { const coordinate = point(stop.latitude, stop.longitude); if (coordinate) coordinates.push(coordinate); });
    if (firstFit.current !== fitKey && coordinates.length) {
      const bounds = L.latLngBounds(coordinates);
      instance.fitBounds(bounds, { padding: [45, 45], maxZoom: 15, animate: false }); firstFit.current = fitKey;
    } else if (follow && active) instance.panInside(active.getLatLng(), { padding: [45, 45], animate: false });
  }, [journeys, selectedId, time, connected, follow, stopData]);

  useEffect(() => {
    stops.current?.clearLayers();
    (JSON.parse(stopData) as Array<{name: string; latitude: string | null; longitude: string | null}>).forEach((stop) => {
      const coordinate = point(stop.latitude, stop.longitude);
      if (coordinate && stops.current) L.circleMarker(coordinate, { color: '#7c3aed', fillColor: '#ede9fe', fillOpacity: 1, radius: 6, weight: 2 }).bindTooltip(label(stop.name)).addTo(stops.current);
    });
  }, [stopData]);

  return <section className="overflow-hidden rounded-2xl border bg-card">
    <div className="flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3"><div><h2 className="text-sm font-semibold">Vehicle map</h2><p className="text-xs text-muted-foreground">Green: fresh GPS · Grey: last known · Purple: selected vehicle / stop</p></div><div className="flex items-center gap-2"><label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={follow} onChange={(event) => setFollow(event.target.checked)}/>Follow selected</label><Button size="sm" variant="outline" onClick={() => { firstFit.current = ''; setFollow(true); const active = selectedId ? markers.current.get(selectedId) : undefined; if (active) map.current?.setView(active.getLatLng(), 15, { animate: false }); }}>Recenter</Button></div></div>
    <div ref={container} role="region" aria-label="Live school vehicle map" className="isolate z-0 h-[380px] w-full sm:h-[500px]"/>
    {tileError && <p role="status" className="px-4 py-2 text-xs text-muted-foreground">Some map tiles could not load. Vehicle coordinates and journey cards remain available.</p>}
    <p className="border-t px-4 py-2 text-xs text-muted-foreground">Stop markers are school references. Road arrival times are not calculated from straight-line distance.</p>
  </section>;
}
