import type { ApiResponse } from './client';

export type BookCategory = 'textbook' | 'reference' | 'fiction' | 'non_fiction' | 'magazine' | 'newspaper';
export type CopyStatus = 'available' | 'issued' | 'damaged' | 'lost' | 'withdrawn';
export type BorrowerType = 'student' | 'staff';
export interface LibraryBook {
  id: string; isbn: string | null; title: string; author: string; publisher: string | null;
  edition: string | null; category: BookCategory; total_copies: number; available_copies: number;
  shelf_location: string | null; language: string | null; reading_level: string | null;
  is_lendable: boolean; is_active: boolean; added_date_ad: string; created_at: string;
}
export interface LibraryBorrower { id: string; type: BorrowerType; name: string; reference: string | null; active_loans: number; grade?: number | null; section?: string | null; roll_number?: number | null; designation?: string | null }
export interface LibraryLoan {
  id: string; book_id: string; copy_id: string | null; book_title: string; accession_number: string | null;
  issued_to_id: string; issued_to_type: BorrowerType; borrower_name: string; borrower_reference: string | null;
  issue_date_ad: string; issue_date_bs: string; due_date_ad: string; due_date_bs: string;
  return_date_ad: string | null; return_date_bs: string | null; status: 'issued' | 'overdue' | 'returned' | 'lost';
  renewal_count: number; max_renewals: number; renewal_days: number; allow_overdue_renewal: boolean;
  overdue_days: number; fine_amount: string; estimated_fine: string; return_condition: string | null;
  notes: string | null; created_at: string;
}
export interface LibraryCopy { id: string; book_id: string; accession_number: string; status: CopyStatus; acquired_date_ad: string; notes: string | null; loan: LibraryLoan | null }
export interface LibraryPolicy { loan_days: number; student_limit: number; staff_limit: number; renewal_days: number; max_renewals: number; allow_overdue_renewal: boolean; daily_fine: string; fine_cap: string }
export interface LibraryStats { total_books: number; total_copies: number; available_copies: number; total_issued: number; overdue_count: number; total_returned: number; lost_loans: number; assessed_fines: string; categories: Record<string, number>; copy_states: Record<string, number> }
export interface LibraryEvent { id: string; action: string; actor_name: string | null; notes: string | null; before: Record<string, unknown>; after: Record<string, unknown>; created_at: string }
export const bookCategories: Record<BookCategory, string> = { textbook: 'Textbook', reference: 'Reference', fiction: 'Fiction', non_fiction: 'Non-fiction', magazine: 'Magazine', newspaper: 'Newspaper' };
export const librarySelectClass = 'h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export const openLoan = (loan: LibraryLoan) => loan.status === 'issued' || loan.status === 'overdue';
export const canRenewLoan = (loan: LibraryLoan) => openLoan(loan) && loan.renewal_count < loan.max_renewals && (loan.status !== 'overdue' || loan.allow_overdue_renewal);
export function libraryData<T>(response: ApiResponse<T>) { if (!response.success) throw new Error(response.error?.message ?? 'Unable to complete this library request'); return response.data; }
const nepalDateFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kathmandu', year: 'numeric', month: '2-digit', day: '2-digit' });
export function nepalDate(value = new Date()) {
  const parts = nepalDateFormatter.formatToParts(value);
  const part = (name: string) => parts.find((item) => item.type === name)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}
export function dueDate(days: number) { if (!Number.isInteger(days) || days < 1 || days > 90) return ''; const value = new Date(`${nepalDate()}T00:00:00Z`); value.setUTCDate(value.getUTCDate() + days); return value.toISOString().slice(0, 10); }
export function downloadLibraryReport(blob: Blob, kind: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = `library-${kind}-${nepalDate()}.csv`;
  link.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
