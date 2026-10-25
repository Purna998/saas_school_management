"use client"

import { FormEvent, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export interface StaffMember {
  id: string
  employee_id?: string | null
  full_name_en: string
  full_name_np?: string | null
  gender: string
  date_of_birth_ad?: string | null
  date_of_birth_bs?: string | null
  phone?: string | null
  email?: string | null
  address?: string | null
  photo_url?: string | null
  staff_type: string
  designation?: string | null
  department?: string | null
  qualification?: string | null
  tsc_number?: string | null
  joined_date_ad?: string | null
  joined_date_bs?: string | null
  status: string
  salary?: string | number | null
  created_at?: string
  updated_at?: string
}

interface FormState {
  employee_id: string
  full_name_en: string
  full_name_np: string
  gender: string
  date_of_birth_ad: string
  date_of_birth_bs: string
  phone: string
  email: string
  address: string
  staff_type: string
  designation: string
  department: string
  qualification: string
  tsc_number: string
  joined_date_ad: string
  joined_date_bs: string
  salary: string
  status: string
}

const emptyForm: FormState = {
  employee_id: "",
  full_name_en: "",
  full_name_np: "",
  gender: "male",
  date_of_birth_ad: "",
  date_of_birth_bs: "",
  phone: "",
  email: "",
  address: "",
  staff_type: "teaching",
  designation: "",
  department: "",
  qualification: "",
  tsc_number: "",
  joined_date_ad: "",
  joined_date_bs: "",
  salary: "",
  status: "active",
}

const fieldClass = "space-y-1.5"
const labelClass = "text-sm font-medium"
const selectClass = "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"

function optional(value: string): string | undefined {
  const trimmed = value.trim()
  return trimmed || undefined
}

interface StaffEditorDialogProps {
  open: boolean
  mode: "create" | "edit"
  initialType?: string
  staff?: StaffMember | null
  saving: boolean
  onOpenChange: (open: boolean) => void
  onSave: (payload: Record<string, unknown>) => Promise<void>
}

export function StaffEditorDialog({
  open,
  mode,
  initialType = "teaching",
  staff,
  saving,
  onOpenChange,
  onSave,
}: StaffEditorDialogProps) {
  const [form, setForm] = useState<FormState>(() => staff
    ? {
        employee_id: staff.employee_id ?? "",
        full_name_en: staff.full_name_en,
        full_name_np: staff.full_name_np ?? "",
        gender: staff.gender,
        date_of_birth_ad: staff.date_of_birth_ad ?? "",
        date_of_birth_bs: staff.date_of_birth_bs ?? "",
        phone: staff.phone ?? "",
        email: staff.email ?? "",
        address: staff.address ?? "",
        staff_type: staff.staff_type,
        designation: staff.designation ?? "",
        department: staff.department ?? "",
        qualification: staff.qualification ?? "",
        tsc_number: staff.tsc_number ?? "",
        joined_date_ad: staff.joined_date_ad ?? "",
        joined_date_bs: staff.joined_date_bs ?? "",
        salary: staff.salary?.toString() ?? "",
        status: staff.status,
      }
    : { ...emptyForm, staff_type: initialType })

  const setField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const blankable = (value: string) => optional(value) ?? (mode === "edit" ? null : undefined)
    const payload: Record<string, unknown> = {
      employee_id: blankable(form.employee_id),
      full_name_en: form.full_name_en.trim(),
      full_name_np: blankable(form.full_name_np),
      gender: form.gender,
      date_of_birth_ad: blankable(form.date_of_birth_ad),
      date_of_birth_bs: blankable(form.date_of_birth_bs),
      phone: blankable(form.phone),
      email: blankable(form.email),
      address: blankable(form.address),
      staff_type: form.staff_type,
      designation: blankable(form.designation),
      department: blankable(form.department),
      qualification: blankable(form.qualification),
      tsc_number: isTeacher ? blankable(form.tsc_number) : null,
      joined_date_ad: blankable(form.joined_date_ad),
      joined_date_bs: blankable(form.joined_date_bs),
      salary: form.salary ? Number(form.salary) : mode === "edit" ? null : undefined,
    }
    if (mode === "edit") payload.status = form.status
    await onSave(payload)
  }

  const isTeacher = form.staff_type === "teaching"

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !saving && onOpenChange(nextOpen)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "create" ? `Add ${isTeacher ? "teacher" : "staff member"}` : "Edit staff member"}</DialogTitle>
          <DialogDescription>Enter employment and contact information. Fields marked with * are required.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-name">Full name *</label>
              <Input id="staff-name" value={form.full_name_en} onChange={(event) => setField("full_name_en", event.target.value)} minLength={2} required />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-name-np">Nepali name</label>
              <Input id="staff-name-np" value={form.full_name_np} onChange={(event) => setField("full_name_np", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-employee-id">Employee ID</label>
              <Input id="staff-employee-id" value={form.employee_id} onChange={(event) => setField("employee_id", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-type">Staff type *</label>
              <select id="staff-type" className={selectClass} value={form.staff_type} onChange={(event) => setField("staff_type", event.target.value)} required>
                <option value="teaching">Teacher</option>
                <option value="administrative">Administrator</option>
                <option value="non_teaching">Support staff</option>
              </select>
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-gender">Gender *</label>
              <select id="staff-gender" className={selectClass} value={form.gender} onChange={(event) => setField("gender", event.target.value)} required>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-dob">Date of birth (AD)</label>
              <Input id="staff-dob" type="date" value={form.date_of_birth_ad} onChange={(event) => setField("date_of_birth_ad", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-dob-bs">Date of birth (BS)</label>
              <Input id="staff-dob-bs" placeholder="2045-01-01" value={form.date_of_birth_bs} onChange={(event) => setField("date_of_birth_bs", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-phone">Phone</label>
              <Input id="staff-phone" type="tel" value={form.phone} onChange={(event) => setField("phone", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-email">Email</label>
              <Input id="staff-email" type="email" value={form.email} onChange={(event) => setField("email", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-designation">Designation</label>
              <Input id="staff-designation" placeholder={isTeacher ? "Senior Teacher" : "Accountant"} value={form.designation} onChange={(event) => setField("designation", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-department">Department</label>
              <Input id="staff-department" placeholder={isTeacher ? "Science" : "Administration"} value={form.department} onChange={(event) => setField("department", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-qualification">Qualification</label>
              <Input id="staff-qualification" value={form.qualification} onChange={(event) => setField("qualification", event.target.value)} />
            </div>
            {isTeacher && (
              <div className={fieldClass}>
                <label className={labelClass} htmlFor="staff-tsc">TSC number</label>
                <Input id="staff-tsc" placeholder="TSC-12345" pattern="TSC-[0-9]{5}" title="Use the format TSC-12345" value={form.tsc_number} onChange={(event) => setField("tsc_number", event.target.value.toUpperCase())} />
              </div>
            )}
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-joined">Joined date (AD)</label>
              <Input id="staff-joined" type="date" value={form.joined_date_ad} onChange={(event) => setField("joined_date_ad", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-joined-bs">Joined date (BS)</label>
              <Input id="staff-joined-bs" placeholder="2080-01-01" value={form.joined_date_bs} onChange={(event) => setField("joined_date_bs", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="staff-salary">Monthly salary (NPR)</label>
              <Input id="staff-salary" type="number" min={0} step="0.01" value={form.salary} onChange={(event) => setField("salary", event.target.value)} />
            </div>
            {mode === "edit" && (
              <div className={fieldClass}>
                <label className={labelClass} htmlFor="staff-status">Status</label>
                <select id="staff-status" className={selectClass} value={form.status} onChange={(event) => setField("status", event.target.value)}>
                  <option value="active">Active</option>
                  <option value="on_leave">On leave</option>
                  <option value="resigned">Resigned</option>
                  <option value="retired">Retired</option>
                  <option value="terminated">Terminated</option>
                </select>
              </div>
            )}
            <div className={`${fieldClass} sm:col-span-2`}>
              <label className={labelClass} htmlFor="staff-address">Address</label>
              <Input id="staff-address" value={form.address} onChange={(event) => setField("address", event.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline" disabled={saving}>Cancel</Button></DialogClose>
            <Button type="submit" disabled={saving}>{saving ? "Saving..." : mode === "create" ? "Add member" : "Save changes"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Detail({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm capitalize">{value === null || value === undefined || value === "" ? "-" : String(value).replaceAll("_", " ")}</dd>
    </div>
  )
}

export function StaffDetailsDialog({ open, staff, loading, onOpenChange }: {
  open: boolean
  staff?: StaffMember | null
  loading: boolean
  onOpenChange: (open: boolean) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{staff?.staff_type === "teaching" ? "Teacher" : "Staff"} details</DialogTitle>
          <DialogDescription>Personal, contact, and employment information.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="py-12 text-center text-muted-foreground">Loading details...</div>
        ) : staff ? (
          <dl className="grid gap-5 sm:grid-cols-3">
            <Detail label="Name" value={staff.full_name_en} />
            <Detail label="Nepali name" value={staff.full_name_np} />
            <Detail label="Employee ID" value={staff.employee_id} />
            <Detail label="Type" value={staff.staff_type} />
            <Detail label="Designation" value={staff.designation} />
            <Detail label="Department" value={staff.department} />
            <Detail label="Status" value={staff.status} />
            <Detail label="TSC number" value={staff.tsc_number} />
            <Detail label="Qualification" value={staff.qualification} />
            <Detail label="Gender" value={staff.gender} />
            <Detail label="DOB (AD)" value={staff.date_of_birth_ad} />
            <Detail label="DOB (BS)" value={staff.date_of_birth_bs} />
            <Detail label="Phone" value={staff.phone} />
            <Detail label="Email" value={staff.email} />
            <Detail label="Address" value={staff.address} />
            <Detail label="Joined (AD)" value={staff.joined_date_ad} />
            <Detail label="Joined (BS)" value={staff.joined_date_bs} />
            <Detail label="Salary (NPR)" value={staff.salary} />
          </dl>
        ) : (
          <div className="py-12 text-center text-destructive">Unable to load staff details.</div>
        )}
      </DialogContent>
    </Dialog>
  )
}
