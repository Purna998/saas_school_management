'use client';
import type { ReportColumn, ReportRow, ReportSummary } from '@/lib/api/reports';
import { formatReportValue } from '@/lib/api/reports';
import { Button } from '@/components/ui/button';

export const reportSelect = 'min-h-10 rounded-lg border bg-background px-3 text-sm focus:ring-2 focus:ring-ring';
export const reportStamp = new Intl.DateTimeFormat('en-NP', { timeZone: 'Asia/Kathmandu', dateStyle: 'medium', timeStyle: 'short' });
export function ReportMessage({ error, children }: { error?: string; children?: React.ReactNode }) {
  return <p role={error ? 'alert' : 'status'} className={`rounded-xl border p-5 text-sm leading-6 ${error ? 'border-destructive/30 text-destructive' : 'text-muted-foreground'}`}>{error ?? children}</p>;
}
export function ReportTable({ columns, rows }: { columns: ReportColumn[]; rows: ReportRow[] }) {
  return <div className="overflow-x-auto rounded-xl border"><table className="w-full text-left text-sm"><thead className="bg-muted/60"><tr>{columns.map((column) => <th key={column.key} scope="col" className="whitespace-nowrap px-4 py-3 text-xs font-semibold">{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index} className="border-t align-top">{columns.map((column) => <td key={column.key} className={`max-w-80 break-words px-4 py-3 ${['money', 'integer', 'decimal', 'percent'].includes(column.kind) ? 'whitespace-nowrap tabular-nums' : 'min-w-28'}`}>{formatReportValue(row[column.key] ?? null, column.kind)}</td>)}</tr>)}</tbody></table>{!rows.length && <p className="p-6 text-center text-sm text-muted-foreground">No records match these filters. No sample or assumed values have been added.</p>}</div>;
}
export function ReportTotals({ values }: { values: ReportSummary[] }) {
  return <dl className="pastel-summary grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{values.map((value) => <div key={value.key} className="rounded-xl border p-4"><dt className="text-xs text-muted-foreground">{value.label}</dt><dd className="mt-2 break-words text-xl font-semibold tabular-nums">{formatReportValue(value.value, value.kind)}</dd></div>)}</dl>;
}
export function ReportPages({ page, total, busy, onPage }: { page: number; total: number; busy: boolean; onPage: (value: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / 20));
  return <div className="flex flex-wrap items-center justify-between gap-3 pt-3 text-xs text-muted-foreground"><p>{total.toLocaleString('en-NP')} rows · Page {page} of {pages}</p><div className="flex gap-2"><Button size="sm" variant="outline" disabled={busy || page <= 1} onClick={() => onPage(page - 1)}>Previous</Button><Button size="sm" variant="outline" disabled={busy || page >= pages} onClick={() => onPage(page + 1)}>Next</Button></div></div>;
}
export function downloadReportBlob(blob: Blob, id: string, format: 'csv' | 'excel') {
  const url = URL.createObjectURL(blob), link = document.createElement('a');
  link.href = url; link.download = `school-report-${id}.${format === 'excel' ? 'xlsx' : 'csv'}`; link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
