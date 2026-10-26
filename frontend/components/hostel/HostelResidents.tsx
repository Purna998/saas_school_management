'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Plus, Printer } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { hostelData } from '@/lib/api/hostel';
import type { Resident } from '@/lib/api/hostel';
import { money } from '@/lib/api/fees';
import { useAuthStore } from '@/lib/store/auth';
import { HostelEmpty, HostelField, HostelPagination, HostelStatus, downloadHostelCsv, hostelSelect } from './HostelCommon';
import { HostelHistory } from './HostelReports';

export type StayAction = 'transfer' | 'checkout' | 'leave' | 'returnLeave' | 'visit' | 'bill';

export function HostelResidents({ canAllocate, onAdmit, onResident }: { canAllocate: boolean; onAdmit: () => void; onResident: (id: string) => void }) {
  const [page, setPage] = useState(1); const [search, setSearch] = useState(''); const [submitted, setSubmitted] = useState(''); const [status, setStatus] = useState('active'); const [exporting, setExporting] = useState(false);
  const filters = { search: submitted, status: status || undefined };
  const residents = useQuery({ queryKey: ['hostel', 'residents', filters, page], queryFn: async () => hostelData(await apiClient.hostel.residents({ ...filters, page })) });
  const download = async () => { setExporting(true); try { downloadHostelCsv(hostelData(await apiClient.hostel.export({ report: 'residents', ...filters })), 'residents'); } catch (error) { toast.error((error as Error).message); } finally { setExporting(false); } };
  return <div className="space-y-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Resident register</h2><p className="mt-1 text-sm text-muted-foreground">Current boarders, agreed charges and previous stays.</p></div><div className="flex gap-2"><Button variant="outline" disabled={exporting} onClick={download}><Download />{exporting ? 'Exporting…' : 'Export register'}</Button>{canAllocate && <Button onClick={onAdmit}><Plus />Admit boarder</Button>}</div></div>
    <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); setSubmitted(search.trim()); setPage(1); }}><div className="min-w-48 flex-1"><HostelField label="Search residents"><Input maxLength={200} placeholder="Student, admission number, hostel, room, bed" value={search} onChange={(event) => setSearch(event.target.value)} /></HostelField></div><HostelField label="Stay status"><select className={hostelSelect} value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="active">Current residents</option><option value="vacated">Checked out / transferred</option><option value="">All stay history</option></select></HostelField><Button type="submit" variant="outline">Search</Button></form>
    {residents.isLoading ? <HostelEmpty>Loading residents…</HostelEmpty> : residents.error ? <HostelEmpty error={residents.error.message} /> : !residents.data?.residents.length ? <HostelEmpty>No residents match the applied filters.</HostelEmpty> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-3">Resident at admission</th><th className="p-3">Hostel / bed</th><th className="p-3">Admission</th><th className="p-3">Status / monthly charge</th><th className="p-3">Record</th></tr></thead><tbody>{residents.data.residents.map((stay) => <tr key={stay.id}><td className="min-w-44 p-3"><p className="font-medium">{stay.student_name}</p><p className="mt-1 text-xs text-muted-foreground">{stay.student_reference ?? 'No reference'} · {stay.academic_year_bs} BS</p></td><td className="p-3"><p>{stay.hostel_name}</p><p className="mt-1 text-xs text-muted-foreground">Room {stay.room_number} · Bed {stay.bed_label ?? 'Legacy bed unknown'}</p></td><td className="whitespace-nowrap p-3"><p>{stay.allocated_date_bs} BS</p><p className="mt-1 text-xs text-muted-foreground">{stay.allocated_date_ad} AD</p></td><td className="p-3"><HostelStatus status={stay.return_overdue ? 'overdue' : stay.leave_id ? 'on_leave' : stay.status} /><p className="mt-2 text-xs">{money(stay.monthly_fee)} / month</p>{stay.expected_return_bs && <p className="mt-1 text-xs text-muted-foreground">Expected {stay.expected_return_bs} BS</p>}</td><td className="p-3"><Button size="sm" variant="outline" onClick={() => onResident(stay.id)}>View stay</Button></td></tr>)}</tbody></table></div>}
    {residents.data && <HostelPagination page={page} total={residents.data.total} busy={residents.isFetching} onPage={setPage} />}
    <p className="text-xs text-muted-foreground">A temporary leave keeps the bed occupied. Transfers create a new stay while preserving the previous room, bed and agreed rate.</p>
  </div>;
}

export function HostelStayDialog({ allocationId, canAllocate, canBill, onClose, onAction }: { allocationId: string; canAllocate: boolean; canBill: boolean; onClose: () => void; onAction: (action: StayAction, stay: Resident) => void }) {
  const [history, setHistory] = useState(false);
  const schoolName = useAuthStore((state) => state.user?.tenant_name);
  const resident = useQuery({ queryKey: ['hostel', 'resident', allocationId], queryFn: async () => hostelData(await apiClient.hostel.resident(allocationId)), staleTime: 0, refetchOnMount: 'always' });
  const stay = resident.data;
  return <Dialog open onOpenChange={(open) => !open && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>Hostel stay record</DialogTitle><DialogDescription>Admission snapshots, physical bed, agreed charge and residential activity.</DialogDescription></DialogHeader>
    {resident.isFetching ? <HostelEmpty>Loading current stay…</HostelEmpty> : resident.error ? <HostelEmpty error={resident.error.message} /> : stay && <>
      <section id="hostel-slip" className="space-y-5 rounded-xl border p-5 text-sm"><header className="border-b pb-4"><h2 className="text-lg font-semibold">{schoolName ?? 'School hostel'} · आवासीय विवरण</h2><p className="mt-1">{stay.hostel_name} · Room {stay.room_number} · Bed {stay.bed_label ?? 'Legacy bed unknown'}</p></header><h3 className="text-lg font-semibold">{stay.student_name}</h3><dl className="grid gap-4 sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">Student reference at admission</dt><dd className="mt-1">{stay.student_reference ?? 'Not recorded'}</dd></div><div><dt className="text-xs text-muted-foreground">BS academic year at admission</dt><dd className="mt-1">{stay.academic_year_bs}</dd></div><div><dt className="text-xs text-muted-foreground">Admitted</dt><dd className="mt-1">{stay.allocated_date_bs} BS · {stay.allocated_date_ad} AD</dd></div><div><dt className="text-xs text-muted-foreground">Stay status</dt><dd className="mt-1"><HostelStatus status={stay.return_overdue ? 'overdue' : stay.leave_id ? 'on_leave' : stay.status} /></dd></div><div><dt className="text-xs text-muted-foreground">Agreed monthly charge</dt><dd className="mt-1">{money(stay.monthly_fee)} · Payment recorded separately</dd></div>{stay.vacated_date_bs && <div><dt className="text-xs text-muted-foreground">Checkout / transfer</dt><dd className="mt-1">{stay.vacated_date_bs} BS · {stay.vacated_date_ad} AD</dd></div>}{stay.expected_return_bs && <div><dt className="text-xs text-muted-foreground">Return expected</dt><dd className="mt-1">{stay.expected_return_bs} BS · {stay.expected_return_ad} AD</dd></div>}</dl>{stay.notes && <p>Admission notes: {stay.notes}</p>}{stay.checkout_reason && <p>Checkout / transfer reason: {stay.checkout_reason}</p>}<p className="border-t pt-4 font-mono text-xs text-muted-foreground">Stay ID: {stay.id}</p></section>
      <div className="my-4 flex flex-wrap gap-2">{canAllocate && stay.status === 'active' && <>{!stay.leave_id && <><Button onClick={() => onAction('leave', stay)}>Record approved leave</Button><Button variant="outline" onClick={() => onAction('transfer', stay)}>Transfer</Button><Button variant="outline" onClick={() => onAction('checkout', stay)}>Check out resident</Button></>}{stay.leave_id && <Button onClick={() => onAction('returnLeave', stay)}>Record return from leave</Button>}<Button variant="outline" onClick={() => onAction('visit', stay)}>Log visitor</Button></>}{canBill && <Button variant="outline" disabled={Number(stay.monthly_fee) <= 0} onClick={() => onAction('bill', stay)}>Post monthly hostel bill</Button>}<Button variant="ghost" onClick={() => setHistory(!history)}>{history ? 'Hide activity' : 'View activity'}</Button></div>
      {history && <HostelHistory allocationId={stay.id} />}
      <DialogFooter><Button variant="outline" onClick={onClose}>Close record</Button><Button onClick={() => window.print()}><Printer />Print stay record</Button></DialogFooter>
    </>}
  </DialogContent></Dialog>;
}
