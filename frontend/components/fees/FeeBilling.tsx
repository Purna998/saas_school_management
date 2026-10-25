'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FilePlus2, Loader2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api/client';
import { bsMonthNames, feeData, feeSelectClass, fromPaise, money, paise } from '@/lib/api/fees';
import type { FeeStructure } from '@/lib/api/fees';
import { FeeEmpty, FeeField } from './FeeDialogs';

function ClassBilling({ structure, section, year }: { structure: FeeStructure; section: string; year: string }) {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [months, setMonths] = useState<number[]>(Array.from({ length: 12 }, (_, index) => index + 1));
  const [optional, setOptional] = useState<string[]>([]);
  const [dueDay, setDueDay] = useState('10');
  const queryClient = useQueryClient();
  const roster = useQuery({ queryKey: ['students', 'roster', Number(structure.grade), section || undefined], queryFn: async () => feeData(await apiClient.fees.roster(Number(structure.grade), section || undefined)) });
  const students = roster.data?.students ?? [];
  const chosen = students.filter((student) => selected.has(student.id));
  const heads = structure.fee_heads.filter((head) => !head.is_optional || optional.includes(head.id));
  const periodCount = (frequency: string) => frequency === 'monthly' ? months.length : frequency === 'quarterly' ? months.filter((month) => [1, 4, 7, 10].includes(month)).length : months.includes(1) ? 1 : 0;
  const bills = heads.reduce((sum, head) => sum + periodCount(head.frequency), 0) * chosen.length;
  const amount = heads.reduce((sum, head) => sum + paise(head.amount) * BigInt(periodCount(head.frequency)), BigInt(0)) * BigInt(chosen.length);
  const generate = useMutation({ mutationFn: async () => feeData(await apiClient.fees.generate({
    academic_year_bs: year, grade: structure.grade, fee_structure_id: structure.id,
    student_ids: chosen.map((student) => student.id), months, optional_head_ids: optional, due_day_bs: Number(dueDay),
  })), onSuccess: async (result) => {
    toast.success(`${result.entries_created} bills created; ${result.entries_skipped} existing bills skipped`);
    await queryClient.invalidateQueries({ queryKey: ['fees'] });
  }, onError: (error) => toast.error(error.message) });
  const toggleStudent = (id: string, checked: boolean) => setSelected((current) => { const next = new Set(current); if (checked) next.add(id); else next.delete(id); return next; });
  return <form className="grid gap-5 xl:grid-cols-[1fr_1.1fr]" onSubmit={(event) => { event.preventDefault(); if (window.confirm(`Generate up to ${bills} bills for ${chosen.length} students, totaling ${money(fromPaise(amount))}? Existing bills will be skipped.`)) generate.mutate(); }}>
    <Card><CardHeader className="flex-row items-start justify-between"><div><CardTitle>Select students</CardTitle><p className="mt-1 text-sm text-muted-foreground">Grade {structure.grade}{section ? ` · Section ${section}` : ' · All sections'} · {chosen.length} selected</p></div><Button type="button" size="icon" variant="ghost" disabled={roster.isFetching} aria-label="Refresh billing roster" onClick={() => roster.refetch()}><RefreshCw className={roster.isFetching ? 'animate-spin' : ''} /></Button></CardHeader><CardContent>
      {roster.isLoading ? <FeeEmpty>Loading students…</FeeEmpty> : roster.error ? <FeeEmpty error={roster.error.message} /> : students.length === 0 ? <FeeEmpty>No active students match this grade and section.</FeeEmpty> : <>
        <label className="mb-3 flex items-center gap-2 border-b pb-3 text-sm font-medium"><input type="checkbox" checked={chosen.length === students.length} disabled={generate.isPending} onChange={(event) => setSelected(event.target.checked ? new Set(students.map((student) => student.id)) : new Set())} />Select all {students.length} students</label>
        <div className="max-h-[460px] overflow-y-auto">{students.map((student) => <label key={student.id} className="flex min-h-11 cursor-pointer items-center gap-3 rounded-lg px-2 py-2 text-sm hover:bg-muted"><input type="checkbox" checked={selected.has(student.id)} disabled={generate.isPending} onChange={(event) => toggleStudent(student.id, event.target.checked)} /><span className="w-8 text-muted-foreground">{student.roll_number ?? '—'}</span><span>{student.full_name_en}</span></label>)}</div>
      </>}
    </CardContent></Card>
    <Card><CardHeader><CardTitle>Billing periods and fees</CardTitle><p className="mt-1 text-sm text-muted-foreground">{structure.name} · {year} BS</p></CardHeader><CardContent><fieldset disabled={generate.isPending} className="space-y-5">
      <section className="space-y-2"><h3 className="text-sm font-medium">Required fees in this structure</h3>{structure.fee_heads.filter((head) => !head.is_optional).map((head) => <div key={head.id} className="flex flex-wrap justify-between gap-2 rounded-lg bg-muted/40 px-3 py-2 text-sm"><span>{head.name}</span><span>{money(head.amount)} · {head.frequency.replaceAll('_', ' ')}</span></div>)}{!structure.fee_heads.some((head) => !head.is_optional) && <p className="text-xs text-muted-foreground">No required fee heads. Select an optional fee below.</p>}</section>
      <section><div className="mb-3 flex items-center justify-between"><h3 className="text-sm font-medium">BS months</h3><Button type="button" variant="ghost" size="sm" onClick={() => setMonths(months.length === 12 ? [] : Array.from({ length: 12 }, (_, index) => index + 1))}>{months.length === 12 ? 'Clear months' : 'Select all months'}</Button></div><div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{bsMonthNames.map((name, index) => <label key={name} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={months.includes(index + 1)} onChange={(event) => setMonths((current) => event.target.checked ? [...current, index + 1] : current.filter((month) => month !== index + 1))} />{name}</label>)}</div><p className="mt-3 text-xs leading-5 text-muted-foreground">Quarterly fees bill in Baisakh, Shrawan, Kartik, and Magh. Annual and one-time fees are included only when Baisakh is selected. Choose the student&apos;s actual enrollment periods.</p></section>
      {structure.fee_heads.some((head) => head.is_optional) && <section className="space-y-2 border-t pt-4"><h3 className="text-sm font-medium">Optional fees for all selected students</h3>{structure.fee_heads.filter((head) => head.is_optional).map((head) => <label key={head.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={optional.includes(head.id)} onChange={(event) => setOptional((current) => event.target.checked ? [...current, head.id] : current.filter((id) => id !== head.id))} />{head.name} · {money(head.amount)} / period</label>)}</section>}
      <FeeField label="Due on BS day of the billing month"><Input required type="number" min={1} max={28} value={dueDay} onChange={(event) => setDueDay(event.target.value)} className="max-w-28" /></FeeField>
      <section className="rounded-xl bg-accent/50 p-4 text-sm"><p><strong>{chosen.length}</strong> students · up to <strong>{bills}</strong> bills</p><p className="mt-2 text-lg font-semibold">{money(fromPaise(amount))}</p><p className="mt-2 text-xs text-muted-foreground">Estimate before existing bills are skipped. Previously generated amounts and paid balances are retained.</p></section>
      {bills > 25000 && <p role="alert" className="text-sm text-destructive">Select fewer students or months; a batch supports up to 25,000 bills.</p>}
      <Button type="submit" disabled={!bills || bills > 25000 || generate.isPending || roster.isFetching} className="w-full">{generate.isPending ? <Loader2 className="animate-spin" /> : <FilePlus2 />}Generate {bills} bills</Button>
      {generate.data && <p role="status" className="rounded-lg border p-3 text-sm">Created {generate.data.entries_created} bills totaling {money(generate.data.total_assessed)}. Skipped {generate.data.entries_skipped} existing bills.</p>}
    </fieldset></CardContent></Card>
  </form>;
}

export function FeeBilling({ year, grade }: { year: string; grade: string }) {
  const [structureId, setStructureId] = useState('');
  const [sectionDraft, setSectionDraft] = useState('');
  const [section, setSection] = useState('');
  const structures = useQuery({ queryKey: ['fees', 'structures', year, grade, true], queryFn: async () => feeData(await apiClient.fees.structures.list({ academic_year_bs: year, grade })) });
  const effectiveStructure = structures.data?.find((structure) => structure.id === structureId) ?? structures.data?.[0];
  return <div className="space-y-5"><Card><CardContent className="flex flex-col gap-4 pt-5 sm:flex-row sm:items-end"><FeeField label="Active fee structure"><select className={`${feeSelectClass} sm:min-w-72`} value={effectiveStructure?.id ?? ''} onChange={(event) => setStructureId(event.target.value)}>{!structures.data?.length && <option value="">No active structure</option>}{structures.data?.map((structure) => <option key={structure.id} value={structure.id}>Grade {structure.grade} · {structure.name}</option>)}</select></FeeField><form className="flex items-end gap-2" onSubmit={(event) => { event.preventDefault(); setSection(sectionDraft.trim()); }}><FeeField label="Section (blank for all)"><Input maxLength={10} value={sectionDraft} onChange={(event) => setSectionDraft(event.target.value)} placeholder="A" /></FeeField><Button type="submit" variant="outline">Apply section</Button></form></CardContent></Card>
    {structures.isLoading ? <FeeEmpty>Loading structures…</FeeEmpty> : structures.error ? <FeeEmpty error={structures.error.message} /> : effectiveStructure ? <ClassBilling key={`${year}:${effectiveStructure.id}:${section}`} structure={effectiveStructure} section={section} year={year} /> : <FeeEmpty>Create an active fee structure in Fee setup before generating student bills.</FeeEmpty>}
  </div>;
}
