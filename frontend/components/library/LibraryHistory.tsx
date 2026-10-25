'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { libraryData } from '@/lib/api/library';
import { LibraryEmpty, LibraryPagination } from './LibraryCommon';

const actionLabels: Record<string, string> = { book_added: 'Title added', book_updated: 'Catalog updated', copies_added: 'Copies accessioned', copy_updated: 'Copy state changed', issued: 'Book issued', returned: 'Book returned / recovered', renewed: 'Loan renewed', lost: 'Loan marked lost', policy_updated: 'Lending policy updated' };
const visibleFields: Record<string, string> = { title: 'Title', author: 'Author', isbn: 'ISBN', category: 'Category', publisher: 'Publisher', edition: 'Edition', language: 'Language', reading_level: 'Reading level', shelf_location: 'Shelf', is_active: 'Active title', is_lendable: 'Lendable', status: 'Status', copy_status: 'Copy state', accession_number: 'Accession', due_date_ad: 'Due date (AD)', fine_amount: 'Fine assessment (NPR)', renewal_count: 'Renewals', copies_added: 'Copies added', borrower_name: 'Borrower', daily_fine: 'Daily fine (NPR)', fine_cap: 'Fine cap (NPR)', loan_days: 'Loan days', student_limit: 'Student limit', staff_limit: 'Staff limit', max_renewals: 'Renewal limit', renewal_days: 'Renewal days', allow_overdue_renewal: 'Overdue renewal' };
const displayValue = (value: unknown) => typeof value === 'boolean' ? value ? 'Yes' : 'No' : String(value ?? '—');
const stamp = new Intl.DateTimeFormat('en-NP', { timeZone: 'Asia/Kathmandu', dateStyle: 'medium', timeStyle: 'short' });

export function LibraryHistory({ bookId, issueId }: { bookId?: string; issueId?: string }) {
  const [page, setPage] = useState(1);
  const history = useQuery({ queryKey: ['library', 'history', bookId, issueId, page], queryFn: async () => libraryData(await apiClient.library.history({ book_id: bookId, issue_id: issueId, page })) });
  if (history.isLoading) return <LibraryEmpty>Loading activity history…</LibraryEmpty>;
  if (history.error) return <LibraryEmpty error={history.error.message} />;
  return <section aria-label="Library activity history">
    {!history.data?.events.length ? <LibraryEmpty>No recorded events for this selection.</LibraryEmpty> : <ol className="space-y-3">{history.data.events.map((event) => <li key={event.id} className="rounded-xl border p-4 text-sm">
      <div className="flex flex-wrap justify-between gap-2"><strong>{actionLabels[event.action] ?? event.action.replaceAll('_', ' ')}</strong><span className="text-xs text-muted-foreground">{stamp.format(new Date(event.created_at))} NPT</span></div>
      <p className="mt-1 text-xs text-muted-foreground">Recorded by {event.actor_name ?? 'authorized library staff'}</p>
      {event.notes && <p className="mt-2 whitespace-pre-wrap">{event.notes}</p>}
      <dl className="mt-2 space-y-1">{Object.entries(event.after).filter(([field]) => visibleFields[field]).map(([field, value]) => <div key={field} className="flex flex-wrap gap-2"><dt className="text-muted-foreground">{visibleFields[field]}:</dt><dd>{field in event.before && <span className="text-muted-foreground">{displayValue(event.before[field])} → </span>}{displayValue(value)}</dd></div>)}</dl>
      {Array.isArray(event.after.accessions) && <p className="mt-2 break-words font-mono text-xs">{event.after.accessions.slice(0, 20).join(', ')}{event.after.accessions.length > 20 ? ` · ${event.after.accessions.length - 20} more in inventory` : ''}</p>}
    </li>)}</ol>}
    {history.data && <LibraryPagination page={page} total={history.data.total} busy={history.isFetching} onPage={setPage} />}
  </section>;
}
