'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { libraryData, librarySelectClass } from '@/lib/api/library';
import type { CopyStatus, LibraryBook, LibraryCopy, LibraryLoan } from '@/lib/api/library';
import { LibraryEmpty, LibraryField, LibraryPagination, LibraryStatus, useLibraryCommand } from './LibraryCommon';
import { LibraryHistory } from './LibraryHistory';

export function AddCopiesForm({ bookId, onClose, onBusy }: { bookId: string; onClose: () => void; onBusy: (busy: boolean) => void }) {
  const [count, setCount] = useState('1');
  const [accessions, setAccessions] = useState('');
  const [notes, setNotes] = useState('');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const change = (update: () => void) => { update(); setRequestId(crypto.randomUUID()); };
  const save = useLibraryCommand(async () => {
    onBusy(true);
    try {
      const identifiers = accessions.split(/\r?\n/).map((value) => value.trim()).filter(Boolean);
      if (!Number.isInteger(Number(count)) || Number(count) < 1 || Number(count) > 500) throw new Error('Choose 1–500 copies');
      if (identifiers.length && identifiers.length !== Number(count)) throw new Error('Enter one accession per copy, or leave all accessions blank');
      return libraryData(await apiClient.library.addCopies(bookId, { count: Number(count), accession_numbers: identifiers.length ? identifiers : null, notes: notes.trim() || null, request_id: requestId }));
    } finally { onBusy(false); }
  }, onClose, 'Accessioned copies added');
  return <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4 rounded-xl border p-4">
    <h3 className="font-semibold">Add physical copies</h3>
    <LibraryField label="Number of copies"><Input type="number" required min={1} max={500} value={count} onChange={(event) => change(() => setCount(event.target.value))} /></LibraryField>
    <LibraryField label="Existing accession numbers (optional, one per line)"><textarea rows={4} className="border p-3" maxLength={25500} value={accessions} onChange={(event) => change(() => setAccessions(event.target.value))} /></LibraryField>
    <p className="text-xs text-muted-foreground">Leave blank to generate unique LIB accession numbers. Existing accession numbers must be unique across your school.</p>
    <LibraryField label="Acquisition notes"><Input maxLength={1000} value={notes} onChange={(event) => change(() => setNotes(event.target.value))} /></LibraryField>
    <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel adding</Button><Button type="submit">{save.isPending ? 'Adding…' : 'Add copies'}</Button></div>
  </fieldset></form>;
}

function CopyStateForm({ copy, onClose, onBusy }: { copy: LibraryCopy; onClose: () => void; onBusy: (busy: boolean) => void }) {
  const [status, setStatus] = useState<CopyStatus>(copy.loan ? 'withdrawn' : copy.status === 'issued' ? 'damaged' : copy.status);
  const [notes, setNotes] = useState('');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const save = useLibraryCommand(async () => {
    onBusy(true);
    try { return libraryData(await apiClient.library.updateCopy(copy.id, { status, notes: notes.trim(), request_id: requestId })); }
    finally { onBusy(false); }
  }, onClose, 'Copy condition updated');
  return <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4 rounded-xl border p-4">
    <h3 className="font-semibold">Update {copy.accession_number}</h3>
    {copy.loan && <p className="text-sm">This copy has a lost loan. Withdraw it to write off stock, or recover it through the original loan before restoring availability.</p>}
    <LibraryField label="Copy condition"><select className={librarySelectClass} value={status} onChange={(event) => { setStatus(event.target.value as CopyStatus); setRequestId(crypto.randomUUID()); }}>{(copy.loan ? ['withdrawn'] : ['available', 'damaged', 'lost', 'withdrawn']).map((value) => <option key={value} value={value}>{value === 'available' ? 'Available / repaired' : value === 'lost' ? 'Lost from shelf' : value === 'withdrawn' ? 'Withdrawn from stock' : 'Damaged / under repair'}</option>)}</select></LibraryField>
    <LibraryField label="Reason"><Input required minLength={3} maxLength={1000} value={notes} onChange={(event) => { setNotes(event.target.value); setRequestId(crypto.randomUUID()); }} /></LibraryField>
    <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel update</Button><Button type="submit">{save.isPending ? 'Saving…' : 'Save condition'}</Button></div>
  </fieldset></form>;
}

export function BookInventoryDialog({ bookId, canEdit, canIssue, onClose, onIssue, onLoan }: { bookId: string; canEdit: boolean; canIssue: boolean; onClose: () => void; onIssue: (book: LibraryBook, copy?: LibraryCopy) => void; onLoan: (loan: LibraryLoan) => void }) {
  const [tab, setTab] = useState('copies');
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const [search, setSearch] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<LibraryCopy | null>(null);
  const [busy, setBusy] = useState(false);
  const book = useQuery({ queryKey: ['library', 'book', bookId], queryFn: async () => libraryData(await apiClient.library.books.get(bookId)) });
  const inventory = useQuery({ queryKey: ['library', 'copies', bookId, page, status, submitted], queryFn: async () => libraryData(await apiClient.library.copies(bookId, { page, status: status || undefined, search: submitted })), enabled: tab === 'copies' });
  return <Dialog open onOpenChange={(open) => !open && !busy && onClose()}><DialogContent className="max-w-4xl"><DialogHeader><DialogTitle>{book.data?.title ?? 'Physical inventory'}</DialogTitle><DialogDescription>Accession-level stock and permanent activity history. Withdrawn copies remain in the register.</DialogDescription></DialogHeader>
    {book.error && <LibraryEmpty error={book.error.message} />}
    {book.data && <p className="mb-4 text-sm text-muted-foreground">{book.data.author} · {book.data.shelf_location || 'Shelf unassigned'} · {book.data.available_copies} on shelf / {book.data.total_copies} in stock{!book.data.is_active && ' · Archived'}{!book.data.is_lendable && ' · Reference-only'}</p>}
    <div className="mb-4 flex gap-2"><Button variant={tab === 'copies' ? 'default' : 'outline'} disabled={busy} onClick={() => setTab('copies')}>Copies</Button><Button variant={tab === 'history' ? 'default' : 'outline'} disabled={busy} onClick={() => setTab('history')}>Activity history</Button>{canEdit && tab === 'copies' && <Button className="ml-auto" variant="outline" disabled={busy} onClick={() => { setAdding(!adding); setEditing(null); }}>{adding ? 'Hide form' : 'Add copies'}</Button>}</div>
    {tab === 'history' ? <LibraryHistory bookId={bookId} /> : <div className="space-y-4">
      {adding && <AddCopiesForm bookId={bookId} onClose={() => setAdding(false)} onBusy={setBusy} />}
      {editing && <CopyStateForm key={editing.id} copy={editing} onClose={() => setEditing(null)} onBusy={setBusy} />}
      <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); setSubmitted(search.trim()); setPage(1); }}><LibraryField label="Accession search"><Input maxLength={50} value={search} onChange={(event) => setSearch(event.target.value)} /></LibraryField><LibraryField label="Stock state"><select className={librarySelectClass} value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">All copies</option>{['available', 'issued', 'damaged', 'lost', 'withdrawn'].map((value) => <option key={value}>{value}</option>)}</select></LibraryField><Button variant="outline" type="submit">Search</Button></form>
      {inventory.isLoading ? <LibraryEmpty>Loading copies…</LibraryEmpty> : inventory.error ? <LibraryEmpty error={inventory.error.message} /> : !inventory.data?.copies.length ? <LibraryEmpty>No copies match these filters.</LibraryEmpty> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-3">Accession</th><th className="p-3">State</th><th className="p-3">Acquired (AD) / notes</th><th className="p-3">Actions</th></tr></thead><tbody>{inventory.data.copies.map((copy) => <tr key={copy.id}><td className="p-3 font-mono text-xs">{copy.accession_number}</td><td className="p-3"><LibraryStatus status={copy.status} /></td><td className="max-w-56 break-words p-3">{copy.acquired_date_ad}<p className="mt-1 text-xs text-muted-foreground">{copy.notes}</p></td><td className="p-3"><div className="flex flex-wrap gap-2">{copy.loan && <Button size="sm" variant="outline" onClick={() => onLoan(copy.loan!)}>View loan</Button>}{canIssue && copy.status === 'available' && book.data?.is_active && book.data.is_lendable && <Button size="sm" disabled={busy} onClick={() => onIssue(book.data!, copy)}>Issue copy</Button>}{canEdit && copy.status !== 'issued' && <Button size="sm" variant="outline" disabled={busy} onClick={() => { setEditing(copy); setAdding(false); }}>Condition</Button>}</div></td></tr>)}</tbody></table></div>}
      {inventory.data && <LibraryPagination page={page} total={inventory.data.total} busy={inventory.isFetching || busy} onPage={setPage} />}
    </div>}
    <DialogFooter><Button variant="outline" disabled={busy} onClick={onClose}>Close inventory</Button></DialogFooter>
  </DialogContent></Dialog>;
}
