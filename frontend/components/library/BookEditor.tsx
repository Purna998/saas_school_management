'use client';

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { bookCategories, libraryData, librarySelectClass } from '@/lib/api/library';
import type { BookCategory, LibraryBook } from '@/lib/api/library';
import { LibraryField, useLibraryCommand } from './LibraryCommon';

export function BookEditor({ book, onClose }: { book?: LibraryBook; onClose: () => void }) {
  const [draft, setDraft] = useState({ title: book?.title ?? '', author: book?.author ?? '', isbn: book?.isbn ?? '',
    publisher: book?.publisher ?? '', edition: book?.edition ?? '', category: book?.category ?? 'textbook' as BookCategory,
    shelf_location: book?.shelf_location ?? '', language: book?.language ?? '', reading_level: book?.reading_level ?? '', is_lendable: book?.is_lendable ?? true });
  const [count, setCount] = useState('1');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const change = (next: Partial<typeof draft>) => { setDraft((current) => ({ ...current, ...next })); setRequestId(crypto.randomUUID()); };
  const save = useLibraryCommand(async () => {
    if (!book && (!Number.isInteger(Number(count)) || Number(count) < 1 || Number(count) > 500)) throw new Error('Add from 1 to 500 initial copies');
    const payload = { ...draft, isbn: draft.isbn.trim() || null, publisher: draft.publisher.trim() || null,
      edition: draft.edition.trim() || null, shelf_location: draft.shelf_location.trim() || null,
      language: draft.language.trim() || null, reading_level: draft.reading_level.trim() || null, request_id: requestId };
    return book ? libraryData(await apiClient.library.books.update(book.id, payload)) : libraryData(await apiClient.library.books.create({ ...payload, total_copies: Number(count) }));
  }, onClose, book ? 'Catalog entry updated' : 'Title and accessioned copies added');

  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent className="max-w-3xl">
    <DialogHeader><DialogTitle>{book ? 'Edit catalog entry' : 'Add a library title'}</DialogTitle><DialogDescription>{book ? 'Existing loan slips retain their original title and borrower details. Manage physical stock through Copies & history.' : 'Use Add copies on an existing title for extra physical copies. ISBN is optional, but must be valid when supplied.'}</DialogDescription></DialogHeader>
    <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4">
      <LibraryField label="Title"><Input required maxLength={300} value={draft.title} onChange={(event) => change({ title: event.target.value })} /></LibraryField>
      <div className="grid gap-4 sm:grid-cols-2">
        <LibraryField label="Author / responsible organization"><Input required maxLength={200} value={draft.author} onChange={(event) => change({ author: event.target.value })} /></LibraryField>
        <LibraryField label="ISBN (optional)"><Input maxLength={30} value={draft.isbn} onChange={(event) => change({ isbn: event.target.value })} placeholder="ISBN-10 or ISBN-13" /></LibraryField>
        <LibraryField label="Category"><select className={librarySelectClass} value={draft.category} onChange={(event) => { const category = event.target.value as BookCategory; change({ category, is_lendable: !['reference', 'newspaper'].includes(category) }); }}>{Object.entries(bookCategories).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></LibraryField>
        <LibraryField label="Shelf location"><Input maxLength={50} value={draft.shelf_location} onChange={(event) => change({ shelf_location: event.target.value })} placeholder="A-02 / Children’s section" /></LibraryField>
        <LibraryField label="Publisher"><Input maxLength={200} value={draft.publisher} onChange={(event) => change({ publisher: event.target.value })} /></LibraryField>
        <LibraryField label="Edition"><Input maxLength={50} value={draft.edition} onChange={(event) => change({ edition: event.target.value })} /></LibraryField>
        <LibraryField label="Language"><Input maxLength={50} list="library-languages" value={draft.language} onChange={(event) => change({ language: event.target.value })} /><datalist id="library-languages"><option value="नेपाली" /><option value="English" /><option value="Bilingual" /></datalist></LibraryField>
        <LibraryField label="Reading level"><Input maxLength={50} list="library-reading-levels" value={draft.reading_level} onChange={(event) => change({ reading_level: event.target.value })} /><datalist id="library-reading-levels">{['Nursery–UKG', 'Grades 1–3', 'Grades 4–5', 'Grades 6–8', 'Grades 9–10', 'Grades 11–12', 'All readers'].map((level) => <option key={level} value={level} />)}</datalist></LibraryField>
        {!book && <LibraryField label="Initial copies"><Input required type="number" min={1} max={500} value={count} onChange={(event) => { setCount(event.target.value); setRequestId(crypto.randomUUID()); }} /></LibraryField>}
      </div>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={draft.is_lendable} onChange={(event) => change({ is_lendable: event.target.checked })} />Allow borrowing outside the library</label>
      {!draft.is_lendable && <p className="text-xs text-muted-foreground">Reference-only: copies remain on shelf and cannot be issued.</p>}
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit">{save.isPending && <Loader2 className="animate-spin" />}{book ? 'Save catalog entry' : 'Add title & copies'}</Button></DialogFooter>
    </fieldset></form>
  </DialogContent></Dialog>;
}
