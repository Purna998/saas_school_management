'use client';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Printer } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { reportData } from '@/lib/api/reports';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ReportMessage, ReportPages, ReportTable, ReportTotals, downloadReportBlob, reportStamp } from './ReportCommon';

export function ReportRecord({ id, userId, canExport, canArchive, onClose }: { id: string; userId: string; canExport: boolean; canArchive: boolean; onClose: () => void }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1), [printing, setPrinting] = useState(false), [ending, setEnding] = useState(false);
  const [reason, setReason] = useState(''), [key, setKey] = useState(() => crypto.randomUUID());
  const report = useQuery({ queryKey: ['reports', 'record', userId, id, page], queryFn: async () => reportData(await apiClient.reports.get(id, page)), gcTime: 0 });
  const print = useQuery({ queryKey: ['reports', 'print', userId, id], queryFn: async () => reportData(await apiClient.reports.print(id)), enabled: printing && canExport, retry: false, gcTime: 0 });
  const download = useMutation({ mutationFn: async (format: 'csv' | 'excel') => { const blob = reportData(await apiClient.reports.download(id, format)); downloadReportBlob(blob, id, format); } });
  const archive = useMutation({ mutationFn: async () => reportData(await apiClient.reports.archive(id, { request_id: key, notes: reason.trim() })), onSuccess: async () => { setEnding(false); await Promise.all([client.invalidateQueries({ queryKey: ['reports', 'history'] }), client.invalidateQueries({ queryKey: ['reports', 'record'] })]); } });
  const data = report.data, busy = download.isPending || archive.isPending;
  return <Dialog open onOpenChange={(open) => !open && !busy && onClose()}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>{printing ? 'Complete printable report' : data?.title ?? 'Saved report'}</DialogTitle><DialogDescription>Saved school data · report reference {id.slice(0, 8)}</DialogDescription></DialogHeader>
    {report.isPending ? <ReportMessage>Loading saved report…</ReportMessage> : report.error ? <ReportMessage error={report.error.message}/> : data && <>
      {printing ? <>{print.isFetching ? <ReportMessage>Loading every saved row for printing…</ReportMessage> : print.error ? <ReportMessage error={print.error.message}/> : print.data && <section id="school-report-print" className="space-y-4"><header className="border-b pb-4"><p className="text-xl font-semibold">{print.data.school.name_en}</p>{print.data.school.name_np && <p>{print.data.school.name_np}</p>}<p className="mt-1 text-xs">{[print.data.school.municipality, print.data.school.district].filter(Boolean).join(', ')}{print.data.school.emis_code && ` · School EMIS ${print.data.school.emis_code}`}</p><h2 className="mt-4 text-lg font-semibold">{print.data.title}</h2><p className="mt-2 text-xs">Generated {print.data.generated_at && reportStamp.format(new Date(print.data.generated_at))} NPT · {print.data.generated_by_name} · {print.data.row_count} rows</p><p className="mt-1 text-xs">{Object.entries(print.data.parameters).map(([field, value]) => `${field.replaceAll('_', ' ')}: ${value}`).join(' · ')}</p></header><ReportTotals values={print.data.summary}/><ReportTable columns={print.data.columns} rows={print.data.rows}/><ul className="list-disc space-y-1 pl-4 text-xs">{print.data.notes.map((note) => <li key={note}>{note}</li>)}</ul><footer className="border-t pt-3 text-[9px]">Saved report reference: {id} · SHA256 {print.data.content_hash}</footer></section>}<div className="mt-5 flex justify-end gap-2"><Button variant="outline" onClick={() => setPrinting(false)}>Back to report</Button><Button disabled={print.isFetching || !print.data || print.data.rows.length !== print.data.row_count} onClick={() => window.print()}><Printer size={16}/>Print / Save PDF</Button></div></> : <>
        {data.archived_at && <ReportMessage>Archived {reportStamp.format(new Date(data.archived_at))} NPT · {data.archive_reason}. The saved data is retained.</ReportMessage>}
        {data.error_message && <ReportMessage error={data.error_message}/>}
        <p className="mb-4 text-xs text-muted-foreground">{data.generated_at ? `Generated ${reportStamp.format(new Date(data.generated_at))} NPT` : 'No verified generation time'}{data.generated_by_name && ` · ${data.generated_by_name}`} · {data.status}</p>
        <ReportTotals values={data.summary}/><div className="mt-4"><ReportTable columns={data.columns} rows={data.rows}/></div><ReportPages page={page} total={data.row_count} onPage={setPage} busy={report.isFetching}/>
        <ul className="mt-4 list-disc space-y-1 pl-5 text-xs leading-5 text-muted-foreground">{data.notes.map((note) => <li key={note}>{note}</li>)}</ul>
        <div className="mt-5 flex flex-wrap gap-2">{canExport && data.snapshot_version === 2 && data.status === 'ready' && <><Button variant="outline" disabled={busy} onClick={() => download.mutate('csv')}><Download size={16}/>Download CSV · all rows</Button><Button variant="outline" disabled={busy} onClick={() => download.mutate('excel')}><Download size={16}/>Download Excel · all rows</Button><Button variant="outline" disabled={busy || !data.print_available} onClick={() => setPrinting(true)}><Printer size={16}/>Full print / PDF view</Button></>}{canArchive && !data.archived_at && <Button variant="outline" disabled={busy} onClick={() => setEnding(!ending)}>Archive report</Button>}</div>
        {!data.print_available && data.snapshot_version === 2 && <p className="mt-2 text-xs text-muted-foreground">For large reports, use CSV/Excel or generate a narrower report for printing.</p>}
        {download.error && <ReportMessage error={download.error.message}/>}
        {ending && <form className="mt-5 space-y-3 rounded-xl border p-4" onSubmit={(event) => { event.preventDefault(); archive.mutate(); }}><label className="grid gap-2 text-sm">Archive reason<Input required minLength={3} maxLength={1000} disabled={archive.isPending} value={reason} onChange={(event) => { setReason(event.target.value); setKey(crypto.randomUUID()); }}/></label><p className="text-xs text-muted-foreground">This removes it from the current list and retains its snapshot and history.</p><Button disabled={archive.isPending}>Confirm archive</Button>{archive.error && <ReportMessage error={archive.error.message}/>}</form>}
        {!!data.events.length && <section className="mt-6 border-t pt-4"><h3 className="text-sm font-semibold">Recent report activity</h3><ul className="mt-3 space-y-2 text-xs text-muted-foreground">{data.events.map((event, index) => <li key={index}>{event.action.replaceAll('_', ' ')} · {event.actor_name ?? 'School staff'} · {reportStamp.format(new Date(event.created_at))} NPT{event.notes && ` · ${event.notes}`}</li>)}</ul></section>}
      </>}
    </>}
  </DialogContent></Dialog>;
}
