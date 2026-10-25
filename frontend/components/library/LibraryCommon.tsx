'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';

export function LibraryField({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-1.5 text-sm"><span className="font-medium">{label}</span>{children}</label>;
}

export function LibraryEmpty({ error, children }: { error?: string; children?: React.ReactNode }) {
  return <div role={error ? 'alert' : undefined} className={`py-10 text-center text-sm ${error ? 'text-destructive' : 'text-muted-foreground'}`}>{error ?? children}</div>;
}

export function LibraryStat({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-xl border bg-muted/30 p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-xl font-semibold">{value}</p></div>;
}

export function LibraryStatus({ status }: { status: string }) {
  const tone = ['available', 'returned'].includes(status) ? 'bg-emerald-50 text-emerald-700' : ['lost', 'overdue'].includes(status) ? 'bg-red-50 text-red-700' : ['damaged', 'withdrawn'].includes(status) ? 'bg-amber-50 text-amber-800' : 'bg-accent text-primary';
  return <span className={`inline-block rounded-full px-2.5 py-1 text-xs capitalize ${tone}`}>{status}</span>;
}

export function LibraryPagination({ page, total, busy, onPage }: { page: number; total: number; busy: boolean; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / 20));
  return <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t pt-4 text-sm"><p className="text-muted-foreground">{total} records · Page {page} of {pages}</p><div className="flex gap-2"><Button variant="outline" size="sm" disabled={page <= 1 || busy} onClick={() => onPage(page - 1)}>Previous</Button><Button variant="outline" size="sm" disabled={page >= pages || busy} onClick={() => onPage(page + 1)}>Next</Button></div></div>;
}

export function useLibraryCommand<T>(execute: () => Promise<T>, onSuccess: (data: T) => void, message: string) {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: execute, onSuccess: async (data) => {
    toast.success(message); onSuccess(data);
    await queryClient.invalidateQueries({ queryKey: ['library'] });
  }, onError: (error) => toast.error(error.message) });
}
