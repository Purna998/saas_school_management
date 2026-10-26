import type { ApiResponse } from './client';

export interface ReportDefinition {
  key: string; title: string; group: string; description: string; filters: string[];
  required: string[]; statuses: string[]; available: boolean;
}
export interface ReportCatalog { reports: ReportDefinition[]; today_bs: string; today_ad: string; max_rows: number; print_max_rows: number }
export interface ReportFilters {
  report_type: string; academic_year_bs?: string; month_bs?: string; date_from_bs?: string; date_to_bs?: string;
  grade?: number; section?: string; status?: string; period_number?: number; exam_id?: string; student_id?: string;
}
export interface ReportColumn { key: string; label: string; kind: 'text' | 'integer' | 'money' | 'decimal' | 'date' | 'bs_date' | 'percent' }
export type ReportRow = Record<string, string | null>;
export interface ReportSummary { key: string; label: string; kind: ReportColumn['kind']; value: string }
export interface ReportPreview {
  title: string; columns: ReportColumn[]; rows: ReportRow[]; summary: ReportSummary[]; total: number;
  page: number; limit: number; parameters: Record<string, string | number>; notes: string[]; as_at: string;
}
export interface SavedReport {
  id: string; report_type: string; title: string; parameters: Record<string, string | number>;
  file_format: 'csv' | 'excel' | 'pdf'; status: 'ready' | 'expired' | 'failed' | 'generating'; generated_at: string | null;
  generated_by_name: string | null; created_at: string; snapshot_version: number; row_count: number;
  columns: ReportColumn[]; summary: ReportSummary[]; notes: string[]; content_hash: string | null;
  school: { name_en?: string; name_np?: string | null; emis_code?: string | null; municipality?: string | null; district?: string | null };
  archived_at: string | null; archive_reason: string | null; error_message: string | null; print_available: boolean;
}
export interface ReportDetail extends SavedReport {
  rows: ReportRow[]; page: number; limit: number;
  events: { action: string; actor_name: string | null; created_at: string; notes: string | null }[];
}
export interface ReportStudentOption { id: string; full_name_en: string; admission_number: string | null; current_grade: number | null }
export interface ReportExamOption { id: string; name: string; grade: number; academic_year_bs: string; status: string }
const reportNumbers = new Intl.NumberFormat('ne-NP', { numberingSystem: 'latn' });
export const reportData = <T,>(value: ApiResponse<T>) => { if (!value.success) throw new Error(value.error?.message ?? 'Unable to load the report'); return value.data; };
export function formatReportValue(value: string | null, kind: ReportColumn['kind']) {
  if (value === null) return '—';
  if (kind === 'money' && /^-?\d+(\.\d{1,2})?$/.test(value)) {
    const negative = value.startsWith('-'), [whole, fraction = ''] = value.replace(/^-/, '').split('.');
    return `NPR ${negative ? '−' : ''}${reportNumbers.format(BigInt(whole))}.${fraction.padEnd(2, '0')}`;
  }
  if (kind === 'integer' && /^-?\d+$/.test(value)) return reportNumbers.format(BigInt(value));
  return kind === 'percent' ? `${value}%` : value;
}
export function cleanReportFilters(definition: ReportDefinition, values: Record<string, string>): ReportFilters {
  const result: ReportFilters = { report_type: definition.key };
  definition.filters.forEach((key) => {
    let value = values[key]?.trim();
    if (!value) return;
    if (key.endsWith('_bs')) value = value.replace(/[०-९]/g, (digit) => String('०१२३४५६७८९'.indexOf(digit)));
    Object.assign(result, { [key]: ['grade', 'period_number'].includes(key) ? Number(value) : value });
  });
  return result;
}
