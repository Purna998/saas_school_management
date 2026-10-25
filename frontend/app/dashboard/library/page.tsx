'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { RefreshCw } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { LibraryEmpty, LibraryStat } from '@/components/library/LibraryCommon';
import { LibraryCatalog } from '@/components/library/LibraryCatalog';
import { useLibraryAccess, useLibraryStats } from '@/components/library/useLibraryStats';
import type { LibraryBook, LibraryCopy, LibraryLoan } from '@/lib/api/library';
import type { LoanAction } from '@/components/library/LibraryCirculation';

const loading = () => <LibraryEmpty>Loading library workspace…</LibraryEmpty>;
const LibraryLoans = dynamic(() => import('@/components/library/LibraryLoans').then((module) => module.LibraryLoans), { loading });
const LibraryPolicy = dynamic(() => import('@/components/library/LibraryPolicy').then((module) => module.LibraryPolicy), { loading });
const LibraryReports = dynamic(() => import('@/components/library/LibraryReports').then((module) => module.LibraryReports), { loading });
const BookEditor = dynamic(() => import('@/components/library/BookEditor').then((module) => module.BookEditor), { loading });
const BookInventoryDialog = dynamic(() => import('@/components/library/LibraryInventory').then((module) => module.BookInventoryDialog), { loading });
const IssueBookDialog = dynamic(() => import('@/components/library/LibraryCirculation').then((module) => module.IssueBookDialog), { loading });
const LoanActionDialog = dynamic(() => import('@/components/library/LibraryCirculation').then((module) => module.LoanActionDialog), { loading });
const LoanDetailsDialog = dynamic(() => import('@/components/library/LibraryCirculation').then((module) => module.LoanDetailsDialog), { loading });

type Modal = { type: 'editor'; book?: LibraryBook } | { type: 'inventory'; bookId: string } | { type: 'issue'; book: LibraryBook; copy?: LibraryCopy } | { type: 'action'; action: LoanAction; loanId: string } | { type: 'details'; loan: LibraryLoan } | null;

export default function LibraryPage() {
  const access = useLibraryAccess();
  const stats = useLibraryStats();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState('catalog');
  const [modal, setModal] = useState<Modal>(null);
  const close = () => setModal(null);
  const onLoan = (loan: LibraryLoan) => setModal({ type: 'details', loan });
  const onIssue = (book: LibraryBook, copy?: LibraryCopy) => setModal({ type: 'issue', book, copy });
  const onAction = (action: LoanAction, loan: LibraryLoan) => setModal({ type: 'action', action, loanId: loan.id });
  if (!access.canRead) return <LibraryEmpty>Your account requires library access to open this workspace.</LibraryEmpty>;
  return <div className="space-y-6">
    <header className="flex flex-wrap items-center justify-between gap-4"><div><h1>Library</h1><p className="text-muted-foreground">Books, physical copies, readers and school lending records.</p></div><Button variant="outline" disabled={stats.isFetching} onClick={() => queryClient.invalidateQueries({ queryKey: ['library'] })}><RefreshCw className={stats.isFetching ? 'animate-spin' : ''} />Refresh records</Button></header>
    {access.privateAccess && <section aria-label="Whole-school library totals">{stats.error ? <LibraryEmpty error={stats.error.message} /> : <div className="pastel-summary grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><LibraryStat label="Active catalog titles" value={stats.data?.total_books ?? '…'} /><LibraryStat label="On-shelf copies · active titles" value={stats.data?.available_copies ?? '…'} /><LibraryStat label="Active loans · students & staff" value={stats.data?.total_issued ?? '…'} /><LibraryStat label="Overdue loans" value={stats.data?.overdue_count ?? '…'} /></div>}</section>}
    <nav aria-label="Library sections" className="section-tabs">{(access.privateAccess ? [['catalog', 'Catalog'], ['loans', 'Loans'], ['overdue', 'Overdue'], ['reports', 'Reports & activity'], ['policy', 'Lending rules']] : [['catalog', 'Catalog']]).map(([id, title]) => <Button key={id} variant={tab === id ? 'default' : 'ghost'} aria-current={tab === id ? 'page' : undefined} onClick={() => setTab(id)}>{title}</Button>)}</nav>
    <Card><CardContent className="pt-5">
      {tab === 'catalog' && <LibraryCatalog {...access} onEdit={(book) => setModal({ type: 'editor', book })} onInventory={(bookId) => setModal({ type: 'inventory', bookId })} onIssue={onIssue} />}
      {access.privateAccess && <>{(tab === 'loans' || tab === 'overdue') && <LibraryLoans key={tab} canIssue={access.canIssue} canReturn={access.canReturn} initialStatus={tab === 'overdue' ? 'overdue' : 'active'} onLoan={onLoan} onAction={onAction} />}{tab === 'reports' && <LibraryReports />}{tab === 'policy' && <LibraryPolicy canEdit={access.canEdit} />}</>}
    </CardContent></Card>
    {modal?.type === 'editor' && (modal.book ? access.canEdit : access.canCreate) && <BookEditor book={modal.book} onClose={close} />}
    {access.privateAccess && <>
      {modal?.type === 'inventory' && <BookInventoryDialog bookId={modal.bookId} canEdit={access.canEdit} canIssue={access.canIssue} onClose={close} onIssue={onIssue} onLoan={onLoan} />}
      {modal?.type === 'issue' && access.canIssue && <IssueBookDialog book={modal.book} copyId={modal.copy?.id} accession={modal.copy?.accession_number} onClose={close} onLoan={onLoan} />}
      {modal?.type === 'action' && (modal.action === 'renew' ? access.canIssue : access.canReturn) && <LoanActionDialog loanId={modal.loanId} action={modal.action} onClose={close} onLoan={onLoan} />}
      {modal?.type === 'details' && <LoanDetailsDialog loan={modal.loan} canIssue={access.canIssue} canReturn={access.canReturn} onClose={close} onAction={onAction} />}
    </>}
  </div>;
}
