import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { apiClient } from '../lib/api/client';
import { cleanReportFilters, formatReportValue } from '../lib/api/reports';
import type { ReportCatalog, ReportDefinition, ReportDetail, ReportPreview, SavedReport } from '../lib/api/reports';
import { ReportComposer } from '../components/reports/ReportComposer';
import { ReportRecord } from '../components/reports/ReportRecord';
import { ReportTable } from '../components/reports/ReportCommon';

afterEach(cleanup);
const noop = () => {};
const directory: ReportDefinition = { key: 'student_list', title: 'Student directory', group: 'Students', description: 'Current school records', filters: ['grade', 'section', 'status'], required: [], statuses: ['active', 'inactive'], available: true };
const catalog: ReportCatalog = { reports: [directory], today_bs: '2083-07-09', today_ad: '2026-10-26', max_rows: 10000, print_max_rows: 2000 };
const columns: ReportPreview['columns'] = [{ key: 'name', label: 'Student', kind: 'text' }, { key: 'fee', label: 'NPR charge', kind: 'money' }];
const preview: ReportPreview = { title: directory.title, columns, rows: [{ name: 'कृत्रिम विद्यार्थी', fee: '1000.25' }], summary: [{ key: 'rows', label: 'Matching rows', value: '1', kind: 'integer' }], total: 1, page: 1, limit: 20, parameters: {}, notes: ['Current directory, not historic enrollment.'], as_at: '2026-10-26T10:00:00+05:45' };
const report: ReportDetail = { id: 'report-1', report_type: 'student_list', title: directory.title, parameters: {}, file_format: 'csv', status: 'ready', generated_at: preview.as_at, generated_by_name: 'School office', created_at: preview.as_at, snapshot_version: 2, row_count: 1, columns, summary: preview.summary, notes: preview.notes, content_hash: 'checksum', school: { name_en: 'Synthetic Nepal School', name_np: 'कृत्रिम विद्यालय' }, archived_at: null, archive_reason: null, error_message: null, print_available: true, rows: preview.rows, page: 1, limit: 20, events: [] };
function client() { return new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } } }); }
function wrap(q: QueryClient, element: React.ReactNode) { return <QueryClientProvider client={q}>{element}</QueryClientProvider>; }

test('report NPR formatting preserves large paise and signed refunds', () => {
  assert.equal(formatReportValue('9007199254740993.07', 'money'), 'NPR 9,00,71,99,25,47,40,993.07');
  assert.equal(formatReportValue('-0.01', 'money'), 'NPR −0.01');
  assert.equal(formatReportValue(null, 'percent'), '—');
  assert.equal(formatReportValue('50.00', 'percent'), '50.00%');
});

test('report filters normalize BS digits and omit unrelated filters', () => {
  const definition = { ...directory, key: 'attendance_monthly', filters: ['month_bs', 'grade', 'period_number'] };
  assert.deepEqual(cleanReportFilters(definition, { month_bs: '२०८३-०७', grade: '2', section: 'private-unrelated', period_number: '' }), { report_type: 'attendance_monthly', month_bs: '2083-07', grade: 2 });
});

test('empty report table does not invent rows', () => {
  const view = render(<ReportTable columns={columns} rows={[]}/>);
  assert.ok(view.getByText(/No records match/));
  assert.equal(view.queryByText('Sample Student'), null);
});

test('preview requires an explicit action and read-only report access cannot save', async () => {
  const q = client(), original = apiClient.reports.preview;
  let calls = 0;
  apiClient.reports.preview = async () => { calls++; return { success: true, data: preview }; };
  try {
    const view = render(wrap(q, <ReportComposer definition={directory} catalog={catalog} userId="office" canGenerate={false} onSaved={noop}/>));
    assert.equal(calls, 0);
    fireEvent.change(view.getByLabelText('Section'), { target: { value: 'A' } });
    assert.equal(calls, 0);
    fireEvent.click(view.getByRole('button', { name: 'Apply filters & preview' }));
    await waitFor(() => assert.ok(view.getByText('कृत्रिम विद्यार्थी')));
    assert.equal(calls, 1);
    assert.equal(view.queryByRole('button', { name: 'Save all matching rows' }), null);
  } finally { apiClient.reports.preview = original; q.clear(); }
});

test('saved generation retries keep the same request and dirty filters block saving', async () => {
  const q = client(), originalPreview = apiClient.reports.preview, originalGenerate = apiClient.reports.generate;
  const requests: unknown[] = [];
  apiClient.reports.preview = async () => ({ success: true, data: preview });
  apiClient.reports.generate = async (data) => { requests.push(data); return { success: false, data: null as never, error: { message: 'Temporary failure' } }; };
  try {
    const view = render(wrap(q, <ReportComposer definition={directory} catalog={catalog} userId="office" canGenerate onSaved={noop}/>));
    fireEvent.click(view.getByRole('button', { name: 'Apply filters & preview' }));
    await waitFor(() => assert.ok(view.getByRole('button', { name: 'Save all matching rows' })));
    fireEvent.click(view.getByRole('button', { name: 'Save all matching rows' }));
    await waitFor(() => assert.ok(view.getByText('Temporary failure')));
    fireEvent.click(view.getByRole('button', { name: 'Save all matching rows' }));
    await waitFor(() => assert.equal(requests.length, 2));
    assert.deepEqual(requests[0], requests[1]);
    fireEvent.change(view.getByLabelText('Section'), { target: { value: 'B' } });
    assert.equal((view.getByRole('button', { name: 'Save all matching rows' }) as HTMLButtonElement).disabled, true);
    assert.ok(view.getByText(/Filters changed/));
  } finally { apiClient.reports.preview = originalPreview; apiClient.reports.generate = originalGenerate; q.clear(); }
});

test('oversized result previews require narrower filters before saving', async () => {
  const q = client(), original = apiClient.reports.preview;
  apiClient.reports.preview = async () => ({ success: true, data: { ...preview, total: 10001 } });
  try {
    const view = render(wrap(q, <ReportComposer definition={directory} catalog={catalog} userId="office" canGenerate onSaved={noop}/>));
    fireEvent.click(view.getByRole('button', { name: 'Apply filters & preview' }));
    await waitFor(() => assert.ok(view.getByText(/Reports are never silently truncated/)));
    assert.equal((view.getByRole('button', { name: 'Save all matching rows' }) as HTMLButtonElement).disabled, true);
  } finally { apiClient.reports.preview = original; q.clear(); }
});

test('printing fetches every saved row instead of printing the visible page', async () => {
  const q = client(), original = apiClient.reports.print;
  const rows = Array.from({ length: 45 }, (_, index) => ({ name: `Printed rider ${index + 1}`, fee: '10.25' }));
  q.setQueryData(['reports', 'record', 'office', report.id, 1], { ...report, row_count: 45, rows: rows.slice(0, 20) });
  let called = false;
  apiClient.reports.print = async () => { called = true; return { success: true, data: { ...report, row_count: 45, rows } }; };
  try {
    const view = render(wrap(q, <ReportRecord id={report.id} userId="office" canExport canArchive={false} onClose={noop}/>));
    assert.equal(view.queryByText('Printed rider 45'), null);
    fireEvent.click(view.getByRole('button', { name: 'Full print / PDF view' }));
    await waitFor(() => assert.ok(view.getByText('Printed rider 45')));
    assert.equal(called, true);
    assert.equal((view.getByRole('button', { name: 'Print / Save PDF' }) as HTMLButtonElement).disabled, false);
    assert.ok(view.getByText('Synthetic Nepal School'));
  } finally { apiClient.reports.print = original; q.clear(); }
});

test('unverified legacy files have no download action and export-restricted staff see no export controls', () => {
  const q = client();
  q.setQueryData(['reports', 'record', 'office', report.id, 1], { ...report, snapshot_version: 0, status: 'expired', columns: [], rows: [], summary: [], row_count: 0, error_message: 'Legacy placeholder output is unverified.' });
  const view = render(wrap(q, <ReportRecord id={report.id} userId="office" canExport canArchive={false} onClose={noop}/>));
  assert.ok(view.getByText(/Legacy placeholder/));
  assert.equal(view.queryByRole('button', { name: /Download CSV/ }), null);
  view.unmount();
  q.setQueryData(['reports', 'record', 'office', report.id, 1], report);
  const other = render(wrap(q, <ReportRecord id={report.id} userId="office" canExport={false} canArchive={false} onClose={noop}/>));
  assert.equal(other.queryByRole('button', { name: /Download/ }), null);
  assert.equal(other.queryByRole('button', { name: 'Full print / PDF view' }), null);
  q.clear();
});

test('archiving requires a reason and retains the same UUID after a connection error', async () => {
  const q = client(), original = apiClient.reports.archive;
  q.setQueryData(['reports', 'record', 'office', report.id, 1], report);
  const requests: unknown[] = [];
  apiClient.reports.archive = async (_id, data) => { requests.push(data); return { success: false, data: null as unknown as SavedReport, error: { message: 'Retry archive' } }; };
  try {
    const view = render(wrap(q, <ReportRecord id={report.id} userId="office" canExport={false} canArchive onClose={noop}/>));
    fireEvent.click(view.getByRole('button', { name: 'Archive report' }));
    assert.equal((view.getByLabelText('Archive reason') as HTMLInputElement).required, true);
    fireEvent.change(view.getByLabelText('Archive reason'), { target: { value: 'Replaced by reviewed snapshot' } });
    fireEvent.click(view.getByRole('button', { name: 'Confirm archive' }));
    await waitFor(() => assert.ok(view.getByText('Retry archive')));
    fireEvent.click(view.getByRole('button', { name: 'Confirm archive' }));
    await waitFor(() => assert.equal(requests.length, 2));
    assert.deepEqual(requests[0], requests[1]);
  } finally { apiClient.reports.archive = original; q.clear(); }
});
