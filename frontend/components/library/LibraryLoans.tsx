'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Search } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api/client';
import { canRenewLoan, downloadLibraryReport, libraryData, librarySelectClass, openLoan } from '@/lib/api/library';
import type { LibraryLoan } from '@/lib/api/library';
import { money } from '@/lib/api/fees';
import { LibraryEmpty, LibraryField, LibraryPagination, LibraryStatus } from './LibraryCommon';
import type { LoanAction } from './LibraryCirculation';

export function LibraryLoans({ canIssue, canReturn, initialStatus = 'active', onLoan, onAction }: { canIssue: boolean; canReturn: boolean; initialStatus?: string; onLoan: (loan: LibraryLoan) => void; onAction: (action: LoanAction, loan: LibraryLoan) => void }) {
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState({ search: '', status: initialStatus, borrower_type: '', start_date: '', end_date: '' });
  const [filters, setFilters] = useState(draft);
  const [exporting, setExporting] = useState(false);
  const params = { search: filters.search, status: filters.status || undefined, borrower_type: filters.borrower_type || undefined, start_date: filters.start_date || undefined, end_date: filters.end_date || undefined };
  const loans = useQuery({ queryKey: ['library', 'loans', params, page], queryFn: async () => libraryData(await apiClient.library.loans({ ...params, page })) });
  const exportLoans = async () => { setExporting(true); try { downloadLibraryReport(libraryData(await apiClient.library.export({ ...params, report: 'loans' })), 'loans'); } catch (error) { toast.error((error as Error).message); } finally { setExporting(false); } };
  return <div className="space-y-5"><div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-lg font-semibold">Loan register</h2><p className="mt-1 text-sm text-muted-foreground">Student and staff loans, overdue items, returns and lost copies.</p></div><Button variant="outline" disabled={exporting} onClick={exportLoans}><Download />{exporting ? 'Exporting…' : 'Export filtered loans'}</Button></div>
    <form className="flex flex-wrap items-end gap-3 rounded-xl border p-4" onSubmit={(event) => { event.preventDefault(); if (draft.start_date && draft.end_date && draft.start_date > draft.end_date) { toast.error('The end date must be on or after the start date'); return; } setFilters({ ...draft, search: draft.search.trim() }); setPage(1); }}>
      <div className="min-w-48 flex-1"><LibraryField label="Search loans"><Input maxLength={300} value={draft.search} onChange={(event) => setDraft({ ...draft, search: event.target.value })} placeholder="Borrower, reference, title, accession" /></LibraryField></div>
      <LibraryField label="Loan status"><select className={librarySelectClass} value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}>{[['active', 'Active loans'], ['overdue', 'Overdue'], ['issued', 'Issued, not overdue'], ['returned', 'Returned'], ['lost', 'Lost'], ['', 'All history']].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></LibraryField>
      <LibraryField label="Borrower type"><select className={librarySelectClass} value={draft.borrower_type} onChange={(event) => setDraft({ ...draft, borrower_type: event.target.value })}><option value="">Students & staff</option><option value="student">Students</option><option value="staff">Staff</option></select></LibraryField>
      <LibraryField label="Issued from (AD)"><Input type="date" value={draft.start_date} onChange={(event) => setDraft({ ...draft, start_date: event.target.value })} /></LibraryField><LibraryField label="Issued through (AD)"><Input type="date" min={draft.start_date || undefined} value={draft.end_date} onChange={(event) => setDraft({ ...draft, end_date: event.target.value })} /></LibraryField><Button type="submit" variant="outline"><Search />Apply filters</Button>
    </form>
    {loans.isLoading ? <LibraryEmpty>Loading loans…</LibraryEmpty> : loans.error ? <LibraryEmpty error={loans.error.message} /> : !loans.data?.issues.length ? <LibraryEmpty>No loans match the applied filters.</LibraryEmpty> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-3">Book / accession</th><th className="p-3">Borrower at issuance</th><th className="p-3">Due date</th><th className="p-3">Status / assessment</th><th className="p-3">Actions</th></tr></thead><tbody>{loans.data.issues.map((loan) => <tr key={loan.id}>
      <td className="min-w-44 max-w-72 break-words p-3"><p className="font-medium">{loan.book_title}</p><p className="mt-1 font-mono text-xs text-muted-foreground">{loan.accession_number ?? 'Legacy copy unknown'}</p></td><td className="min-w-40 p-3"><p>{loan.borrower_name}</p><p className="mt-1 text-xs text-muted-foreground">{loan.borrower_reference || 'No reference'} · {loan.issued_to_type}</p></td>
      <td className="whitespace-nowrap p-3"><p>{loan.due_date_bs} BS</p><p className="mt-1 text-xs text-muted-foreground">{loan.due_date_ad} AD</p>{loan.overdue_days > 0 && <p className="mt-1 text-xs text-red-700">{loan.overdue_days} days overdue</p>}</td>
      <td className="p-3"><LibraryStatus status={loan.status} /><p className="mt-2 text-xs">{money(openLoan(loan) ? loan.estimated_fine : loan.fine_amount)} {openLoan(loan) ? 'suggested' : 'recorded'}</p><p className="mt-1 text-xs text-muted-foreground">Renewals {loan.renewal_count}/{loan.max_renewals}</p></td>
      <td className="p-3"><div className="flex max-w-64 flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => onLoan(loan)}>Lending slip</Button>{canReturn && (openLoan(loan) || loan.status === 'lost') && <Button size="sm" onClick={() => onAction('return', loan)}>{loan.status === 'lost' ? 'Recover' : 'Return'}</Button>}{canIssue && canRenewLoan(loan) && <Button size="sm" variant="outline" onClick={() => onAction('renew', loan)}>Renew</Button>}{canReturn && openLoan(loan) && <Button size="sm" variant="ghost" onClick={() => onAction('lost', loan)}>Mark lost</Button>}</div></td>
    </tr>)}</tbody></table></div>}
    {loans.data && <LibraryPagination page={page} total={loans.data.total} busy={loans.isFetching} onPage={setPage} />}
    <p className="text-xs text-muted-foreground">Exports use the applied filters and include every matching row, up to 50,000. Fine assessments are not payment records.</p>
  </div>;
}
