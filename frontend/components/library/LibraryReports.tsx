'use client';

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { bookCategories, libraryData } from '@/lib/api/library';
import { money } from '@/lib/api/fees';
import { LibraryEmpty, LibraryStat } from './LibraryCommon';
import { LibraryHistory } from './LibraryHistory';

export function LibraryReports() {
  const stats = useQuery({ queryKey: ['library', 'stats'], queryFn: async () => libraryData(await apiClient.library.stats()) });
  return <div className="space-y-6"><div><h2 className="text-lg font-semibold">Library reports & activity</h2><p className="mt-1 text-sm text-muted-foreground">Whole-school records. Export the filtered catalog or loan register from their respective tabs.</p></div>
    {stats.isLoading ? <LibraryEmpty>Loading reports…</LibraryEmpty> : stats.error ? <LibraryEmpty error={stats.error.message} /> : stats.data && <>
      <div className="pastel-summary grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><LibraryStat label="Registered stock (excludes withdrawn)" value={stats.data.total_copies} /><LibraryStat label="Completed returns / recoveries" value={stats.data.total_returned} /><LibraryStat label="Unresolved lost loans" value={stats.data.lost_loans} /><LibraryStat label="Recorded fine assessments · not collections" value={money(stats.data.assessed_fines)} /></div>
      <div className="grid gap-5 md:grid-cols-2"><section className="rounded-xl border p-5"><h3 className="mb-4 font-semibold">Active titles by category</h3><dl className="space-y-3 text-sm">{Object.entries(bookCategories).map(([key, label]) => <div key={key} className="flex justify-between"><dt>{label}</dt><dd>{stats.data!.categories[key] ?? 0}</dd></div>)}</dl></section><section className="rounded-xl border p-5"><h3 className="mb-4 font-semibold">Physical copy register · all titles</h3><dl className="space-y-3 text-sm">{['available', 'issued', 'damaged', 'lost', 'withdrawn'].map((key) => <div key={key} className="flex justify-between"><dt className="capitalize">{key}</dt><dd>{stats.data!.copy_states[key] ?? 0}</dd></div>)}</dl><p className="mt-4 text-xs text-muted-foreground">Includes archived titles. Withdrawn copies remain in this register for history.</p></section></div>
      <p className="text-xs text-muted-foreground">Recorded assessments include accrued fines carried into renewals. This report does not track collections or outstanding financial balances.</p>
    </>}
    <section className="rounded-xl border p-5"><h3 className="mb-4 font-semibold">Activity history</h3><LibraryHistory /></section>
  </div>;
}
