'use client';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Eye, Save } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { cleanReportFilters, reportData } from '@/lib/api/reports';
import type { ReportCatalog, ReportDefinition, ReportFilters, ReportExamOption, ReportStudentOption } from '@/lib/api/reports';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { TransportBsField, TransportField, TransportPicker, useTransportBsDates } from '@/components/transport/TransportCommon';
import { ReportMessage, ReportPages, ReportTable, ReportTotals, reportSelect, reportStamp } from './ReportCommon';

export function ReportComposer({ definition, catalog, canGenerate, userId, onSaved }: { definition: ReportDefinition; catalog: ReportCatalog; canGenerate: boolean; userId: string; onSaved: (id: string) => void }) {
  const client = useQueryClient();
  const [values, setValues] = useState<Record<string, string>>({ academic_year_bs: catalog.today_bs.slice(0, 4), month_bs: catalog.today_bs.slice(0, 7), date_from_bs: `${catalog.today_bs.slice(0, 7)}-01`, date_to_bs: catalog.today_bs });
  const [title, setTitle] = useState(''), [format, setFormat] = useState<'csv' | 'excel'>('csv');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [applied, setApplied] = useState<ReportFilters | null>(null), [page, setPage] = useState(1);
  const filters = cleanReportFilters(definition, values);
  const dirty = JSON.stringify(filters) !== JSON.stringify(applied);
  const ready = definition.required.every((field) => Boolean(values[field]?.trim()));
  const has = (name: string) => definition.filters.includes(name);
  const dates = useTransportBsDates(has('date_from_bs') ? { from: values.date_from_bs ?? '', to: values.date_to_bs ?? '' } : {});
  const preview = useQuery({ queryKey: ['reports', 'preview', userId, applied, page], enabled: applied !== null, queryFn: async () => reportData(await apiClient.reports.preview(applied!, page)), gcTime: 0, retry: false });
  const change = (field: string, value: string) => { setValues((previous) => ({ ...previous, [field]: value })); setKey(crypto.randomUUID()); };
  const save = useMutation({ gcTime: 0, mutationFn: async () => {
    if (dirty || !applied) throw new Error('Preview the current filters before saving');
    return reportData(await apiClient.reports.generate({ ...applied, title: title.trim() || undefined, file_format: format, request_id: key }));
  }, onSuccess: async (report) => { await client.invalidateQueries({ queryKey: ['reports', 'history'] }); setKey(crypto.randomUUID()); onSaved(report.id); } });
  const busy = save.isPending;
  return <section className="space-y-5 rounded-2xl border bg-card p-4 sm:p-6">
    <header><h2 className="text-lg font-semibold">{definition.title}</h2><p className="mt-1 text-sm leading-6 text-muted-foreground">{definition.description}</p></header>
    {has('student_id') && <TransportPicker<ReportStudentOption> label="report students" queryKey={['reports', 'student', userId]} load={async (search, selectedPage) => reportData(await apiClient.reports.students(search, selectedPage))} selected={values.student_id} onSelect={(student) => change('student_id', student.id)} disabled={busy} render={(student) => <><strong>{student.full_name_en}</strong><p className="mt-1 text-xs">{student.admission_number ?? 'No admission reference'} · Grade {student.current_grade ?? 'Unassigned'}</p></>}/>}
    {has('exam_id') && <TransportPicker<ReportExamOption> label="report exams" queryKey={['reports', 'exam', userId]} load={async (search, selectedPage) => reportData(await apiClient.reports.exams(search, selectedPage))} selected={values.exam_id} onSelect={(exam) => change('exam_id', exam.id)} disabled={busy} render={(exam) => <><strong>{exam.name}</strong><p className="mt-1 text-xs">Grade {exam.grade} · {exam.academic_year_bs} BS · {exam.status}</p></>}/>}
    <form onSubmit={(event) => { event.preventDefault(); setApplied(filters); setPage(1); if (!dirty) void preview.refetch(); }}><fieldset disabled={busy} className="grid items-end gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {has('academic_year_bs') && <TransportField label="BS academic year"><Input required={definition.required.includes('academic_year_bs')} maxLength={10} placeholder="2083 or 2083/084" value={values.academic_year_bs ?? ''} onChange={(event) => change('academic_year_bs', event.target.value)}/></TransportField>}
      {has('month_bs') && <TransportField label="BS month (YYYY-MM)"><Input required pattern="[0-9०-९]{4}-[0-9०-९]{2}" maxLength={7} placeholder="2083-07" value={values.month_bs ?? ''} onChange={(event) => change('month_bs', event.target.value)}/></TransportField>}
      {has('date_from_bs') && <TransportBsField required label="From BS (inclusive)" value={values.date_from_bs ?? ''} onChange={(value) => change('date_from_bs', value)} ad={dates.data?.from}/>}
      {has('date_to_bs') && <TransportBsField required label="To BS (inclusive)" value={values.date_to_bs ?? ''} onChange={(value) => change('date_to_bs', value)} ad={dates.data?.to}/>}
      {has('grade') && <TransportField label="Grade"><select className={reportSelect} value={values.grade ?? ''} onChange={(event) => change('grade', event.target.value)}><option value="">All recorded grades</option>{Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>Grade {index + 1}</option>)}</select></TransportField>}
      {has('section') && <TransportField label="Section"><Input maxLength={10} placeholder="All sections" value={values.section ?? ''} onChange={(event) => change('section', event.target.value)}/></TransportField>}
      {has('status') && <TransportField label="Record state"><select className={reportSelect} value={values.status ?? ''} onChange={(event) => change('status', event.target.value)}><option value="">All states</option>{definition.statuses.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select></TransportField>}
      {has('period_number') && <TransportField label="Attendance register"><select className={reportSelect} value={values.period_number ?? ''} onChange={(event) => change('period_number', event.target.value)}><option value="">Daily register only</option>{Array.from({ length: 8 }, (_, index) => <option key={index + 1} value={index + 1}>Period {index + 1} only</option>)}</select></TransportField>}
      <Button type="submit" disabled={!ready || preview.isFetching || (has('date_from_bs') && (!dates.data?.from || !dates.data?.to))}><Eye size={16}/>{preview.isFetching ? 'Loading preview…' : 'Apply filters & preview'}</Button>
    </fieldset></form>
    {dates.error && <ReportMessage error={dates.error.message}/>}
    {!ready && <p className="text-xs text-muted-foreground">Complete the required filters or choose a student/exam above.</p>}
    {preview.error && <ReportMessage error={preview.error.message}/>}
    {preview.data && <>
      <div className="space-y-4 border-t pt-5"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Live preview</h3><p className="text-xs text-muted-foreground">Read {reportStamp.format(new Date(preview.data.as_at))} NPT</p></div>{dirty && <ReportMessage>Filters changed. Apply them again before saving. The preview below still uses the previously applied filters.</ReportMessage>}<ReportTotals values={preview.data.summary}/><ReportTable columns={preview.data.columns} rows={preview.data.rows}/><ReportPages page={page} total={preview.data.total} onPage={setPage} busy={preview.isFetching}/><ul className="list-disc space-y-1 pl-5 text-xs leading-5 text-muted-foreground">{preview.data.notes.map((note) => <li key={note}>{note}</li>)}</ul></div>
      {canGenerate && <form className="space-y-4 border-t pt-5" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><h3 className="font-semibold">Save a report snapshot</h3><p className="text-xs leading-5 text-muted-foreground">Saving reads all matching rows again. Preview and saved totals can differ if school records changed meanwhile. The saved report keeps its own data and generation time.</p><fieldset disabled={busy} className="flex flex-wrap items-end gap-3"><TransportField label="Report title (optional)"><Input maxLength={180} minLength={title ? 3 : undefined} placeholder={definition.title} value={title} onChange={(event) => { setTitle(event.target.value); setKey(crypto.randomUUID()); }}/></TransportField><TransportField label="Preferred download format"><select className={reportSelect} value={format} onChange={(event) => { setFormat(event.target.value as 'csv' | 'excel'); setKey(crypto.randomUUID()); }}><option value="csv">CSV · UTF-8 Nepali text</option><option value="excel">Excel workbook (.xlsx)</option></select></TransportField><Button type="submit" disabled={dirty || preview.isFetching || Boolean(preview.error) || preview.data.total > catalog.max_rows}><Save size={16}/>{busy ? 'Saving all rows…' : 'Save all matching rows'}</Button></fieldset>{preview.data.total > catalog.max_rows && <ReportMessage>Narrow the filters to at most {catalog.max_rows.toLocaleString()} rows. Reports are never silently truncated.</ReportMessage>}{save.error && <ReportMessage error={save.error.message}/>}<p className="text-xs text-muted-foreground">Open a saved report to download or Print / Save PDF. Print supports up to {catalog.print_max_rows.toLocaleString()} rows.</p></form>}
    </>}
  </section>;
}
