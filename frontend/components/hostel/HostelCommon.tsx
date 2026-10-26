'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api/client';
import { bsString, hostelData, normalizeBsInput } from '@/lib/api/hostel';
import type { CalendarConversion } from '@/lib/api/hostel';
import { nepalDate } from '@/lib/api/library';
import { useAuthStore } from '@/lib/store/auth';

export const hostelSelect = 'min-h-10 rounded-lg border border-input bg-background px-3 text-sm focus:ring-2 focus:ring-ring';
export function HostelField({ label, children }: { label: string; children: React.ReactNode }) { return <label className="grid gap-1.5 text-sm"><span className="font-medium">{label}</span>{children}</label>; }
export function HostelEmpty({ error, children }: { error?: string; children?: React.ReactNode }) { return <div role={error ? 'alert' : undefined} className={`py-9 text-center text-sm ${error ? 'text-destructive' : 'text-muted-foreground'}`}>{error ?? children}</div>; }
export function HostelStat({ label, value }: { label: string; value: string | number }) { return <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p></div>; }
export function HostelStatus({ status }: { status: string }) { return <span className={`inline-block rounded-full px-2.5 py-1 text-xs ${['absent', 'overdue', 'maintenance'].includes(status) ? 'bg-amber-50 text-amber-800' : ['present', 'taken', 'active', 'available'].includes(status) ? 'bg-emerald-50 text-emerald-800' : 'bg-accent text-primary'}`}>{status.replaceAll('_', ' ')}</span>; }
export function HostelPagination({ page, total, busy, onPage }: { page: number; total: number; busy?: boolean; onPage: (page: number) => void }) { return <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-4 text-sm"><p className="text-muted-foreground">{total} records · Page {page} of {Math.max(1, Math.ceil(total / 20))}</p><div className="flex gap-2"><Button variant="outline" size="sm" disabled={busy || page <= 1} onClick={() => onPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={busy || page * 20 >= total} onClick={() => onPage(page + 1)}>Next</Button></div></div>; }
export function useHostelCommand<T>(execute: () => Promise<T>, onSuccess: (result: T) => void, message: string, fees = false) {
  const client = useQueryClient();
  return useMutation({ mutationFn: execute, onSuccess: async (data) => { toast.success(message); onSuccess(data); await client.invalidateQueries({ queryKey: ['hostel'] }); if (fees) await client.invalidateQueries({ queryKey: ['fees'] }); }, onError: (error) => toast.error(error.message) });
}
export function useHostelAccess() {
  const user = useAuthStore((state) => state.user);
  const has = (code: string) => Boolean(user?.permissions?.includes(code) || user?.permissions?.includes('*:*'));
  const canEdit = has('hostel:create'); const canAllocate = has('hostel:allocate');
  return { canRead: has('hostel:read') && (!['parent', 'student'].includes(user?.role ?? '') || canEdit || canAllocate), canEdit, canAllocate, canBill: has('fee:create') };
}
export function useHostelToday() {
  const ad = nepalDate();
  return useQuery({ queryKey: ['calendar', 'nepal-date', ad], queryFn: async () => hostelData(await apiClient.calendar.convertAdToBs(ad)) as CalendarConversion, select: (data) => ({ ad, bs: bsString(data), year: `${data.bs_date.year}/${String((data.bs_date.year + 1) % 1000).padStart(3, '0')}` }), staleTime: 60_000 });
}
export function useBsDate(value: string) {
  const normalized = normalizeBsInput(value);
  return useQuery({ queryKey: ['calendar', 'bs-ad', normalized], queryFn: async () => hostelData(await apiClient.calendar.convertBsToAd(normalized)) as CalendarConversion, enabled: /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(normalized), retry: false, staleTime: Infinity });
}
export function HostelBsField({ label, value, onChange, ad, error }: { label: string; value: string; onChange: (value: string) => void; ad?: string; error?: string }) { return <div><HostelField label={label}><Input required maxLength={10} pattern="[0-9०-९]{4}-[0-9०-९]{2}-[0-9०-९]{2}" placeholder="2083-07-09" value={value} onChange={(event) => onChange(event.target.value)} /></HostelField><p className={`mt-1 text-xs ${error ? 'text-destructive' : 'text-muted-foreground'}`}>{error ?? (ad ? `${ad} AD` : 'Enter a valid BS date as YYYY-MM-DD')}</p></div>; }
export const hostelStamp = new Intl.DateTimeFormat('en-NP', { timeZone: 'Asia/Kathmandu', dateStyle: 'medium', timeStyle: 'short' });
export function downloadHostelCsv(blob: Blob, name: string) { const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `hostel-${name}-${nepalDate()}.csv`; link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
