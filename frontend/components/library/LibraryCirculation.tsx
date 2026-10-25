'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Printer, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { canRenewLoan, dueDate, libraryData, librarySelectClass, openLoan } from '@/lib/api/library';
import type { BorrowerType, LibraryBook, LibraryBorrower, LibraryLoan } from '@/lib/api/library';
import { money, paise } from '@/lib/api/fees';
import { LibraryEmpty, LibraryField, LibraryPagination, LibraryStatus, useLibraryCommand } from './LibraryCommon';
import { LibraryHistory } from './LibraryHistory';

export function BorrowerPicker({ selected, onSelect, disabled = false }: { selected: LibraryBorrower | null; onSelect: (borrower: LibraryBorrower | null) => void; disabled?: boolean }) {
  const [kind, setKind] = useState<BorrowerType>('student');
  const [search, setSearch] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [page, setPage] = useState(1);
  const borrowers = useQuery({ queryKey: ['library', 'borrowers', kind, submitted, page], queryFn: async () => libraryData(await apiClient.library.borrowers({ borrower_type: kind, search: submitted, page })) });
  return <section aria-label="Choose borrower" className="mb-5 space-y-3">
    <form onSubmit={(event) => { event.preventDefault(); setPage(1); setSubmitted(search.trim()); }}><fieldset disabled={disabled} className="flex flex-wrap items-end gap-2">
      <LibraryField label="Borrower type"><select className={librarySelectClass} value={kind} onChange={(event) => { setKind(event.target.value as BorrowerType); setPage(1); onSelect(null); }}><option value="student">Student</option><option value="staff">Staff member</option></select></LibraryField>
      <div className="min-w-40 flex-1"><LibraryField label="Search borrowers"><Input maxLength={200} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Name, admission / EMIS / employee ID" /></LibraryField></div>
      <Button type="submit" variant="outline" disabled={borrowers.isFetching}><Search />Search</Button>
    </fieldset></form>
    {borrowers.isLoading ? <LibraryEmpty>Loading eligible borrowers…</LibraryEmpty> : borrowers.error ? <LibraryEmpty error={borrowers.error.message} /> : !borrowers.data?.borrowers.length ? <LibraryEmpty>No active borrowers match this search.</LibraryEmpty> : <div className="grid max-h-64 gap-2 overflow-y-auto sm:grid-cols-2">{borrowers.data.borrowers.map((borrower) => <button type="button" key={borrower.id} disabled={disabled} aria-pressed={selected?.id === borrower.id && selected?.type === borrower.type} onClick={() => onSelect(borrower)} className={`rounded-lg border p-3 text-left text-sm hover:bg-accent focus-visible:outline-2 focus-visible:outline-ring ${selected?.id === borrower.id && selected.type === borrower.type ? 'border-primary bg-accent' : ''}`}>
      <p className="font-medium">{borrower.name}</p><p className="mt-1 text-xs text-muted-foreground">{borrower.reference || 'No reference recorded'}{borrower.type === 'student' ? ` · Grade ${borrower.grade ?? '—'} ${borrower.section ?? ''}${borrower.roll_number != null ? ` · Roll ${borrower.roll_number}` : ''}` : borrower.designation ? ` · ${borrower.designation}` : ''}</p><p className="mt-1 text-xs">{borrower.active_loans} active loans</p>
    </button>)}</div>}
    {borrowers.data && <LibraryPagination page={page} total={borrowers.data.total} busy={borrowers.isFetching || disabled} onPage={setPage} />}
  </section>;
}

export function IssueBookDialog({ book, copyId, accession, onClose, onLoan }: { book: LibraryBook; copyId?: string; accession?: string; onClose: () => void; onLoan: (loan: LibraryLoan) => void }) {
  const [borrower, setBorrower] = useState<LibraryBorrower | null>(null);
  const [days, setDays] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const policy = useQuery({ queryKey: ['library', 'policy'], queryFn: async () => libraryData(await apiClient.library.policy()) });
  const effectiveDays = days ?? String(policy.data?.loan_days ?? '');
  const maximum = borrower?.type === 'staff' ? policy.data?.staff_limit : policy.data?.student_limit;
  const atLimit = borrower && maximum !== undefined && borrower.active_loans >= maximum;
  const issue = useLibraryCommand(async () => {
    if (!borrower) throw new Error('Select an eligible borrower');
    return libraryData(await apiClient.library.issue({ book_id: book.id, copy_id: copyId, issued_to_id: borrower.id, issued_to_type: borrower.type, due_days: Number(effectiveDays), notes: notes.trim() || null, request_id: requestId }));
  }, (loan) => { onClose(); onLoan(loan); }, 'Book issued and lending slip created');
  const change = (update: () => void) => { update(); setRequestId(crypto.randomUUID()); };
  return <Dialog open onOpenChange={(open) => !open && !issue.isPending && onClose()}><DialogContent className="max-w-3xl">
    <DialogHeader><DialogTitle>Issue a book</DialogTitle><DialogDescription>{book.title} · {accession ?? 'An available copy will be assigned'} · One active copy of a title per borrower.</DialogDescription></DialogHeader>
    <BorrowerPicker selected={borrower} disabled={issue.isPending} onSelect={(next) => change(() => setBorrower(next))} />
    <form onSubmit={(event) => { event.preventDefault(); issue.mutate(); }}><fieldset disabled={issue.isPending} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2"><LibraryField label="Loan period (days)"><Input required type="number" min={1} max={90} value={effectiveDays} onChange={(event) => change(() => setDays(event.target.value))} /></LibraryField><div className="rounded-lg bg-accent/40 p-3 text-sm"><p>Due date (AD)</p><p className="mt-1 font-semibold">{dueDate(Number(effectiveDays)) || 'Choose 1–90 days'}</p></div></div>
      <LibraryField label="Issue notes"><Input maxLength={1000} value={notes} onChange={(event) => change(() => setNotes(event.target.value))} /></LibraryField>
      {borrower && <p className="text-sm">Selected: <strong>{borrower.name}</strong> · {borrower.type} · {borrower.reference || 'No reference'}</p>}
      {atLimit && <p role="alert" className="text-sm text-destructive">The borrower has reached the {maximum}-loan limit. Return a book before issuing another.</p>}
      {policy.error && <LibraryEmpty error={policy.error.message} />}
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!borrower || Boolean(atLimit) || !policy.data || issue.isPending}>{issue.isPending && <Loader2 className="animate-spin" />}Issue book</Button></DialogFooter>
    </fieldset></form>
  </DialogContent></Dialog>;
}

export type LoanAction = 'return' | 'renew' | 'lost';

function LoanActionForm({ loan, action, onClose, onLoan, onBusy }: { loan: LibraryLoan; action: LoanAction; onClose: () => void; onLoan: (loan: LibraryLoan) => void; onBusy: (busy: boolean) => void }) {
  const [condition, setCondition] = useState('good');
  const [fine, setFine] = useState(action === 'lost' ? '0.00' : loan.estimated_fine);
  const [days, setDays] = useState(String(loan.renewal_days));
  const [notes, setNotes] = useState('');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const change = (update: () => void) => { update(); setRequestId(crypto.randomUUID()); };
  const command = useLibraryCommand(async () => {
    onBusy(true);
    try {
    if (action !== 'renew' && !/^\d{1,8}(\.\d{1,2})?$/.test(fine)) throw new Error('Enter an NPR fine with up to two decimal places, or zero');
    const payload = { request_id: requestId, notes: notes.trim() || null };
    if (action === 'renew') return libraryData(await apiClient.library.renew(loan.id, { ...payload, due_days: Number(days) }));
    if (action === 'lost') return libraryData(await apiClient.library.lost(loan.id, { ...payload, fine_amount: fine }));
    return libraryData(await apiClient.library.return({ ...payload, book_issue_id: loan.id, condition, fine_amount: fine }));
    } finally { onBusy(false); }
  }, (result) => { onClose(); onLoan(result); }, action === 'renew' ? 'Loan renewed' : action === 'lost' ? 'Loan marked lost; copy remains unavailable' : 'Return recorded; stock updated');
  const reasonRequired = action === 'lost' || (action === 'return' && (condition === 'damaged' || paise(fine) > BigInt(0) || paise(fine) !== paise(loan.estimated_fine)));
  return <form onSubmit={(event) => { event.preventDefault(); command.mutate(); }}><fieldset disabled={command.isPending} className="space-y-4">
    <div className="rounded-xl bg-accent/40 p-4 text-sm"><p className="font-semibold">{loan.book_title} · {loan.accession_number ?? 'Legacy copy'}</p><p className="mt-1">{loan.borrower_name} · {loan.borrower_reference ?? loan.issued_to_type}</p><p className="mt-1">Due {loan.due_date_bs} BS · {loan.due_date_ad} AD</p></div>
    {action === 'renew' ? <><LibraryField label="Extend loan by days"><Input required type="number" min={1} max={90} value={days} onChange={(event) => change(() => setDays(event.target.value))} /></LibraryField><p className="text-sm">Renewals used: {loan.renewal_count} / {loan.max_renewals}. {paise(loan.estimated_fine) > BigInt(0) && `Accrued assessment of ${money(loan.estimated_fine)} is retained.`}</p></> : <>
      {action === 'return' && <LibraryField label="Returned condition"><select className={librarySelectClass} value={condition} onChange={(event) => change(() => setCondition(event.target.value))}><option value="good">Good — available for borrowing</option><option value="damaged">Damaged — hold for repair</option></select></LibraryField>}
      <LibraryField label="Assessed fine (NPR)"><Input required inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" value={fine} onChange={(event) => change(() => setFine(event.target.value))} /></LibraryField>
      <p className="text-xs leading-5 text-muted-foreground">This records an assessment, not a payment. {action === 'return' && `The loan’s policy suggests ${money(loan.estimated_fine)}. `}Enter zero to waive; explain any waiver or nonzero assessment. Payment collection remains in Fees & Payments.</p>
    </>}
    <LibraryField label={reasonRequired ? 'Reason / notes (required)' : 'Notes'}><Input required={reasonRequired} minLength={reasonRequired ? 3 : undefined} maxLength={1000} value={notes} onChange={(event) => change(() => setNotes(event.target.value))} /></LibraryField>
    <DialogFooter><Button type="button" variant="outline" disabled={command.isPending} onClick={onClose}>Cancel</Button><Button type="submit">{command.isPending && <Loader2 className="animate-spin" />}{action === 'renew' ? 'Renew loan' : action === 'lost' ? 'Mark lost' : loan.status === 'lost' ? 'Recover copy' : 'Record return'}</Button></DialogFooter>
  </fieldset></form>;
}

export function LoanActionDialog({ loanId, action, onClose, onLoan }: { loanId: string; action: LoanAction; onClose: () => void; onLoan: (loan: LibraryLoan) => void }) {
  const [pending, setPending] = useState(false);
  const loan = useQuery({ queryKey: ['library', 'loan', loanId], queryFn: async () => libraryData(await apiClient.library.loan(loanId)), staleTime: 0, refetchOnMount: 'always' });
  return <Dialog open onOpenChange={(open) => !open && !pending && onClose()}><DialogContent className="max-w-lg"><DialogHeader><DialogTitle>{action === 'renew' ? 'Renew library loan' : action === 'lost' ? 'Record a lost book' : 'Return / recover library copy'}</DialogTitle><DialogDescription>Review the current loan before recording this action. History is retained.</DialogDescription></DialogHeader>
    {loan.isFetching ? <LibraryEmpty>Loading the current loan…</LibraryEmpty> : loan.error ? <LibraryEmpty error={loan.error.message} /> : loan.data && <LoanActionForm loan={loan.data} action={action} onClose={onClose} onLoan={onLoan} onBusy={setPending} />}
  </DialogContent></Dialog>;
}

export function LoanDetailsDialog({ loan, canIssue, canReturn, onClose, onAction }: { loan: LibraryLoan; canIssue: boolean; canReturn: boolean; onClose: () => void; onAction: (action: LoanAction, loan: LibraryLoan) => void }) {
  const [history, setHistory] = useState(false);
  return <Dialog open onOpenChange={(open) => !open && onClose()}><DialogContent className="max-w-2xl">
    <DialogHeader><DialogTitle>Library lending record</DialogTitle><DialogDescription>Accession, borrower, due dates, assessments and recorded activity.</DialogDescription></DialogHeader>
    <section id="library-slip" className="space-y-4 rounded-xl border p-5 text-sm">
      <header className="border-b pb-4"><h2 className="text-lg font-semibold">School library · Lending slip</h2><p className="mt-1 font-mono text-xs">{loan.accession_number ?? 'Legacy copy not recorded'}</p></header>
      <h3 className="text-lg font-semibold">{loan.book_title}</h3>
      <dl className="grid gap-4 sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">Borrower at issuance</dt><dd className="mt-1 font-medium">{loan.borrower_name}</dd></div><div><dt className="text-xs text-muted-foreground">Reference / class at issuance</dt><dd className="mt-1">{loan.borrower_reference ?? 'Not recorded'} · {loan.issued_to_type}</dd></div><div><dt className="text-xs text-muted-foreground">Issued</dt><dd className="mt-1">{loan.issue_date_bs} BS<br />{loan.issue_date_ad} AD</dd></div><div><dt className="text-xs text-muted-foreground">Due</dt><dd className="mt-1 font-semibold">{loan.due_date_bs} BS<br />{loan.due_date_ad} AD</dd></div>{loan.return_date_ad && <div><dt className="text-xs text-muted-foreground">Returned / recovered</dt><dd className="mt-1">{loan.return_date_bs} BS · {loan.return_date_ad} AD</dd></div>}<div><dt className="text-xs text-muted-foreground">Status</dt><dd className="mt-1"><LibraryStatus status={loan.status} /></dd></div><div><dt className="text-xs text-muted-foreground">Renewals</dt><dd className="mt-1">{loan.renewal_count} / {loan.max_renewals}</dd></div><div><dt className="text-xs text-muted-foreground">Recorded fine assessment</dt><dd className="mt-1">{money(loan.fine_amount)} · Not a payment</dd></div></dl>
      {loan.notes && <p className="border-t pt-4">Notes: {loan.notes}</p>}
    </section>
    <div className="mt-4 flex flex-wrap gap-2">{canReturn && (openLoan(loan) || loan.status === 'lost') && <Button onClick={() => onAction('return', loan)}>{loan.status === 'lost' ? 'Recover copy' : 'Return book'}</Button>}{canIssue && canRenewLoan(loan) && <Button variant="outline" onClick={() => onAction('renew', loan)}>Renew</Button>}{canReturn && openLoan(loan) && <Button variant="outline" onClick={() => onAction('lost', loan)}>Mark lost</Button>}<Button variant="outline" onClick={() => setHistory((value) => !value)}>{history ? 'Hide history' : 'View history'}</Button></div>
    {history && <LibraryHistory issueId={loan.id} />}
    <DialogFooter><Button variant="outline" onClick={onClose}>Close</Button><Button onClick={() => window.print()}><Printer />Print lending slip</Button></DialogFooter>
  </DialogContent></Dialog>;
}
