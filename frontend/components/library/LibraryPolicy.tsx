'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api/client';
import { libraryData } from '@/lib/api/library';
import type { LibraryPolicy as Policy } from '@/lib/api/library';
import { LibraryEmpty, LibraryField, useLibraryCommand } from './LibraryCommon';

function PolicyForm({ policy, canEdit }: { policy: Policy; canEdit: boolean }) {
  const [draft, setDraft] = useState(policy);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const change = (patch: Partial<Policy>) => { setDraft((value) => ({ ...value, ...patch })); setRequestId(crypto.randomUUID()); };
  const save = useLibraryCommand(async () => libraryData(await apiClient.library.updatePolicy({ ...draft, request_id: requestId })), () => {}, 'Lending rules saved for future loans');
  const numbers: { field: 'loan_days' | 'student_limit' | 'staff_limit' | 'renewal_days' | 'max_renewals'; label: string; min: number; max: number }[] = [
    { field: 'loan_days', label: 'Default loan period (days)', min: 1, max: 90 }, { field: 'student_limit', label: 'Maximum active loans per student', min: 1, max: 100 }, { field: 'staff_limit', label: 'Maximum active loans per staff member', min: 1, max: 100 }, { field: 'renewal_days', label: 'Default renewal extension (days)', min: 1, max: 90 }, { field: 'max_renewals', label: 'Maximum renewals per loan', min: 0, max: 10 },
  ];
  return <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={!canEdit || save.isPending} className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2">{numbers.map((item) => <LibraryField key={item.field} label={item.label}><Input required type="number" min={item.min} max={item.max} value={Number.isNaN(draft[item.field]) ? '' : draft[item.field]} onChange={(event) => change({ [item.field]: event.target.value === '' ? NaN : Number(event.target.value) })} /></LibraryField>)}</div>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.allow_overdue_renewal} onChange={(event) => change({ allow_overdue_renewal: event.target.checked })} />Permit renewal of overdue loans</label>
    <div className="grid gap-4 sm:grid-cols-2"><LibraryField label="Suggested daily late fine (NPR)"><Input required pattern="[0-9]+(\.[0-9]{1,2})?" inputMode="decimal" value={draft.daily_fine} onChange={(event) => change({ daily_fine: event.target.value })} /></LibraryField><LibraryField label="Maximum suggested late fine per loan (NPR)"><Input required pattern="[0-9]+(\.[0-9]{1,2})?" inputMode="decimal" value={draft.fine_cap} onChange={(event) => change({ fine_cap: event.target.value })} /></LibraryField></div>
    <p className="rounded-lg bg-accent/40 p-4 text-sm leading-6">Late fine suggestions are disabled when the daily rate is zero. A positive rate requires a positive cap. Each loan keeps the renewal and fine rules from its issue date. Borrower limits use the current school policy. Return staff can assess or waive fines with a reason. These assessments do not create fee charges or collect money.</p>
    {canEdit && <Button type="submit">{save.isPending ? 'Saving…' : 'Save lending rules'}</Button>}
  </fieldset></form>;
}

export function LibraryPolicy({ canEdit }: { canEdit: boolean }) {
  const policy = useQuery({ queryKey: ['library', 'policy'], queryFn: async () => libraryData(await apiClient.library.policy()) });
  return <section className="space-y-5"><div><h2 className="text-lg font-semibold">Lending rules</h2><p className="mt-1 text-sm text-muted-foreground">School policy for new issues. {canEdit ? 'Changes are recorded in activity history.' : 'Your account has read-only access.'}</p></div>{policy.isLoading ? <LibraryEmpty>Loading lending rules…</LibraryEmpty> : policy.error ? <LibraryEmpty error={policy.error.message} /> : policy.data && <PolicyForm key={JSON.stringify(policy.data)} policy={policy.data} canEdit={canEdit} />}</section>;
}
