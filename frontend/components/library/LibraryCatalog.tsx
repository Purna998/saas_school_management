'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, Plus, Search } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api/client';
import { bookCategories, downloadLibraryReport, libraryData, librarySelectClass } from '@/lib/api/library';
import type { LibraryBook } from '@/lib/api/library';
import { LibraryEmpty, LibraryField, LibraryPagination, useLibraryCommand } from './LibraryCommon';

export function LibraryCatalog({ canCreate, canEdit, canIssue, privateAccess, onEdit, onInventory, onIssue }: { canCreate: boolean; canEdit: boolean; canIssue: boolean; privateAccess: boolean; onEdit: (book?: LibraryBook) => void; onInventory: (bookId: string) => void; onIssue: (book: LibraryBook) => void }) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [submitted, setSubmitted] = useState('');
  const [category, setCategory] = useState('');
  const [active, setActive] = useState('true');
  const [available, setAvailable] = useState(false);
  const [exporting, setExporting] = useState(false);
  const filters = { search: submitted, category: category || undefined, is_active: active === 'true', available_only: available };
  const books = useQuery({ queryKey: ['library', 'books', filters, page], queryFn: async () => libraryData(await apiClient.library.books.list({ ...filters, page })) });
  const [archive, setArchive] = useState<{ book: LibraryBook; requestId: string } | null>(null);
  const archiveBook = useLibraryCommand(async () => {
    if (!archive) throw new Error('Choose a title');
    return libraryData(await apiClient.library.books.update(archive.book.id, { is_active: !archive.book.is_active, request_id: archive.requestId }));
  }, () => setArchive(null), 'Catalog status updated; stock and loans retained');
  const exportCatalog = async () => { setExporting(true); try { downloadLibraryReport(libraryData(await apiClient.library.export({ ...filters, report: 'catalog' })), 'catalog'); } catch (error) { toast.error((error as Error).message); } finally { setExporting(false); } };
  return <div className="space-y-5">
    <div className="flex flex-wrap justify-between gap-3"><div><h2 className="text-lg font-semibold">Book catalog</h2><p className="mt-1 text-sm text-muted-foreground">Search titles, authors, ISBNs, and accession numbers.</p></div><div className="flex gap-2">{privateAccess && <Button variant="outline" disabled={exporting} onClick={exportCatalog}><Download />{exporting ? 'Exporting…' : 'Export catalog'}</Button>}{canCreate && <Button onClick={() => onEdit()}><Plus />Add title</Button>}</div></div>
    <form className="flex flex-wrap items-end gap-3 rounded-xl border p-4" onSubmit={(event) => { event.preventDefault(); setSubmitted(search.trim()); setPage(1); }}>
      <div className="min-w-48 flex-1"><LibraryField label="Search catalog"><Input maxLength={300} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Title, author, ISBN, accession" /></LibraryField></div>
      <LibraryField label="Category"><select className={librarySelectClass} value={category} onChange={(event) => { setCategory(event.target.value); setPage(1); }}><option value="">All categories</option>{Object.entries(bookCategories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></LibraryField>
      <LibraryField label="Catalog status"><select className={librarySelectClass} value={active} onChange={(event) => { setActive(event.target.value); setPage(1); }}><option value="true">Active titles</option><option value="false">Archived titles</option></select></LibraryField>
      <label className="flex min-h-10 items-center gap-2 text-sm"><input type="checkbox" checked={available} onChange={(event) => { setAvailable(event.target.checked); setPage(1); }} />Available to borrow</label><Button type="submit" variant="outline"><Search />Search</Button>
    </form>
    {archive && <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-accent/40 p-4 text-sm"><p>{archive.book.is_active ? 'Archive' : 'Restore'} <strong>{archive.book.title}</strong>? Existing loans and history are retained.</p><div className="flex gap-2"><Button variant="outline" disabled={archiveBook.isPending} onClick={() => setArchive(null)}>Cancel</Button><Button disabled={archiveBook.isPending} onClick={() => archiveBook.mutate()}>{archiveBook.isPending ? 'Saving…' : 'Confirm status change'}</Button></div></div>}
    {books.isLoading ? <LibraryEmpty>Loading catalog…</LibraryEmpty> : books.error ? <LibraryEmpty error={books.error.message} /> : !books.data?.books.length ? <LibraryEmpty>No titles match these filters.{canCreate && ' Add a title to begin your school catalog.'}</LibraryEmpty> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-3">Title / author</th><th className="p-3">Classification</th><th className="p-3">Shelf / stock</th><th className="p-3">Actions</th></tr></thead><tbody>{books.data.books.map((book) => <tr key={book.id}>
      <td className="min-w-48 max-w-80 break-words p-3"><p className="font-semibold">{book.title}</p><p className="mt-1 text-muted-foreground">{book.author}</p><p className="mt-1 text-xs text-muted-foreground">{book.isbn ? `ISBN ${book.isbn}` : 'No ISBN'}{book.edition && ` · ${book.edition}`}{book.publisher && ` · ${book.publisher}`}</p></td>
      <td className="p-3"><p>{bookCategories[book.category]}</p><p className="mt-1 text-xs text-muted-foreground">{[book.language, book.reading_level].filter(Boolean).join(' · ') || 'Reading level unassigned'}</p>{!book.is_lendable && <span className="mt-2 inline-block rounded-full bg-amber-50 px-2 py-1 text-xs text-amber-800">Reference-only</span>}</td>
      <td className="p-3"><p>{book.shelf_location || 'Unassigned'}</p><p className="mt-1 text-xs">{book.available_copies} on shelf / {book.total_copies} in stock</p>{!book.is_active && <p className="mt-1 text-xs text-muted-foreground">Archived</p>}</td>
      <td className="p-3"><div className="flex max-w-72 flex-wrap gap-2">{privateAccess && <Button size="sm" variant="outline" onClick={() => onInventory(book.id)}>Copies & history</Button>}{canIssue && book.is_active && book.is_lendable && book.available_copies > 0 && <Button size="sm" onClick={() => onIssue(book)}>Issue</Button>}{canEdit && <><Button size="sm" variant="outline" onClick={() => onEdit(book)}>Edit</Button><Button size="sm" variant="ghost" disabled={archiveBook.isPending} onClick={() => setArchive({ book, requestId: crypto.randomUUID() })}>{book.is_active ? 'Archive' : 'Restore'}</Button></>}</div></td>
    </tr>)}</tbody></table></div>}
    {books.data && <LibraryPagination page={page} total={books.data.total} busy={books.isFetching} onPage={setPage} />}
    <p className="text-xs text-muted-foreground">Stock includes issued, damaged and lost copies; withdrawn copies are excluded. On-shelf reference copies cannot be borrowed.</p>
  </div>;
}
