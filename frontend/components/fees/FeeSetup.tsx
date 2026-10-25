'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Archive, Edit, Loader2, Plus, Trash2, Undo2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { feeData, feeSelectClass, money, validMoney } from '@/lib/api/fees';
import type { FeeFrequency, FeeHead, FeeStructure } from '@/lib/api/fees';
import { FeeEmpty, FeeField } from './FeeDialogs';

interface HeadDraft { name: string; amount: string; frequency: FeeFrequency; is_optional: boolean }
const emptyHead = (): HeadDraft => ({ name: '', amount: '', frequency: 'monthly', is_optional: false });
const frequencyLabels = { monthly: 'Monthly', quarterly: 'Quarterly (months 1, 4, 7, 10)', annual: 'Annual', one_time: 'One-time (this academic year)' };

function HeadFields({ value, onChange }: { value: HeadDraft; onChange: (next: HeadDraft) => void }) {
  return <div className="grid gap-3 sm:grid-cols-2">
    <FeeField label="Fee head name"><Input required maxLength={100} value={value.name} onChange={(event) => onChange({ ...value, name: event.target.value })} placeholder="Tuition, exam, transport…" /></FeeField>
    <FeeField label="Amount per billing period (NPR)"><Input required inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" value={value.amount} onChange={(event) => onChange({ ...value, amount: event.target.value })} /></FeeField>
    <FeeField label="Frequency"><select className={feeSelectClass} value={value.frequency} onChange={(event) => onChange({ ...value, frequency: event.target.value as FeeFrequency })}>{Object.entries(frequencyLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></FeeField>
    <label className="flex items-center gap-2 self-end py-3 text-sm"><input type="checkbox" checked={value.is_optional} onChange={(event) => onChange({ ...value, is_optional: event.target.checked })} />Optional — opt in when billing</label>
  </div>;
}

function StructureEditor({ year, structure, onClose }: { year: string; structure: FeeStructure | null; onClose: () => void }) {
  const [name, setName] = useState(structure?.name ?? '');
  const [grade, setGrade] = useState(structure?.grade ?? '');
  const [description, setDescription] = useState(structure?.description ?? '');
  const [heads, setHeads] = useState<HeadDraft[]>(structure ? [] : [emptyHead()]);
  const queryClient = useQueryClient();
  const save = useMutation({ mutationFn: async () => {
    if (!structure && heads.some((head) => !validMoney(head.amount))) throw new Error('Every fee amount must be positive and have up to two decimal places');
    const payload = { name: name.trim(), description: description.trim() || null };
    return structure ? feeData(await apiClient.fees.structures.update(structure.id, payload)) : feeData(await apiClient.fees.structures.create({ ...payload, grade, academic_year_bs: year, fee_heads: heads }));
  }, onSuccess: async () => { toast.success(structure ? 'Fee structure updated' : 'Fee structure created'); onClose(); await queryClient.invalidateQueries({ queryKey: ['fees', 'structures'] }); }, onError: (error) => toast.error(error.message) });
  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent className="max-w-3xl"><DialogHeader><DialogTitle>{structure ? 'Edit fee structure' : 'Create fee structure'}</DialogTitle><DialogDescription>{year} BS · One active structure per grade. Billed fee heads retain their original terms.</DialogDescription></DialogHeader>
    <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2"><FeeField label="Structure name"><Input required maxLength={150} value={name} onChange={(event) => setName(event.target.value)} placeholder="Regular school fees" /></FeeField><FeeField label="Grade"><select required disabled={Boolean(structure)} className={feeSelectClass} value={grade} onChange={(event) => setGrade(event.target.value)}><option value="">Select grade</option>{Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>Grade {index + 1}</option>)}</select></FeeField></div>
      <FeeField label="Description"><Input maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional notes for the school office" /></FeeField>
      {!structure && <section className="space-y-4"><h3 className="text-sm font-semibold">Fee heads</h3>{heads.map((head, index) => <div key={index} className="rounded-xl border p-4"><HeadFields value={head} onChange={(next) => setHeads((current) => current.map((item, position) => position === index ? next : item))} />{heads.length > 1 && <Button type="button" size="sm" variant="ghost" className="mt-2" onClick={() => setHeads((current) => current.filter((_, position) => position !== index))}><Trash2 />Remove fee head</Button>}</div>)}<Button type="button" variant="outline" disabled={heads.length >= 50} onClick={() => setHeads((current) => [...current, emptyHead()])}><Plus />Add fee head</Button></section>}
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit">{save.isPending && <Loader2 className="animate-spin" />}{structure ? 'Save changes' : 'Create structure'}</Button></DialogFooter>
    </fieldset></form></DialogContent></Dialog>;
}

function HeadEditor({ structure, head, onClose }: { structure: FeeStructure; head: FeeHead | null; onClose: () => void }) {
  const [draft, setDraft] = useState<HeadDraft>(head ?? emptyHead());
  const queryClient = useQueryClient();
  const save = useMutation({ mutationFn: async () => {
    if (!validMoney(draft.amount)) throw new Error('Enter a positive amount with up to two decimal places');
    return head ? feeData(await apiClient.fees.structures.updateHead(structure.id, head.id, draft)) : feeData(await apiClient.fees.structures.addHead(structure.id, draft));
  }, onSuccess: async () => { toast.success('Fee head saved'); onClose(); await queryClient.invalidateQueries({ queryKey: ['fees', 'structures'] }); }, onError: (error) => toast.error(error.message) });
  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent><DialogHeader><DialogTitle>{head ? 'Edit fee head' : 'Add fee head'}</DialogTitle><DialogDescription>{structure.name} · {structure.academic_year_bs} BS</DialogDescription></DialogHeader><form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending}><HeadFields value={draft} onChange={setDraft} /><DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit">{save.isPending && <Loader2 className="animate-spin" />}Save fee head</Button></DialogFooter></fieldset></form></DialogContent></Dialog>;
}

export function FeeSetup({ year, grade, canCreate }: { year: string; grade: string; canCreate: boolean }) {
  const [archived, setArchived] = useState(false);
  const [editor, setEditor] = useState<{ structure: FeeStructure | null } | null>(null);
  const [headEditor, setHeadEditor] = useState<{ structure: FeeStructure; head: FeeHead | null } | null>(null);
  const queryClient = useQueryClient();
  const structures = useQuery({ queryKey: ['fees', 'structures', year, grade, !archived], queryFn: async () => feeData(await apiClient.fees.structures.list({ academic_year_bs: year, grade, is_active: !archived })) });
  const archive = useMutation({ mutationFn: async (structure: FeeStructure) => feeData(await apiClient.fees.structures.update(structure.id, { is_active: !structure.is_active })), onSuccess: async () => { toast.success(archived ? 'Structure restored' : 'Structure archived; existing bills are retained'); await queryClient.invalidateQueries({ queryKey: ['fees', 'structures'] }); }, onError: (error) => toast.error(error.message) });
  const removeHead = useMutation({ mutationFn: async ({ structure, head }: { structure: FeeStructure; head: FeeHead }) => feeData(await apiClient.fees.structures.deleteHead(structure.id, head.id)), onSuccess: async () => { toast.success('Unbilled fee head removed'); await queryClient.invalidateQueries({ queryKey: ['fees', 'structures'] }); }, onError: (error) => toast.error(error.message) });
  return <div className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={archived} onChange={(event) => setArchived(event.target.checked)} />Show archived structures</label>{canCreate && <Button onClick={() => setEditor({ structure: null })}><Plus />New fee structure</Button>}</div>
    {structures.isLoading ? <FeeEmpty>Loading fee structures…</FeeEmpty> : structures.error ? <FeeEmpty error={structures.error.message} /> : structures.data?.length === 0 ? <FeeEmpty>No {archived ? 'archived' : 'active'} fee structures for this selection.{canCreate && !archived && <p className="mt-2">Create a structure, add fee heads, then generate student bills.</p>}</FeeEmpty> : structures.data?.map((structure) => <Card key={structure.id}><CardHeader className="flex flex-wrap items-start justify-between gap-3 sm:flex-row"><div><CardTitle>{structure.name}</CardTitle><p className="mt-1 text-sm text-muted-foreground">Grade {structure.grade} · {structure.academic_year_bs} BS · {structure.is_active ? 'Active' : 'Archived'}</p>{structure.description && <p className="mt-2 text-sm text-muted-foreground">{structure.description}</p>}</div>{canCreate && <div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => setEditor({ structure })}><Edit />Edit</Button><Button variant="outline" size="sm" disabled={archive.isPending} onClick={() => archive.mutate(structure)}>{structure.is_active ? <Archive /> : <Undo2 />}{structure.is_active ? 'Archive' : 'Restore'}</Button></div>}</CardHeader><CardContent><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th className="p-3 text-left">Fee head</th><th className="p-3 text-right">Amount / period</th><th className="p-3 text-left">Frequency</th><th className="p-3 text-left">Billing</th><th className="p-3 text-right">Actions</th></tr></thead><tbody>{structure.fee_heads.map((head) => <tr key={head.id}><td className="p-3 font-medium">{head.name}</td><td className="p-3 text-right">{money(head.amount)}</td><td className="p-3">{frequencyLabels[head.frequency]}</td><td className="p-3">{head.is_optional ? 'Opt-in' : 'Required'}{head.is_billed && <span className="ml-2 rounded-full bg-muted px-2 py-1 text-[10px]">Billed · locked</span>}</td><td className="p-3 text-right">{canCreate && structure.is_active && !head.is_billed && <div className="flex justify-end gap-1"><Button variant="ghost" size="icon" aria-label={`Edit ${head.name}`} onClick={() => setHeadEditor({ structure, head })}><Edit /></Button><Button variant="ghost" size="icon" aria-label={`Remove ${head.name}`} disabled={removeHead.isPending} onClick={() => window.confirm(`Remove unbilled fee head ${head.name}?`) && removeHead.mutate({ structure, head })}><Trash2 className="text-destructive" /></Button></div>}</td></tr>)}</tbody></table></div>{structure.fee_heads.length === 0 && <FeeEmpty>No fee heads yet.</FeeEmpty>}{canCreate && structure.is_active && <Button variant="outline" size="sm" className="mt-4" onClick={() => setHeadEditor({ structure, head: null })}><Plus />Add fee head</Button>}</CardContent></Card>)}
    {editor && <StructureEditor year={year} structure={editor.structure} onClose={() => setEditor(null)} />}
    {headEditor && <HeadEditor structure={headEditor.structure} head={headEditor.head} onClose={() => setHeadEditor(null)} />}
  </div>;
}
