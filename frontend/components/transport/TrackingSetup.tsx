'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Copy, Link as LinkIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { transportData } from '@/lib/api/transport';
import type { TransportStudent } from '@/lib/api/transport';
import type { FamilyAccess } from '@/lib/api/tracking';
import { TransportEmpty, TransportField, TransportPagination, TransportPicker, transportStamp } from './TransportCommon';

export function PhoneSetup({ tripId, vehicle, onClose }: { tripId: string; vehicle: string; onClose: () => void }) {
  const [label, setLabel] = useState('Assigned helper phone');
  const [link, setLink] = useState('');
  const [notice, setNotice] = useState('');
  const issue = useMutation({ gcTime: 0, mutationFn: async () => transportData(await apiClient.tracking.issuePhone(tripId, label.trim())), onSuccess: (grant) => {
    setLink(`${window.location.origin}/transport/share#code=${encodeURIComponent(grant.token)}`);
    setNotice(`Link expires ${transportStamp.format(new Date(grant.expires_at))} NPT.`);
  } });
  const revoke = useMutation({ mutationFn: async () => transportData(await apiClient.tracking.revokePhone(tripId)), onSuccess: () => { setLink(''); setNotice('All phone links for this trip are revoked.'); } });
  const copy = async () => { try { await navigator.clipboard.writeText(link); setNotice('Copied. Give this link only to the assigned helper or parked driver.'); } catch { setNotice('Select and copy the trip link below.'); } };
  return <Dialog open onOpenChange={(open) => !open && !issue.isPending && !revoke.isPending && onClose()}><DialogContent><DialogHeader><DialogTitle>Connect a trip phone · {vehicle}</DialogTitle><DialogDescription>One phone at a time, limited to this open trip. Creating a link replaces the previous phone link.</DialogDescription></DialogHeader>
    <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); setLink(''); issue.mutate(); }}><TransportField label="Assigned helper / phone label"><Input required minLength={2} maxLength={100} value={label} onChange={(event) => setLabel(event.target.value)}/></TransportField><p className="text-sm leading-6 text-muted-foreground">The phone can send GPS and report stops. It cannot view children’s names or parent contacts. The helper starts sharing explicitly and keeps the HTTPS page open and awake.</p><Button disabled={issue.isPending || revoke.isPending || label.trim().length < 2}><LinkIcon size={16}/>{issue.isPending ? 'Creating…' : 'Create / replace sharing link'}</Button></form>
    {(issue.error || revoke.error) && <TransportEmpty error={(issue.error ?? revoke.error)?.message}/>}
    {link && <div className="mt-4 space-y-2 rounded-xl border bg-accent/30 p-4"><TransportField label="Private trip sharing link"><Input readOnly value={link} onFocus={(event) => event.target.select()}/></TransportField><Button size="sm" variant="outline" onClick={copy}><Copy size={15}/>Copy trip link</Button><p className="text-xs">This secret is shown only here. Close this dialog after handing it to the assigned helper.</p></div>}
    {notice && <p role="status" className="mt-3 text-sm">{notice}</p>}
    <div className="mt-5 flex justify-between gap-2"><Button variant="outline" disabled={issue.isPending || revoke.isPending} onClick={() => revoke.mutate()}>Revoke trip phone access</Button><Button variant="outline" disabled={issue.isPending || revoke.isPending} onClick={onClose}>Done</Button></div>
  </DialogContent></Dialog>;
}

function RevokeFamily({ row, onDone }: { row: FamilyAccess; onDone: () => void }) {
  const client = useQueryClient();
  const [reason, setReason] = useState('');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const revoke = useMutation({ mutationFn: async () => transportData(await apiClient.tracking.unlink(row.id, { notes: reason.trim(), request_id: key })), onSuccess: async () => { await client.invalidateQueries({ queryKey: ['tracking'] }); onDone(); } });
  return <form className="mt-3 space-y-2" onSubmit={(event) => { event.preventDefault(); revoke.mutate(); }}><TransportField label="Reason for ending access"><Input required minLength={3} maxLength={1000} value={reason} onChange={(event) => { setReason(event.target.value); setKey(crypto.randomUUID()); }}/></TransportField>{revoke.error && <p role="alert" className="text-sm text-destructive">{revoke.error.message}</p>}<div className="flex gap-2"><Button size="sm" disabled={revoke.isPending}>Confirm end access</Button><Button type="button" size="sm" variant="outline" disabled={revoke.isPending} onClick={onDone}>Keep access</Button></div></form>;
}

export function FamilySetup({ onClose }: { onClose: () => void }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [student, setStudent] = useState<TransportStudent | null>(null);
  const [email, setEmail] = useState(''), [notes, setNotes] = useState('');
  const [verified, setVerified] = useState(false), [ending, setEnding] = useState<string | null>(null);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [notice, setNotice] = useState('');
  const list = useQuery({ queryKey: ['tracking', 'families', page], queryFn: async () => transportData(await apiClient.tracking.families(page)) });
  const save = useMutation({ mutationFn: async () => {
    if (!student || !verified) throw new Error('Verify the selected student and parent relationship first');
    return transportData(await apiClient.tracking.link({ student_id: student.id, parent_email: email.trim(), notes: notes.trim(), request_id: key }));
  }, onSuccess: async () => { setNotice('Parent access enabled for this student.'); setKey(crypto.randomUUID()); setVerified(false); await client.invalidateQueries({ queryKey: ['tracking'] }); } });
  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>Verified family access</DialogTitle><DialogDescription>Link an existing parent login after the school verifies the relationship. Matching a phone number or email alone never grants access.</DialogDescription></DialogHeader>
    <TransportPicker<TransportStudent> label="students" queryKey={['tracking-students']} load={async (search, selectedPage) => { const data = transportData(await apiClient.transport.students({ search, page: selectedPage })); return { items: data.students, total: data.total }; }} selected={student?.id} onSelect={(value) => { setStudent(value); setVerified(false); setKey(crypto.randomUUID()); }} render={(row) => <><strong>{row.full_name_en}</strong><p>{row.admission_number ?? row.emis_student_id ?? 'School student'} · Grade {row.current_grade ?? '—'}</p></>}/>
    <form className="mt-5 space-y-4 border-t pt-5" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4"><p className="text-sm font-medium">Student: {student?.full_name_en ?? 'Choose a student above'}</p><TransportField label="Existing parent account email"><Input type="email" required maxLength={255} value={email} onChange={(event) => { setEmail(event.target.value); setVerified(false); setKey(crypto.randomUUID()); }}/></TransportField><TransportField label="School verification note"><Input required minLength={3} maxLength={1000} value={notes} onChange={(event) => { setNotes(event.target.value); setKey(crypto.randomUUID()); }}/></TransportField><label className="flex items-start gap-2 text-sm leading-6"><input required type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} className="mt-1.5"/>The school has verified this person is authorized to track this student’s transport.</label><Button disabled={!student || !verified}>{save.isPending ? 'Linking…' : 'Enable parent journey access'}</Button>{save.error && <p role="alert" className="text-sm text-destructive">{save.error.message}</p>}{notice && <p role="status" className="text-sm">{notice}</p>}</fieldset></form>
    <section className="mt-6 border-t pt-5"><h2 className="font-semibold">Current parent links</h2>{list.error ? <TransportEmpty error={list.error.message}/> : !list.data?.links.length ? <TransportEmpty>No verified links yet.</TransportEmpty> : <div className="mt-3 space-y-3">{list.data.links.map((row) => <article key={row.id} className="rounded-xl border p-4 text-sm"><p className="font-medium">{row.student_name}</p><p className="mt-1 break-all text-muted-foreground">{row.parent_email}</p><p className="mt-1 text-xs">{row.notes}</p>{ending === row.id ? <RevokeFamily row={row} onDone={() => setEnding(null)}/> : <Button size="sm" variant="outline" className="mt-3" onClick={() => setEnding(row.id)}>End parent access</Button>}</article>)}</div>}{list.data && <TransportPagination page={page} total={list.data.total} onPage={setPage} busy={list.isFetching}/>}</section>
  </DialogContent></Dialog>;
}
