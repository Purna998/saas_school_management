import type { ApiResponse } from './client';

export type HostelType = 'boys' | 'girls' | 'mixed';
export type RoomType = 'single' | 'double' | 'dormitory';
export type BedState = 'active' | 'maintenance' | 'retired';
export type RegisterSession = 'morning' | 'evening' | 'breakfast' | 'lunch' | 'snacks' | 'dinner';
export type RegisterStatus = 'present' | 'absent' | 'on_leave' | 'excused' | 'taken' | 'skipped';
export interface Hostel { id: string; name: string; hostel_type: HostelType; warden_name: string | null; warden_phone: string | null; address: string | null; notes: string | null; total_rooms: number; capacity: number; is_active: boolean }
export interface HostelRoom { id: string; hostel_id: string; room_number: string; floor: number; capacity: number; occupied: number; room_type: RoomType; monthly_fee: string; is_active: boolean; notes: string | null; hostel_name?: string; hostel_type?: HostelType; hostel_active?: boolean; available_beds?: number }
export interface Resident { id: string; room_id: string; bed_id: string | null; student_id: string; student_name: string; student_reference: string | null; hostel_name: string; room_number: string; bed_label: string | null; monthly_fee: string; allocated_date_ad: string; allocated_date_bs: string; vacated_date_ad: string | null; vacated_date_bs: string | null; academic_year_bs: string; notes: string | null; checkout_reason: string | null; previous_allocation_id: string | null; status: 'active' | 'vacated'; leave_id: string | null; expected_return_ad: string | null; expected_return_bs: string | null; return_overdue: boolean }
export interface HostelBed { id: string; room_id: string; label: string; status: BedState; notes: string | null; resident: Resident | null }
export interface HostelStudent { id: string; full_name_en: string; full_name_np?: string | null; admission_number: string | null; emis_student_id: string | null; current_grade: number | null; current_section: string | null; roll_number: number | null; gender: string; active_allocation_id: string | null }
export interface HostelStats { total_hostels: number; total_rooms: number; total_capacity: number; maintenance_beds: number; total_occupied: number; available_beds: number; on_leave: number; overdue_returns: number; occupancy_rate: number }
export interface HostelLeave { id: string; allocation_id: string; student_name: string; hostel_name: string; room_number: string; departed_at: string; expected_return_ad: string; expected_return_bs: string; returned_at: string | null; destination: string; responsible_person: string; contact_phone: string | null; reason: string; return_notes: string | null; overdue: boolean }
export interface HostelVisit { id: string; allocation_id: string; student_name: string; hostel_name: string; room_number: string; visitor_name: string; relation: string; contact_phone: string | null; purpose: string; arrived_at: string; departed_at: string | null }
export interface RegisterRow extends Resident { recorded_status: RegisterStatus | null; recorded_notes: string | null; version: number }
export interface HostelEvent { id: string; action: string; actor_name: string | null; created_at: string; label: string | null; notes: string | null; before: Record<string, unknown>; after: Record<string, unknown>; register_changes?: { student_name: string; status: string; notes: string | null; previous_status: string | null }[] }
export interface HostelFeeOptions { academic_year_bs: string; monthly_fee: string; options: { id: string; name: string; amount: string; structure_name: string }[] }
export interface HostelBill { ledger_id: string; student_name: string; month_bs: string; amount: string; already_billed: boolean }
export interface CalendarConversion { bs_date: { year: number; month: number; day: number }; ad_date: { iso_date: string } }
export const hostelSessions: Record<RegisterSession, string> = { morning: 'Morning roll call', evening: 'Evening roll call', breakfast: 'Breakfast / बिहानको खाजा', lunch: 'Lunch / खाना', snacks: 'Afternoon snacks / खाजा', dinner: 'Dinner / बेलुकाको खाना' };
export const bsMonths = ['Baisakh / वैशाख', 'Jestha / जेठ', 'Ashadh / असार', 'Shrawan / साउन', 'Bhadra / भदौ', 'Ashwin / असोज', 'Kartik / कात्तिक', 'Mangsir / मंसिर', 'Poush / पुस', 'Magh / माघ', 'Falgun / फागुन', 'Chaitra / चैत'];
export function hostelData<T>(response: ApiResponse<T>) { if (!response.success) throw new Error(response.error?.message ?? 'Unable to complete this hostel request'); return response.data; }
export function bsString(value: CalendarConversion) { return `${value.bs_date.year}-${String(value.bs_date.month).padStart(2, '0')}-${String(value.bs_date.day).padStart(2, '0')}`; }
export function normalizeBsInput(value: string) { return value.replace(/[०-९]/g, (digit) => String('०१२३४५६७८९'.indexOf(digit))).trim(); }
export function registerChoices(session: RegisterSession): RegisterStatus[] { return ['morning', 'evening'].includes(session) ? ['present', 'absent', 'on_leave', 'excused'] : ['taken', 'skipped']; }
