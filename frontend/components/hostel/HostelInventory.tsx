'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { hostelData } from '@/lib/api/hostel';
import type { BedState, HostelBed, HostelRoom } from '@/lib/api/hostel';
import { HostelEmpty, HostelField, HostelPagination, HostelStatus, hostelSelect, useHostelCommand } from './HostelCommon';

export function BedStockForm({ roomId, bed, onClose, onBusy }: { roomId: string; bed?: HostelBed; onClose: () => void; onBusy: (value: boolean) => void }) {
  const [count, setCount] = useState('1'); const [labels, setLabels] = useState(''); const [status, setStatus] = useState<BedState>(bed?.status ?? 'active'); const [notes, setNotes] = useState(''); const [key, setKey] = useState(() => crypto.randomUUID());
  const edit = (change: () => void) => { change(); setKey(crypto.randomUUID()); };
  const save = useHostelCommand(async () => {
    onBusy(true);
    try {
      if (bed) return hostelData(await apiClient.hostel.updateBed(bed.id, { status, notes, request_id: key }));
      const names = labels.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
      if (names.length && names.length !== Number(count)) throw new Error('Enter one label per bed, or leave labels blank');
      return hostelData(await apiClient.hostel.addBeds(roomId, { count: Number(count), labels: names.length ? names : null, notes: notes.trim() || null, request_id: key }));
    } finally { onBusy(false); }
  }, onClose, bed ? 'Bed condition updated' : 'Beds added to physical inventory');
  return <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4 rounded-xl border bg-accent/20 p-4"><h3 className="font-semibold">{bed ? `Condition · ${bed.label}` : 'Add beds'}</h3>
    {bed ? <HostelField label="Bed condition"><select className={hostelSelect} value={status} onChange={(event) => edit(() => setStatus(event.target.value as BedState))}><option value="active">In service / repaired</option><option value="maintenance">Blocked for maintenance</option><option value="retired">Retired from capacity</option></select></HostelField> : <><HostelField label="Number of beds"><Input type="number" required min={1} max={100} value={count} onChange={(event) => edit(() => setCount(event.target.value))} /></HostelField><HostelField label="Existing bed labels (optional, one per line)"><textarea rows={3} maxLength={3200} className="rounded-lg border p-3" value={labels} onChange={(event) => edit(() => setLabels(event.target.value))} /></HostelField><p className="text-xs text-muted-foreground">Leave labels blank to assign new B-0001 style numbers. Retired labels stay reserved for history.</p></>}
    <HostelField label={bed ? 'Reason for condition change' : 'Acquisition notes'}><Input required={Boolean(bed)} minLength={bed ? 3 : undefined} maxLength={1000} value={notes} onChange={(event) => edit(() => setNotes(event.target.value))} /></HostelField><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel changes</Button><Button type="submit">{save.isPending ? 'Saving…' : bed ? 'Save condition' : 'Add beds'}</Button></div>
  </fieldset></form>;
}

export function HostelInventory({ roomId, canEdit, canAllocate, onClose, onAllocate, onResident }: { roomId: string; canEdit: boolean; canAllocate: boolean; onClose: () => void; onAllocate: (room: HostelRoom, bed: HostelBed) => void; onResident: (id: string) => void }) {
  const [page, setPage] = useState(1); const [form, setForm] = useState<HostelBed | 'add' | null>(null); const [busy, setBusy] = useState(false);
  const inventory = useQuery({ queryKey: ['hostel', 'beds', roomId, page], queryFn: async () => hostelData(await apiClient.hostel.beds(roomId, { page })) });
  const data = inventory.data;
  return <Dialog open onOpenChange={(open) => !open && !busy && onClose()}><DialogContent className="max-w-4xl"><DialogHeader><DialogTitle>Bed register · {data?.room.room_number ?? 'Room'}</DialogTitle><DialogDescription>{data?.hostel.name} · Maintenance beds cannot be allocated. Residents on leave retain their bed.</DialogDescription></DialogHeader>
    {canEdit && <div className="mb-4 flex justify-end"><Button disabled={busy} variant="outline" onClick={() => setForm(form ? null : 'add')}>{form ? 'Hide form' : 'Add beds'}</Button></div>}
    {form && <BedStockForm key={form === 'add' ? 'add' : form.id} roomId={roomId} bed={form === 'add' ? undefined : form} onClose={() => setForm(null)} onBusy={setBusy} />}
    {inventory.isLoading ? <HostelEmpty>Loading bed inventory…</HostelEmpty> : inventory.error ? <HostelEmpty error={inventory.error.message} /> : !data?.beds.length ? <HostelEmpty>No physical beds have been registered.</HostelEmpty> : <><p className="my-4 text-sm">{data.room.occupied} occupied / {data.room.capacity} registered beds{!data.room.is_active || !data.hostel.is_active ? ' · Room or hostel is archived' : ''}</p><div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-3">Bed</th><th className="p-3">State</th><th className="p-3">Resident / notes</th><th className="p-3">Actions</th></tr></thead><tbody>{data.beds.map((bed) => <tr key={bed.id}><td className="p-3 font-mono">{bed.label}</td><td className="p-3"><HostelStatus status={bed.resident ? 'occupied' : bed.status === 'active' ? 'available' : bed.status} /></td><td className="p-3"><p>{bed.resident?.student_name ?? '—'}</p><p className="mt-1 max-w-64 break-words text-xs text-muted-foreground">{bed.resident?.student_reference ?? bed.notes}</p></td><td className="p-3"><div className="flex flex-wrap gap-2">{bed.resident && <Button size="sm" variant="outline" disabled={busy} onClick={() => onResident(bed.resident!.id)}>View stay</Button>}{!bed.resident && canEdit && <Button size="sm" variant="outline" disabled={busy} onClick={() => setForm(bed)}>Condition</Button>}{!bed.resident && canAllocate && bed.status === 'active' && data.room.is_active && data.hostel.is_active && <Button size="sm" disabled={busy} onClick={() => onAllocate({ ...data.room, hostel_name: data.hostel.name }, bed)}>Allocate</Button>}</div></td></tr>)}</tbody></table></div><HostelPagination page={page} total={data.total} busy={inventory.isFetching || busy} onPage={setPage} /></>}
    <DialogFooter><Button variant="outline" disabled={busy} onClick={onClose}>Close bed register</Button></DialogFooter>
  </DialogContent></Dialog>;
}
