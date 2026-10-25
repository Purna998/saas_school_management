'use client';

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FeeCollectionChart } from '@/app/dashboard/DashboardChartLoaders';
import { apiClient } from '@/lib/api/client';
import { academicYear, feeData, money } from '@/lib/api/fees';
import { useAuthStore } from '@/lib/store/auth';
import { FeeEmpty } from './FeeDialogs';

export function useCurrentFeeSummary() {
  const user = useAuthStore((state) => state.user);
  const has = (code: string) => Boolean(user?.permissions?.includes(code) || user?.permissions?.includes('*:*'));
  const allowed = has('fee:read') && has('fee:report');
  const calendar = useQuery({ queryKey: ['calendar', 'current-bs'], enabled: allowed,
    queryFn: async () => feeData(await apiClient.calendar.getCurrentBs()) as { bs_date: { year: number } } });
  const year = calendar.data?.bs_date.year ? academicYear(String(calendar.data.bs_date.year)) : '';
  const summary = useQuery({ queryKey: ['fees', 'summary', year], enabled: allowed && Boolean(year), queryFn: async () => feeData(await apiClient.fees.summary(year)) });
  return { allowed, year, data: summary.data, error: calendar.error ?? summary.error };
}

export function FeeOverviewCard({ state }: { state: ReturnType<typeof useCurrentFeeSummary> }) {
  return <Card><CardHeader><CardTitle>Fee Collection</CardTitle><p className="text-xs text-muted-foreground">Live school records {state.year && `· ${state.year} BS`} · Net of refunds</p></CardHeader><CardContent>
    {!state.allowed ? <FeeEmpty>Fee report access is required to view financial totals.</FeeEmpty> : state.error ? <FeeEmpty error={state.error.message} /> : !state.data ? <FeeEmpty>Loading fee totals…</FeeEmpty> : <><FeeCollectionChart data={[{ name: 'Collected', value: Number(state.data.total_collected) }, { name: 'Pending', value: Number(state.data.total_pending) }]} /><div className="mt-1 flex justify-center gap-6 text-xs"><span className="flex items-center gap-2"><span className="size-2.5 rounded-full bg-primary" />Collected</span><span className="flex items-center gap-2"><span className="size-2.5 rounded-full bg-[#ffa365]" />Pending</span></div><div className="mt-5 grid grid-cols-2 divide-x border-t pt-4 text-center"><div><p className="text-[10px] text-muted-foreground">Net collected</p><p className="mt-1 text-sm font-semibold">{money(state.data.total_collected)}</p></div><div><p className="text-[10px] text-muted-foreground">Outstanding</p><p className="mt-1 text-sm font-semibold">{money(state.data.total_pending)}</p></div></div></>}
  </CardContent></Card>;
}
