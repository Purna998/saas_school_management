import type { ApiResponse } from './client';

export type FeeFrequency = 'monthly' | 'quarterly' | 'annual' | 'one_time';
export type PaymentMethod = 'cash' | 'bank_transfer' | 'cheque';
export interface FeeHead { id: string; fee_structure_id: string; name: string; amount: string; frequency: FeeFrequency; is_optional: boolean; is_billed: boolean }
export interface FeeStructure { id: string; school_id: string; academic_year_bs: string; grade: string; name: string; description: string | null; is_active: boolean; fee_heads: FeeHead[] }
export interface FeeStudent { id: string; full_name_en: string; current_grade: number | null; current_section: string | null; roll_number: number | null; status: string }
export interface FeePayment { id: string; student_id: string; ledger_id: string; amount: string; refunded_amount: string; payment_method: PaymentMethod; reference: string | null; receipt_number: string; paid_date_ad: string; paid_date_bs: string | null; remarks: string | null; balance_after: string | null; created_at: string; student_name?: string; fee_head_name?: string }
export interface FeeRefund { id: string; amount: string; reason: string; refund_number: string; payment_method: PaymentMethod; reference: string | null; refunded_date_ad: string; refunded_date_bs: string }
export interface FeeBill { id: string; student_id: string; fee_head_id: string; fee_head_name: string; academic_year_bs: string; month_bs: string | null; original_amount: string; discount_amount: string; amount_due: string; amount_paid: string; balance: string; due_date_ad: string; due_date_bs: string; status: string; payments: FeePayment[] }
export interface FeeStatement { student_id: string; student_name: string; academic_year_bs: string; total_original: string; total_discount: string; total_due: string; total_paid: string; total_balance: string; ledger_entries: FeeBill[] }
export interface FeeAward { id: string; student_id: string; student_name: string; name: string; discount_type: 'fixed' | 'percentage'; discount_value: string; applied_amount: string; academic_year_bs: string; is_active: boolean; reversal_reason: string | null; created_at: string }
export interface FeeSummary { academic_year_bs: string; total_original: string; total_discount: string; total_due: string; gross_collected: string; total_refunded: string; total_collected: string; total_pending: string; total_overdue: string; collection_rate: string; monthly_breakdown: { month_bs: string; total_collected: string; total_pending: string; payment_count: number }[] }
export interface OutstandingStudent { student_id: string; student_name: string; grade: number | null; section: string | null; total_due: string; total_paid: string; total_balance: string; overdue_count: number }
export interface OutstandingFees { total_outstanding: string; student_count: number; page: number; limit: number; students: OutstandingStudent[] }
export interface FeeReceipt { payment: FeePayment; refunds: FeeRefund[]; school: { name_en: string; phone: string | null; email: string | null; municipality: string | null; district: string | null }; student_name: string; admission_number: string | null; fee_head_name: string; month_bs: string | null; academic_year_bs: string; cashier_name: string | null }
export interface BillingResult { entries_created: number; entries_skipped: number; total_assessed: string; student_count: number }

export const bsMonthNames = ['Baisakh', 'Jestha', 'Ashadh', 'Shrawan', 'Bhadra', 'Ashwin', 'Kartik', 'Mangsir', 'Poush', 'Magh', 'Falgun', 'Chaitra'];
export const feeSelectClass = 'h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring';
export const methodLabel = (method: string) => ({ cash: 'Cash', bank_transfer: 'Bank transfer', cheque: 'Cheque' })[method] ?? method;
export const periodLabel = (period: string | null) => !period || period === 'annual' ? 'Annual / one-time' : `${bsMonthNames[Number(period.slice(-2)) - 1] ?? period} ${period.slice(0, 4)}`;
const currencyFormatter = new Intl.NumberFormat('en-NP', { style: 'currency', currency: 'NPR', minimumFractionDigits: 2 });
export const money = (value: string | number | null | undefined) => {
  const raw = String(value ?? '0');
  if (!/^\d+(\.\d{1,2})?$/.test(raw)) return currencyFormatter.format(Number(raw));
  const [whole, fraction = ''] = raw.split('.');
  return currencyFormatter.formatToParts(BigInt(whole)).map((part) => part.type === 'fraction' ? fraction.padEnd(2, '0') : part.value).join('');
};

export function paise(value: string): bigint {
  if (!/^\d+(\.\d{1,2})?$/.test(value)) return BigInt(0);
  const [whole, fraction = ''] = value.split('.');
  return BigInt(whole) * BigInt(100) + BigInt(fraction.padEnd(2, '0'));
}
export function fromPaise(value: bigint) { return `${value / BigInt(100)}.${(value % BigInt(100)).toString().padStart(2, '0')}`; }
export function validMoney(value: string) { return /^\d{1,10}(\.\d{1,2})?$/.test(value) && paise(value) > BigInt(0); }
export function feeData<T>(response: ApiResponse<T>): T {
  if (!response.success) throw new Error(response.error?.message ?? 'Unable to complete this fee request');
  return response.data;
}
export function academicYear(value: string) {
  const match = /^(\d{4})(?:\/(\d{3,4}))?$/.exec(value.trim());
  if (!match) throw new Error('Use a BS academic year such as 2083 or 2083/084');
  const year = Number(match[1]);
  if (match[2] && Number(match[2]) !== year + 1 && Number(match[2]) !== (year + 1) % 1000) throw new Error('The second year must follow the first year');
  return `${year}/${String((year + 1) % 1000).padStart(3, '0')}`;
}
