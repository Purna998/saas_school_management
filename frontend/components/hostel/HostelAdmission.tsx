'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { hostelData } from '@/lib/api/hostel';
import type { HostelRoom, HostelStudent, Resident } from '@/lib/api/hostel';
import { money } from '@/lib/api/fees';
import { HostelEmpty, HostelField, HostelPagination, useHostelCommand, useHostelToday } from './HostelCommon';

function RoomPicker({ onSelect, disabled }: { onSelect: (room: HostelRoom) => void; disabled: boolean }) {
  const [draft, setDraft] = useState(''); const [search, setSearch] = useState(''); const [page, setPage] = useState(1);
  const rooms = useQuery({ queryKey: ['hostel', 'available-rooms', page, search], queryFn: async () => hostelData(await apiClient.hostel.rooms({ available_only: true, search, page })) });
  return <section className="space-y-3"><form className="flex items-end gap-2" onSubmit={(event) => { event.preventDefault(); setSearch(draft.trim()); setPage(1); }}><HostelField label="Find a room"><Input disabled={disabled} maxLength={200} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Hostel name or room number" /></HostelField><Button type="submit" variant="outline" disabled={disabled}>Search rooms</Button></form>
    {rooms.isLoading ? <HostelEmpty>Loading vacancies…</HostelEmpty> : rooms.error ? <HostelEmpty error={rooms.error.message} /> : !rooms.data?.rooms.length ? <HostelEmpty>No available beds match this search.</HostelEmpty> : <div className="grid max-h-56 gap-2 overflow-y-auto sm:grid-cols-2">{rooms.data.rooms.map((room) => <button key={room.id} disabled={disabled} type="button" className="rounded-lg border p-3 text-left text-sm hover:bg-accent" onClick={() => onSelect(room)}><p className="font-semibold">{room.hostel_name} · {room.room_number}</p><p className="mt-1 text-xs text-muted-foreground">{room.hostel_type} · Floor {room.floor} · {room.available_beds} available · {money(room.monthly_fee)} / month</p></button>)}</div>}{rooms.data && <HostelPagination page={page} total={rooms.data.total} busy={disabled || rooms.isFetching} onPage={setPage} />}
  </section>;
}

export function HostelStudentPicker({ selected, onSelect, disabled }: { selected: HostelStudent | null; onSelect: (student: HostelStudent) => void; disabled: boolean }) {
  const [draft, setDraft] = useState(''); const [search, setSearch] = useState(''); const [page, setPage] = useState(1);
  const students = useQuery({ queryKey: ['hostel', 'students', search, page], queryFn: async () => hostelData(await apiClient.hostel.students({ search, page })) });
  return <section className="space-y-3"><form className="flex items-end gap-2" onSubmit={(event) => { event.preventDefault(); setSearch(draft.trim()); setPage(1); }}><HostelField label="Find a student"><Input disabled={disabled} maxLength={200} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Name, admission or EMIS number" /></HostelField><Button type="submit" variant="outline" disabled={disabled}>Search students</Button></form>
    {students.isLoading ? <HostelEmpty>Loading active students…</HostelEmpty> : students.error ? <HostelEmpty error={students.error.message} /> : !students.data?.students.length ? <HostelEmpty>No active students match this search.</HostelEmpty> : <div className="grid max-h-56 gap-2 overflow-y-auto sm:grid-cols-2">{students.data.students.map((student) => <button key={student.id} disabled={disabled || Boolean(student.active_allocation_id)} type="button" aria-pressed={selected?.id === student.id} className={`rounded-lg border p-3 text-left text-sm hover:bg-accent disabled:opacity-60 ${selected?.id === student.id ? 'border-primary bg-accent/40' : ''}`} onClick={() => onSelect(student)}><p className="font-semibold">{student.full_name_en}</p>{student.full_name_np && <p className="mt-1 text-xs">{student.full_name_np}</p>}<p className="mt-1 text-xs text-muted-foreground">{student.admission_number || student.emis_student_id || 'No reference'} · Grade {student.current_grade ?? '—'} {student.current_section} · Roll {student.roll_number ?? '—'} · {student.gender}</p>{student.active_allocation_id && <p className="mt-1 text-xs">Already boarding · use Transfer from the current stay</p>}</button>)}</div>}{students.data && <HostelPagination page={page} total={students.data.total} busy={disabled || students.isFetching} onPage={setPage} />}
  </section>;
}

export function HostelAdmission({ initialRoom, bedId, bedLabel, transfer, onClose, onResident }: { initialRoom?: HostelRoom; bedId?: string; bedLabel?: string; transfer?: Resident; onClose: () => void; onResident: (id: string) => void }) {
  const [room, setRoom] = useState(initialRoom ?? null); const [student, setStudent] = useState<HostelStudent | null>(null); const [chosenBed, setChosenBed] = useState(bedId); const [chosenLabel, setChosenLabel] = useState(bedLabel); const [notes, setNotes] = useState(''); const [key, setKey] = useState(() => crypto.randomUUID());
  const date = useHostelToday();
  const save = useHostelCommand(async () => {
    if (!room || (!student && !transfer)) throw new Error('Select a room and an eligible student');
    const payload = { room_id: room.id, bed_id: chosenBed, notes: notes.trim() || null, request_id: key };
    return transfer ? hostelData(await apiClient.hostel.transfer(transfer.id, payload)) : hostelData(await apiClient.hostel.allocate({ ...payload, student_id: student!.id }));
  }, (stay) => onResident(stay.id), transfer ? 'Resident transferred; previous stay retained' : 'Bed allocated and stay record created');
  const selectRoom = (next: HostelRoom) => { setRoom(next); setChosenBed(undefined); setChosenLabel(undefined); setKey(crypto.randomUUID()); };
  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{transfer ? 'Transfer resident' : 'Admit a boarder / आवासीय भर्ना'}</DialogTitle><DialogDescription>{transfer ? `${transfer.student_name} · Current ${transfer.hostel_name}, ${transfer.room_number}, ${transfer.bed_label ?? 'unknown bed'}. The previous stay and monthly rate remain in history.` : 'Select an enrolled student and an available room. The server checks current bed availability and hostel eligibility.'}</DialogDescription></DialogHeader>
    {room ? <div className="mb-5 rounded-xl border bg-accent/30 p-4 text-sm"><p className="font-semibold">{room.hostel_name ?? 'Selected hostel'} · Room {room.room_number} · {chosenLabel ?? 'Next available bed'}</p><p className="mt-1">Agreed charge: {money(room.monthly_fee)} / BS month</p><Button className="mt-3" size="sm" variant="outline" disabled={save.isPending} onClick={() => { setRoom(null); setChosenBed(undefined); setChosenLabel(undefined); setKey(crypto.randomUUID()); }}>Choose another room</Button></div> : <RoomPicker disabled={save.isPending} onSelect={selectRoom} />}
    {!transfer && <div className="my-5"><HostelStudentPicker selected={student} disabled={save.isPending} onSelect={(value) => { setStudent(value); setKey(crypto.randomUUID()); }} /></div>}
    <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4"><p className="text-sm">{date.data ? `Recorded today: ${date.data.bs} BS · ${date.data.ad} AD · ${date.data.year} BS academic year` : 'Admission dates use the current Nepal civil date.'}</p>{student && <p className="text-sm">Selected student: <strong>{student.full_name_en}</strong> · {student.admission_number || student.emis_student_id || `Grade ${student.current_grade}`}</p>}
      <HostelField label={transfer ? 'Transfer reason' : 'Admission / agreed charge notes'}><Input required={Boolean(transfer)} minLength={transfer ? 3 : undefined} maxLength={1000} value={notes} onChange={(event) => { setNotes(event.target.value); setKey(crypto.randomUUID()); }} /></HostelField>
      <p className="text-xs text-muted-foreground">Allocation reserves the bed. It does not collect a payment. Authorized fee staff can post the agreed monthly charge to Fees & Payments.</p>
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!room || (!student && !transfer)}>{save.isPending ? 'Saving…' : transfer ? 'Confirm transfer' : 'Allocate bed'}</Button></DialogFooter>
    </fieldset></form>
  </DialogContent></Dialog>;
}
