'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { bsMonths, hostelData, normalizeBsInput } from '@/lib/api/hostel';
import type { HostelBill, Resident } from '@/lib/api/hostel';
import { money, paise } from '@/lib/api/fees';
import { HostelBsField, HostelEmpty, HostelField, hostelSelect, useBsDate, useHostelCommand, useHostelToday } from './HostelCommon';

export function HostelOperationDialog({ action, stay, onClose, onResident }: { action: 'leave' | 'returnLeave' | 'checkout' | 'visit'; stay: Resident; onClose: () => void; onResident: (id: string) => void }) {
  const [notes, setNotes] = useState(''); const [expected, setExpected] = useState<string | null>(null); const [destination, setDestination] = useState(''); const [person, setPerson] = useState(''); const [phone, setPhone] = useState(''); const [relation, setRelation] = useState('Guardian'); const [key, setKey] = useState(() => crypto.randomUUID());
  const today = useHostelToday(); const expectedBs = expected ?? today.data?.bs ?? ''; const converted = useBsDate(action === 'leave' ? expectedBs : '');
  const edit = (change: () => void) => { change(); setKey(crypto.randomUUID()); };
  const save = useHostelCommand<unknown>(async () => {
    const request = { notes: notes.trim(), request_id: key };
    if (action === 'checkout') return hostelData(await apiClient.hostel.vacate(stay.id, request));
    if (action === 'returnLeave') { if (!stay.leave_id) throw new Error('The current stay has no open leave'); return hostelData(await apiClient.hostel.returnLeave(stay.leave_id, request)); }
    if (action === 'visit') return hostelData(await apiClient.hostel.visit({ allocation_id: stay.id, visitor_name: person, relation, contact_phone: phone.trim() || null, purpose: notes.trim(), request_id: key }));
    if (!converted.data) throw new Error('Enter a valid BS expected-return date');
    return hostelData(await apiClient.hostel.leave(stay.id, { expected_return_ad: converted.data.ad_date.iso_date, destination, responsible_person: person, contact_phone: phone.trim() || null, reason: notes.trim(), request_id: key }));
  }, () => onResident(stay.id), action === 'leave' ? 'Approved departure recorded; bed remains reserved' : action === 'returnLeave' ? 'Return from leave recorded' : action === 'visit' ? 'Visitor checked in' : 'Resident checked out; bed released');
  const titles = { leave: 'Record approved leave / बिदा', returnLeave: 'Record return from leave', checkout: 'Check out resident', visit: 'Visitor check-in / आगन्तुक' };
  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent><DialogHeader><DialogTitle>{titles[action]}</DialogTitle><DialogDescription>{stay.student_name} · {stay.hostel_name} · Room {stay.room_number}, Bed {stay.bed_label ?? 'unknown'}</DialogDescription></DialogHeader><form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4">
    {action === 'leave' && <><p className="rounded-lg bg-accent/40 p-3 text-sm">Record departure after your school’s guardian and warden approval process. This form records the responsible contact; it does not send an approval request or notification.</p><HostelBsField label="Expected return date (BS)" value={expectedBs} onChange={(value) => edit(() => setExpected(value))} ad={converted.data?.ad_date.iso_date} error={converted.error?.message} /><HostelField label="Destination"><Input required maxLength={200} value={destination} onChange={(event) => edit(() => setDestination(event.target.value))} placeholder="Municipality / place of visit" /></HostelField></>}
    {(action === 'leave' || action === 'visit') && <><HostelField label={action === 'leave' ? 'Responsible guardian / person' : 'Visitor name'}><Input required minLength={2} maxLength={200} value={person} onChange={(event) => edit(() => setPerson(event.target.value))} /></HostelField>{action === 'visit' && <HostelField label="Relationship to resident"><Input required minLength={2} maxLength={50} value={relation} onChange={(event) => edit(() => setRelation(event.target.value))} /></HostelField>}<HostelField label="Contact phone"><Input type="tel" maxLength={20} value={phone} onChange={(event) => edit(() => setPhone(event.target.value))} placeholder="+977… or landline" /></HostelField></>}
    {action === 'checkout' && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">This ends the stay today and releases the bed. Open leave and visitor records must be closed first. Existing fee bills and payments remain in the student account.</p>}
    <HostelField label={action === 'visit' ? 'Visit purpose' : action === 'returnLeave' ? 'Return confirmation / notes' : action === 'leave' ? 'Approved leave reason' : 'Checkout reason'}><Input required minLength={3} maxLength={action === 'visit' ? 500 : 1000} value={notes} onChange={(event) => edit(() => setNotes(event.target.value))} /></HostelField>
    <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={action === 'leave' && (!converted.data || converted.isFetching)}>{save.isPending ? 'Recording…' : action === 'checkout' ? 'Confirm checkout' : action === 'visit' ? 'Check in visitor' : action === 'leave' ? 'Record departure' : 'Confirm return'}</Button></DialogFooter>
  </fieldset></form></DialogContent></Dialog>;
}

export function HostelBillDialog({ stay, onClose }: { stay: Resident; onClose: () => void }) {
  const today = useHostelToday(); const [monthDraft, setMonthDraft] = useState<string | null>(null); const [yearDraft, setYearDraft] = useState<string | null>(null); const [head, setHead] = useState(''); const [dueDay, setDueDay] = useState('10'); const [approved, setApproved] = useState(false); const [key, setKey] = useState(() => crypto.randomUUID()); const [result, setResult] = useState<HostelBill | null>(null);
  const month = monthDraft ?? today.data?.bs.slice(5, 7) ?? ''; const year = yearDraft ?? today.data?.bs.slice(0, 4) ?? ''; const period = `${normalizeBsInput(year)}-${month}`;
  const options = useQuery({ queryKey: ['hostel', 'fee-options', stay.id, period], queryFn: async () => hostelData(await apiClient.hostel.feeOptions(stay.id, period)), enabled: /^[0-9]{4}-(0[1-9]|1[0-2])$/.test(period) && !result });
  const matching = options.data?.options.filter((item) => paise(item.amount) === paise(stay.monthly_fee)) ?? [];
  const save = useHostelCommand(async () => {
    if (!approved || !matching.some((item) => item.id === head)) throw new Error('Select a matching hostel fee head and confirm the monthly charge');
    return hostelData(await apiClient.hostel.bill(stay.id, { fee_head_id: head, month_bs: period, due_day_bs: Number(dueDay), request_id: key }));
  }, setResult, 'Hostel bill linked to the student fee account', true);
  const edit = (change: () => void) => { change(); setKey(crypto.randomUUID()); };
  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent><DialogHeader><DialogTitle>Post monthly hostel bill</DialogTitle><DialogDescription>{stay.student_name} · Agreed monthly charge {money(stay.monthly_fee)}. Collection and receipts use Fees & Payments.</DialogDescription></DialogHeader>
    {result ? <div className="space-y-4"><p className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-900">{result.already_billed ? 'An existing bill was linked; no duplicate charge was created.' : 'The hostel charge has been posted to the student fee ledger.'}</p><p className="text-sm">{result.month_bs} BS · {money(result.amount)}</p><p className="text-xs text-muted-foreground">Open the student’s dues in Fees & Payments to record cash, bank or cheque collection and print a receipt.</p><DialogFooter><Button variant="outline" onClick={onClose}>Close</Button><Button asChild><Link href="/dashboard/fees">Open Fees & Payments</Link></Button></DialogFooter></div> : <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4"><div className="grid gap-4 sm:grid-cols-2"><HostelField label="BS year"><Input required maxLength={4} pattern="[0-9०-९]{4}" value={year} onChange={(event) => edit(() => { setYearDraft(event.target.value); setHead(''); })} /></HostelField><HostelField label="BS billing month"><select required className={hostelSelect} value={month} onChange={(event) => edit(() => { setMonthDraft(event.target.value); setHead(''); })}><option value="">Choose month</option>{bsMonths.map((label, index) => <option key={label} value={String(index + 1).padStart(2, '0')}>{label}</option>)}</select></HostelField></div>
      {options.isLoading ? <HostelEmpty>Loading optional monthly fee heads…</HostelEmpty> : options.error ? <HostelEmpty error={options.error.message} /> : !matching.length ? <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Set up an optional monthly hostel fee head for this student’s grade and BS year in Fees & Payments. Its amount must match {money(stay.monthly_fee)}.</p> : <HostelField label="Hostel fee head"><select required className={hostelSelect} value={head} onChange={(event) => edit(() => setHead(event.target.value))}><option value="">Choose the school’s hostel fee head</option>{matching.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.structure_name} · {money(item.amount)}</option>)}</select></HostelField>}
      <HostelField label="Due day of BS month"><Input required type="number" min={1} max={28} value={dueDay} onChange={(event) => edit(() => setDueDay(event.target.value))} /></HostelField>
      <label className="flex items-start gap-2 text-sm leading-6"><input required type="checkbox" className="mt-1" checked={approved} onChange={(event) => edit(() => setApproved(event.target.checked))} />The school has approved the full monthly charge for this period. Partial-month concessions will be recorded separately in Fees & Payments.</label>
      <p className="text-xs leading-5 text-muted-foreground">One linked hostel charge per student per BS month prevents repeat bills after transfers. This does not charge a wallet or record payment. No rate or proration rule is assumed.</p>
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!head || !approved || options.isFetching}>{save.isPending ? 'Posting…' : 'Post hostel bill'}</Button></DialogFooter>
    </fieldset></form>}
  </DialogContent></Dialog>;
}
