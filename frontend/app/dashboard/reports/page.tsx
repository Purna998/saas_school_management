'use client';
import { useState } from 'react';
import dynamic from 'next/dynamic';
import { useQuery } from '@tanstack/react-query';
import { BarChart3, LockKeyhole, RefreshCw } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { reportData } from '@/lib/api/reports';
import { useAuthStore } from '@/lib/store/auth';
import { Button } from '@/components/ui/button';
import { ReportComposer } from '@/components/reports/ReportComposer';
import { ReportMessage, ReportPages, reportSelect, reportStamp } from '@/components/reports/ReportCommon';

const ReportRecord = dynamic(() => import('@/components/reports/ReportRecord').then((module) => module.ReportRecord));

export default function ReportsPage() {
  const user = useAuthStore((state) => state.user), permissions = new Set(user?.permissions ?? []);
  const has = (permission: string) => permissions.has(permission) || permissions.has('*:*');
  const canRead = has('report:read') && !['parent', 'student'].includes(user?.role ?? '');
  const [tab, setTab] = useState<'generate' | 'history'>('generate'), [choice, setChoice] = useState<string | null>(null), [id, setId] = useState<string | null>(null);
  const [page, setPage] = useState(1), [kind, setKind] = useState(''), [archived, setArchived] = useState(false);
  const catalog = useQuery({ queryKey: ['reports', 'catalog', user?.id], queryFn: async () => reportData(await apiClient.reports.catalog()), enabled: canRead, staleTime: 300000 });
  const history = useQuery({ queryKey: ['reports', 'history', user?.id, page, kind, archived], queryFn: async () => reportData(await apiClient.reports.list({ page, report_type: kind || undefined, archived })), enabled: canRead && tab === 'history', gcTime: 0 });
  const definition = catalog.data?.reports.find((item) => item.key === choice && item.available) ?? catalog.data?.reports.find((item) => item.available);
  if (!canRead) return <ReportMessage>Reports are available to authorized school staff. Parent and student records use their own dedicated views.</ReportMessage>;
  return <div className="space-y-6"><header className="flex flex-wrap items-center justify-between gap-4"><div><h1>Reports / प्रतिवेदन</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">Real school records, clear BS periods and saved reports you can review, export and print.</p></div><Button variant="outline" disabled={catalog.isFetching || history.isFetching} onClick={() => { void catalog.refetch(); if (tab === 'history') void history.refetch(); }}><RefreshCw size={16}/>Refresh</Button></header>
    <nav className="section-tabs" aria-label="Reports sections"><Button variant={tab === 'generate' ? 'default' : 'ghost'} onClick={() => setTab('generate')}>Explore & preview</Button><Button variant={tab === 'history' ? 'default' : 'ghost'} onClick={() => setTab('history')}>Saved report history</Button></nav>
    {catalog.error ? <ReportMessage error={catalog.error.message}/> : catalog.isPending ? <ReportMessage>Loading report catalog…</ReportMessage> : tab === 'generate' && catalog.data ? <>
      <section aria-label="Report catalog" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{catalog.data.reports.map((item) => <button key={item.key} type="button" aria-pressed={definition?.key === item.key} disabled={!item.available} className={`rounded-xl border p-4 text-left transition-colors disabled:opacity-60 ${definition?.key === item.key ? 'border-primary bg-primary/5' : 'bg-card hover:bg-accent/30'}`} onClick={() => setChoice(item.key)}><div className="flex items-start justify-between gap-2"><span className="text-xs text-muted-foreground">{item.group}</span>{item.available ? <BarChart3 size={16} className="text-primary"/> : <LockKeyhole size={16}/>}</div><h2 className="mt-2 text-sm font-semibold">{item.title}</h2><p className="mt-2 text-xs leading-5 text-muted-foreground">{item.available ? item.description : 'Source-module access is required to view this report.'}</p></button>)}</section>
      {definition ? <ReportComposer key={definition.key} definition={definition} catalog={catalog.data} userId={user!.id} canGenerate={has('report:generate')} onSaved={setId}/> : <ReportMessage>No source reports are available to this account. The school administrator can review its reporting access.</ReportMessage>}
    </> : tab === 'history' && <section className="space-y-4 rounded-2xl border bg-card p-5"><div className="flex flex-wrap items-end justify-between gap-3"><h2 className="font-semibold">Saved school reports</h2><div className="flex flex-wrap items-center gap-3"><label className="grid gap-1 text-xs">Report type<select className={reportSelect} value={kind} onChange={(event) => { setKind(event.target.value); setPage(1); }}><option value="">All authorized reports</option>{catalog.data?.reports.filter((item) => item.available).map((item) => <option key={item.key} value={item.key}>{item.title}</option>)}</select></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={archived} onChange={(event) => { setArchived(event.target.checked); setPage(1); }}/>Archived reports</label></div></div>
      {history.isPending ? <ReportMessage>Loading saved reports…</ReportMessage> : history.error ? <ReportMessage error={history.error.message}/> : !history.data?.reports.length ? <ReportMessage>No reports in this view. Preview a report and save a snapshot to start.</ReportMessage> : <div className="space-y-3">{history.data.reports.map((report) => <article key={report.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4"><div><h3 className="text-sm font-semibold">{report.title}</h3><p className="mt-1 text-xs text-muted-foreground">{report.generated_at ? `${reportStamp.format(new Date(report.generated_at))} NPT` : 'Unverified legacy output'} · {report.row_count.toLocaleString()} rows · {report.status}</p>{report.generated_by_name && <p className="mt-1 text-xs text-muted-foreground">Saved by {report.generated_by_name}</p>}</div><Button size="sm" variant="outline" onClick={() => setId(report.id)}>Open saved report</Button></article>)}</div>}{history.data && <ReportPages page={page} total={history.data.total} busy={history.isFetching} onPage={setPage}/>}</section>}
    {id && <ReportRecord key={id} id={id} userId={user!.id} canExport={has('report:export')} canArchive={has('report:delete')} onClose={() => setId(null)}/>}
  </div>;
}
