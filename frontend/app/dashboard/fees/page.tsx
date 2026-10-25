'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { useQuery } from '@tanstack/react-query';
import { Banknote, FilePlus2, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { FeeEmpty, FeeField, FeeStat, PaymentDialog, ReceiptDialog } from '@/components/fees/FeeDialogs';
import { FeeStudentPicker, StudentFeePanel } from '@/components/fees/FeeRegisters';
import { apiClient } from '@/lib/api/client';
import { academicYear, feeData, feeSelectClass, money } from '@/lib/api/fees';
import type { FeePayment, FeeStudent, OutstandingStudent } from '@/lib/api/fees';
import { useAuthStore } from '@/lib/store/auth';

const loadingTab = () => <FeeEmpty>Loading workspace…</FeeEmpty>;
const FeeSetup = dynamic(() => import('@/components/fees/FeeSetup').then((module) => module.FeeSetup), { loading: loadingTab });
const FeeBilling = dynamic(() => import('@/components/fees/FeeBilling').then((module) => module.FeeBilling), { loading: loadingTab });
const FeePayments = dynamic(() => import('@/components/fees/FeeRegisters').then((module) => module.FeePayments), { loading: loadingTab });
const FeeScholarships = dynamic(() => import('@/components/fees/FeeRegisters').then((module) => module.FeeScholarships), { loading: loadingTab });
const FeeReports = dynamic(() => import('@/components/fees/FeeRegisters').then((module) => module.FeeReports), { loading: loadingTab });
type FeeTab = 'students' | 'setup' | 'billing' | 'payments' | 'scholarships' | 'reports';

export default function FeesPage() {
  const user = useAuthStore((state) => state.user);
  const has = (permission: string) => Boolean(user?.permissions?.includes(permission) || user?.permissions?.includes('*:*'));
  const canCreate = has('fee:create');
  const canCollect = has('fee:collect');
  const canReport = has('fee:report');
  const canRefund = has('fee:refund');
  const canRead = has('fee:read') && (!['parent', 'student'].includes(user?.role ?? '') || canCreate || canCollect || canReport);
  const [tab, setTab] = useState<FeeTab>('students');
  const [selectedYear, setSelectedYear] = useState('');
  const [yearDraft, setYearDraft] = useState<string | null>(null);
  const [grade, setGrade] = useState('');
  const [student, setStudent] = useState<FeeStudent | null>(null);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [refund, setRefund] = useState<{ payment: FeePayment; studentName: string } | null>(null);
  const currentBs = useQuery({ queryKey: ['calendar', 'current-bs'], queryFn: async () => feeData(await apiClient.calendar.getCurrentBs()) as { bs_date: { year: number } }, enabled: canRead, staleTime: 60_000 });
  const year = selectedYear || (currentBs.data?.bs_date.year ? academicYear(String(currentBs.data.bs_date.year)) : '');
  const summary = useQuery({ queryKey: ['fees', 'summary', year], queryFn: async () => feeData(await apiClient.fees.summary(year)), enabled: canRead && canReport && Boolean(year) });
  const tabs: { id: FeeTab; title: string; show: boolean }[] = [
    { id: 'students', title: 'Student dues', show: true },
    { id: 'setup', title: 'Fee setup', show: true },
    { id: 'billing', title: 'Billing', show: canCreate },
    { id: 'payments', title: 'Payments & receipts', show: true },
    { id: 'scholarships', title: 'Concessions', show: true },
    { id: 'reports', title: 'Reports', show: canReport },
  ];
  const openStudent = (entry: OutstandingStudent) => {
    setStudent({ id: entry.student_id, full_name_en: entry.student_name, current_grade: entry.grade, current_section: entry.section, roll_number: null, status: '' });
    setTab('students');
  };

  if (!canRead) return <Card><CardContent><FeeEmpty>This school accounting workspace requires fee access from an authorized staff account.</FeeEmpty></CardContent></Card>;

  return <div className="space-y-6">
    <header className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><h1>Fees & Payments</h1><p className="text-muted-foreground">Student dues, confirmed collections, concessions, and receipts in NPR.</p></div><div className="flex gap-2">{canCreate && year && <Button variant="outline" onClick={() => setTab('billing')}><FilePlus2 />Generate bills</Button>}{canCollect && <Button onClick={() => setTab('students')}><Banknote />Collect fees</Button>}</div></header>

    <Card><CardContent className="flex flex-wrap items-end gap-4 pt-5"><form className="flex items-end gap-2" onSubmit={(event) => { event.preventDefault(); try { setSelectedYear(academicYear(yearDraft ?? year)); setYearDraft(null); } catch (error) { toast.error((error as Error).message); } }}><FeeField label="Academic year (BS)"><Input required maxLength={9} className="w-40" value={yearDraft ?? year} placeholder="2083/084" onChange={(event) => setYearDraft(event.target.value)} /></FeeField><Button type="submit" variant="outline">Apply year</Button></form><FeeField label="Current grade filter"><select className={`${feeSelectClass} min-w-40`} value={grade} onChange={(event) => { setGrade(event.target.value); setStudent(null); }}><option value="">All grades</option>{Array.from({ length: 12 }, (_, index) => <option key={index + 1} value={index + 1}>Grade {index + 1}</option>)}</select></FeeField>{canReport && year && <Button variant="ghost" size="sm" disabled={summary.isFetching} onClick={() => summary.refetch()}><RefreshCw className={summary.isFetching ? 'animate-spin' : ''} />Refresh totals</Button>}<p className="text-xs text-muted-foreground">Cash, bank, and cheque records · Online checkout is not enabled.</p></CardContent></Card>

    {canReport && year && <section aria-label="Whole-school fee totals" className="space-y-2"><p className="text-xs text-muted-foreground">Whole-school totals · {year} BS · Net of concessions and refunds</p>{summary.error ? <p role="alert" className="text-sm text-destructive">{summary.error.message}</p> : <div className="pastel-summary grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><FeeStat label="Net billed" value={summary.data ? money(summary.data.total_due) : '…'} /><FeeStat label="Net collected" value={summary.data ? money(summary.data.total_collected) : '…'} /><FeeStat label="Outstanding" value={summary.data ? money(summary.data.total_pending) : '…'} /><FeeStat label="Overdue" value={summary.data ? money(summary.data.total_overdue) : '…'} /></div>}</section>}

    <nav aria-label="Fee sections" className="section-tabs flex flex-wrap gap-1 border-b pb-2">{tabs.filter((item) => item.show).map((item) => <Button key={item.id} variant={tab === item.id ? 'default' : 'ghost'} aria-current={tab === item.id ? 'page' : undefined} onClick={() => setTab(item.id)}>{item.title}</Button>)}</nav>

    {!year ? <FeeEmpty>{currentBs.isLoading ? 'Loading Nepal academic year…' : 'Enter the BS academic year above to open fee records.'}</FeeEmpty> : <section key={`${year}:${grade}`} aria-label="Fee workspace">
      {tab === 'students' && <div className="space-y-5"><FeeStudentPicker grade={grade} selected={student} onSelect={setStudent} />{student ? <StudentFeePanel key={student.id} year={year} student={student} canCreate={canCreate} canCollect={canCollect} onReceipt={setReceipt} /> : <FeeEmpty>Select a student to view dues, record a payment, or apply a concession.</FeeEmpty>}</div>}
      {tab === 'setup' && <FeeSetup year={year} grade={grade} canCreate={canCreate} />}
      {tab === 'billing' && canCreate && <FeeBilling year={year} grade={grade} />}
      {tab === 'payments' && <FeePayments year={year} grade={grade} onReceipt={setReceipt} />}
      {tab === 'scholarships' && <FeeScholarships year={year} grade={grade} canCreate={canCreate} />}
      {tab === 'reports' && canReport && <FeeReports year={year} grade={grade} onStudent={openStudent} />}
    </section>}
    {receipt && <ReceiptDialog paymentId={receipt} canRefund={canRefund} onClose={() => setReceipt(null)} onRefund={(payment, studentName) => { setReceipt(null); setRefund({ payment, studentName }); }} />}
    {refund && <PaymentDialog payment={refund.payment} student={{ id: refund.payment.student_id, full_name_en: refund.studentName }} onClose={() => setRefund(null)} onPaid={setReceipt} />}
  </div>;
}
