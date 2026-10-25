'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Printer } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { apiClient } from '@/lib/api/client';
import { feeData, feeSelectClass, fromPaise, methodLabel, money, paise, periodLabel, validMoney } from '@/lib/api/fees';
import type { FeeBill, FeePayment, FeeStudent, PaymentMethod } from '@/lib/api/fees';

export function FeeField({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="grid gap-1.5 text-sm"><span className="font-medium">{label}</span>{children}</label>;
}

export function FeeEmpty({ error, children }: { error?: string; children?: React.ReactNode }) {
  return <div role={error ? 'alert' : undefined} className={`py-10 text-center text-sm ${error ? 'text-destructive' : 'text-muted-foreground'}`}>{error ?? children}</div>;
}

export function FeeStat({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border bg-muted/30 p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-2 text-lg font-semibold">{value}</p></div>;
}

export function PaymentDialog({ student, bill, payment, onClose, onPaid }: {
  student: { id: string; full_name_en: string }; bill?: FeeBill; payment?: FeePayment;
  onClose: () => void; onPaid: (id: string) => void;
}) {
  const refund = Boolean(payment);
  const maximum = bill ? bill.balance : fromPaise(paise(payment!.amount) - paise(payment!.refunded_amount));
  const [amount, setAmount] = useState(maximum);
  const [method, setMethod] = useState<PaymentMethod>('cash');
  const [reference, setReference] = useState('');
  const [notes, setNotes] = useState('');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const queryClient = useQueryClient();
  const change = (update: () => void) => { update(); setRequestId(crypto.randomUUID()); };
  const mutation = useMutation({
    mutationFn: async () => {
      if (!validMoney(amount) || paise(amount) > paise(maximum)) throw new Error(`Enter an amount from NPR 0.01 to ${money(maximum)}`);
      const values = { amount, payment_method: method, reference: reference.trim() || null, request_id: requestId };
      if (refund) return feeData(await apiClient.fees.refund(payment!.id, { ...values, reason: notes.trim() }));
      return feeData(await apiClient.fees.collect({ ...values, student_id: student.id, ledger_id: bill!.id, remarks: notes.trim() || null }));
    },
    onSuccess: async (result) => {
      toast.success(refund ? 'Refund recorded; the student balance has been updated' : 'Payment recorded and receipt issued');
      onClose();
      onPaid(refund ? payment!.id : result.id);
      await queryClient.invalidateQueries({ queryKey: ['fees'] });
    },
    onError: (error) => toast.error(error.message),
  });
  return <Dialog open onOpenChange={(open) => !open && !mutation.isPending && onClose()}><DialogContent className="max-w-lg">
    <DialogHeader><DialogTitle>{refund ? 'Record a refund' : 'Record a payment'}</DialogTitle><DialogDescription>{refund ? 'Record money already returned outside the system. The original receipt will remain in the audit trail.' : 'Record a confirmed cash, bank, or cheque collection. This records the payment; it does not move money.'}</DialogDescription></DialogHeader>
    <div className="mb-5 rounded-xl bg-accent/50 p-4 text-sm"><p className="font-semibold">{student.full_name_en}</p><p className="mt-1 text-muted-foreground">{bill ? `${bill.fee_head_name} · ${periodLabel(bill.month_bs)}` : payment!.receipt_number}</p><p className="mt-2">{refund ? 'Available to refund' : 'Outstanding on this bill'}: <strong>{money(maximum)}</strong></p></div>
    <form onSubmit={(event) => { event.preventDefault(); mutation.mutate(); }}><fieldset disabled={mutation.isPending} className="space-y-4">
      <FeeField label="Amount (NPR)"><Input required inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" value={amount} onChange={(event) => change(() => setAmount(event.target.value))} /></FeeField>
      <FeeField label={refund ? 'Refund method' : 'Payment method'}><select className={feeSelectClass} value={method} onChange={(event) => change(() => setMethod(event.target.value as PaymentMethod))}><option value="cash">Cash</option><option value="bank_transfer">Bank transfer</option><option value="cheque">Cheque</option></select></FeeField>
      <FeeField label="Bank / cheque reference"><Input required={method !== 'cash'} maxLength={100} value={reference} onChange={(event) => change(() => setReference(event.target.value))} placeholder={method === 'cash' ? 'Optional for cash' : 'Confirmed transaction or cheque number'} /></FeeField>
      <FeeField label={refund ? 'Reason for refund' : 'Remarks'}><Input required={refund} minLength={refund ? 3 : undefined} maxLength={500} value={notes} onChange={(event) => change(() => setNotes(event.target.value))} /></FeeField>
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit">{mutation.isPending && <Loader2 className="animate-spin" />}{refund ? 'Record refund' : 'Record payment'}</Button></DialogFooter>
    </fieldset></form>
  </DialogContent></Dialog>;
}

export function ScholarshipDialog({ student, year, outstanding, bill, onClose }: {
  student: FeeStudent; year: string; outstanding: string; bill?: FeeBill; onClose: () => void;
}) {
  const [name, setName] = useState(bill ? `Fee waiver: ${bill.fee_head_name}` : '');
  const [discountType, setDiscountType] = useState<'fixed' | 'percentage'>(bill ? 'percentage' : 'fixed');
  const [value, setValue] = useState(bill ? '100' : '');
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const queryClient = useQueryClient();
  const base = bill?.balance ?? outstanding;
  const preview = discountType === 'fixed' ? paise(value) : (paise(base) * paise(value) + BigInt(5000)) / BigInt(10000);
  const change = (update: () => void) => { update(); setRequestId(crypto.randomUUID()); };
  const save = useMutation({
    mutationFn: async () => {
      if (!validMoney(value)) throw new Error('Enter a positive amount with up to two decimal places');
      if (discountType === 'percentage' && paise(value) > BigInt(10000)) throw new Error('The percentage cannot exceed 100');
      if (preview <= BigInt(0) || preview > paise(base)) throw new Error('The concession must fit within the current unpaid balance');
      return feeData(await apiClient.fees.award({ student_id: student.id, name, academic_year_bs: year,
        discount_type: discountType, discount_value: value, request_id: requestId,
        ledger_ids: bill ? [bill.id] : undefined }));
    },
    onSuccess: async () => { toast.success('Concession applied to unpaid dues'); onClose(); await queryClient.invalidateQueries({ queryKey: ['fees'] }); },
    onError: (error) => toast.error(error.message),
  });
  return <Dialog open onOpenChange={(open) => !open && !save.isPending && onClose()}><DialogContent className="max-w-lg">
    <DialogHeader><DialogTitle>{bill ? 'Waive or reduce this bill' : 'Scholarship / concession'}</DialogTitle><DialogDescription>{bill ? `${bill.fee_head_name} · ${periodLabel(bill.month_bs)}` : 'Applies once to current unpaid bills in this academic year. Future bills are not automatically discounted.'}</DialogDescription></DialogHeader>
    <p className="mb-5 rounded-lg bg-accent/50 p-3 text-sm">{student.full_name_en} · {year} BS<br /><strong>Eligible unpaid balance: {money(base)}</strong></p>
    <form onSubmit={(event) => { event.preventDefault(); save.mutate(); }}><fieldset disabled={save.isPending} className="space-y-4">
      <FeeField label="Award name / reason"><Input required maxLength={150} value={name} onChange={(event) => change(() => setName(event.target.value))} placeholder="Merit scholarship, sibling concession, correction…" /></FeeField>
      <FeeField label="Discount type"><select className={feeSelectClass} value={discountType} onChange={(event) => change(() => setDiscountType(event.target.value as 'fixed' | 'percentage'))}><option value="fixed">Fixed total amount (NPR)</option><option value="percentage">Percentage of unpaid dues</option></select></FeeField>
      <FeeField label={discountType === 'fixed' ? 'Total concession (NPR)' : 'Discount (%)'}><Input required inputMode="decimal" pattern="[0-9]+(\.[0-9]{1,2})?" value={value} onChange={(event) => change(() => setValue(event.target.value))} /></FeeField>
      <p className="text-sm">Concession: <strong>{money(fromPaise(preview))}</strong></p>
      <p className="text-xs leading-5 text-muted-foreground">Fixed amounts are applied once, oldest bill first. Percentages are spread proportionally. Paid money is not discounted; use a refund to record money returned.</p>
      <DialogFooter><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit">{save.isPending && <Loader2 className="animate-spin" />}Apply concession</Button></DialogFooter>
    </fieldset></form>
  </DialogContent></Dialog>;
}

export function ReceiptDialog({ paymentId, canRefund, onClose, onRefund }: {
  paymentId: string; canRefund: boolean; onClose: () => void; onRefund: (payment: FeePayment, studentName: string) => void;
}) {
  const receipt = useQuery({ queryKey: ['fees', 'receipt', paymentId], queryFn: async () => feeData(await apiClient.fees.receipt(paymentId)) });
  const data = receipt.data;
  return <Dialog open onOpenChange={(open) => !open && onClose()}><DialogContent className="max-w-2xl">
    <DialogHeader><DialogTitle>Fee payment receipt</DialogTitle><DialogDescription>The original payment is retained alongside any refund records.</DialogDescription></DialogHeader>
    {receipt.isLoading ? <FeeEmpty>Loading receipt…</FeeEmpty> : receipt.error ? <FeeEmpty error={receipt.error.message} /> : data && <>
      <section id="fee-receipt" className="space-y-6 rounded-xl border p-5 text-sm">
        <header className="border-b pb-4 text-center"><h2 className="text-xl font-semibold">{data.school.name_en}</h2><p className="mt-1 text-muted-foreground">{[data.school.municipality, data.school.district].filter(Boolean).join(', ')}</p><p className="text-xs text-muted-foreground">{[data.school.phone, data.school.email].filter(Boolean).join(' · ')}</p><p className="mt-4 font-semibold">FEE PAYMENT RECEIPT</p></header>
        <dl className="grid gap-3 sm:grid-cols-2"><div><dt className="text-xs text-muted-foreground">Receipt number</dt><dd className="mt-1 break-all font-mono text-xs">{data.payment.receipt_number}</dd></div><div><dt className="text-xs text-muted-foreground">Date</dt><dd>{data.payment.paid_date_bs ?? '—'} BS · {data.payment.paid_date_ad} AD</dd></div><div><dt className="text-xs text-muted-foreground">Student</dt><dd className="font-medium">{data.student_name}</dd></div><div><dt className="text-xs text-muted-foreground">Admission number</dt><dd>{data.admission_number ?? '—'}</dd></div><div><dt className="text-xs text-muted-foreground">Academic year</dt><dd>{data.academic_year_bs} BS</dd></div><div><dt className="text-xs text-muted-foreground">Received by</dt><dd>{data.cashier_name ?? 'Authorized school staff'}</dd></div></dl>
        <table className="w-full"><thead><tr><th className="p-3 text-left">Fee</th><th className="p-3 text-left">Billing period</th><th className="p-3 text-right">Amount</th></tr></thead><tbody><tr><td className="p-3">{data.fee_head_name}</td><td className="p-3">{periodLabel(data.month_bs)}</td><td className="p-3 text-right font-semibold">{money(data.payment.amount)}</td></tr></tbody></table>
        <div className="grid gap-2 border-t pt-4 sm:grid-cols-2"><p>Method: {methodLabel(data.payment.payment_method)}</p><p>Reference: {data.payment.reference || '—'}</p>{data.payment.balance_after !== null && <p className="sm:col-span-2">Balance immediately after payment: <strong>{money(data.payment.balance_after)}</strong></p>}{data.payment.remarks && <p className="sm:col-span-2">Remarks: {data.payment.remarks}</p>}</div>
        {data.refunds.length > 0 && <section className="border-t pt-4"><h3 className="font-semibold">Refund history</h3>{data.refunds.map((refund) => <div key={refund.id} className="mt-3 rounded-lg border p-3"><p>{money(refund.amount)} · {refund.refunded_date_bs} BS · {methodLabel(refund.payment_method)}</p><p className="mt-1 break-all font-mono text-[11px]">{refund.refund_number}</p><p className="mt-1">{refund.reason}</p>{refund.reference && <p>Reference: {refund.reference}</p>}</div>)}<p className="mt-3 font-medium">Net retained: {money(fromPaise(paise(data.payment.amount) - paise(data.payment.refunded_amount)))}</p></section>}
        <p className="border-t pt-4 text-xs text-muted-foreground">School fee collection record · Amounts in Nepalese rupees (NPR)</p>
      </section>
      <DialogFooter>{canRefund && paise(data.payment.amount) > paise(data.payment.refunded_amount) && <Button disabled={receipt.isFetching} variant="outline" onClick={() => onRefund(data.payment, data.student_name)}>Record refund</Button>}<Button variant="outline" onClick={onClose}>Close</Button><Button disabled={receipt.isFetching} onClick={() => window.print()}>{receipt.isFetching ? <Loader2 className="animate-spin" /> : <Printer />}Print receipt</Button></DialogFooter>
    </>}
  </DialogContent></Dialog>;
}
