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

export interface Guardian {
  id?: string
  relation: string
  full_name_en: string
  full_name_np?: string | null
  phone?: string | null
  email?: string | null
  occupation?: string | null
  is_primary_contact: boolean
}

export interface Student {
  id: string
  roll_number?: number | null
  full_name_en: string
  full_name_np?: string | null
  gender: string
  emis_student_id?: string | null
  admission_number?: string | null
  current_grade?: number | null
  current_section?: string | null
  current_faculty?: string | null
  date_of_birth_ad: string
  date_of_birth_bs?: string | null
  phone?: string | null
  email?: string | null
  address_permanent?: string | null
  address_temporary?: string | null
  caste_ethnicity?: string | null
  religion?: string | null
  mother_tongue?: string | null
  nationality?: string | null
  disability_type?: string | null
  status: string
  photo_url?: string | null
  guardians?: Guardian[]
  created_at?: string
  updated_at?: string
}

export interface StudentSaveRequest {
  payload: Record<string, unknown>
  photo: File | null
}

type EditorMode = "create" | "edit"

interface StudentEditorDialogProps {
  open: boolean
  mode: EditorMode
  student?: Student | null
  saving: boolean
  onOpenChange: (open: boolean) => void
  onSave: (request: StudentSaveRequest) => Promise<void>
}

interface FormState {
  full_name_en: string
  full_name_np: string
  gender: string
  date_of_birth_ad: string
  date_of_birth_bs: string
  current_grade: string
  current_section: string
  current_faculty: string
  roll_number: string
  emis_student_id: string
  admission_number: string
  phone: string
  email: string
  address_permanent: string
  address_temporary: string
  status: string
  guardian_name: string
  guardian_relation: string
  guardian_phone: string
  guardian_email: string
}

const emptyForm: FormState = {
  full_name_en: "",
  full_name_np: "",
  gender: "male",
  date_of_birth_ad: "",
  date_of_birth_bs: "",
  current_grade: "",
  current_section: "",
  current_faculty: "",
  roll_number: "",
  emis_student_id: "",
  admission_number: "",
  phone: "",
  email: "",
  address_permanent: "",
  address_temporary: "",
  status: "active",
  guardian_name: "",
  guardian_relation: "guardian",
  guardian_phone: "",
  guardian_email: "",
}

const fieldClass = "space-y-1.5"
const labelClass = "text-sm font-medium"
const selectClass = "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"

function optional(value: string): string | undefined {
  const trimmed = value.trim()
  return trimmed || undefined
}

export function StudentEditorDialog({
  open,
  mode,
  student,
  saving,
  onOpenChange,
  onSave,
}: StudentEditorDialogProps) {
  const [form, setForm] = useState<FormState>(() => (
    mode === "create" || !student
      ? emptyForm
      : {
          ...emptyForm,
          full_name_en: student.full_name_en,
          full_name_np: student.full_name_np ?? "",
          gender: student.gender,
          date_of_birth_ad: student.date_of_birth_ad,
          date_of_birth_bs: student.date_of_birth_bs ?? "",
          current_grade: student.current_grade?.toString() ?? "",
          current_section: student.current_section ?? "",
          current_faculty: student.current_faculty ?? "",
          roll_number: student.roll_number?.toString() ?? "",
          emis_student_id: student.emis_student_id ?? "",
          admission_number: student.admission_number ?? "",
          phone: student.phone ?? "",
          email: student.email ?? "",
          address_permanent: student.address_permanent ?? "",
          address_temporary: student.address_temporary ?? "",
          status: student.status,
        }
  ))
  const [photo, setPhoto] = useState<File | null>(null)

  const setField = (field: keyof FormState, value: string) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    const editablePayload = {
      full_name_en: form.full_name_en.trim(),
      full_name_np: optional(form.full_name_np),
      phone: optional(form.phone),
      email: optional(form.email),
      address_permanent: optional(form.address_permanent),
      address_temporary: optional(form.address_temporary),
      current_grade: Number(form.current_grade),
      current_section: optional(form.current_section),
      current_faculty: optional(form.current_faculty),
      roll_number: form.roll_number ? Number(form.roll_number) : undefined,
      status: form.status,
    }

    if (mode === "edit") {
      await onSave({ payload: editablePayload, photo })
      return
    }

    const guardians = form.guardian_name.trim()
      ? [
          {
            relation: form.guardian_relation,
            full_name_en: form.guardian_name.trim(),
            phone: optional(form.guardian_phone),
            email: optional(form.guardian_email),
            is_primary_contact: true,
          },
        ]
      : []

    await onSave({
      payload: {
        ...editablePayload,
        gender: form.gender,
        date_of_birth_ad: form.date_of_birth_ad,
        date_of_birth_bs: optional(form.date_of_birth_bs),
        emis_student_id: optional(form.emis_student_id),
        admission_number: optional(form.admission_number),
        guardians,
      },
      photo,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !saving && onOpenChange(nextOpen)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "Add student" : "Edit student"}</DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "Create the student profile. Fields marked with * are required."
              : "Update the student's current profile and academic placement."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-name">Full name *</label>
              <Input id="student-name" value={form.full_name_en} onChange={(event) => setField("full_name_en", event.target.value)} minLength={2} required />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-name-np">Nepali name</label>
              <Input id="student-name-np" value={form.full_name_np} onChange={(event) => setField("full_name_np", event.target.value)} />
            </div>

            {mode === "create" && (
              <>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="student-gender">Gender *</label>
                  <select id="student-gender" className={selectClass} value={form.gender} onChange={(event) => setField("gender", event.target.value)} required>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="student-dob-ad">Date of birth (AD) *</label>
                  <Input id="student-dob-ad" type="date" value={form.date_of_birth_ad} onChange={(event) => setField("date_of_birth_ad", event.target.value)} required />
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="student-dob-bs">Date of birth (BS)</label>
                  <Input id="student-dob-bs" placeholder="2080-01-01" value={form.date_of_birth_bs} onChange={(event) => setField("date_of_birth_bs", event.target.value)} />
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="student-emis">EMIS ID</label>
                  <Input id="student-emis" value={form.emis_student_id} onChange={(event) => setField("emis_student_id", event.target.value)} />
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="student-admission">Admission number</label>
                  <Input id="student-admission" value={form.admission_number} onChange={(event) => setField("admission_number", event.target.value)} />
                </div>
              </>
            )}

            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-grade">Grade *</label>
              <Input id="student-grade" type="number" min={1} max={12} value={form.current_grade} onChange={(event) => setField("current_grade", event.target.value)} required />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-section">Section</label>
              <Input id="student-section" value={form.current_section} onChange={(event) => setField("current_section", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-roll">Roll number</label>
              <Input id="student-roll" type="number" min={1} value={form.roll_number} onChange={(event) => setField("roll_number", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-faculty">Faculty</label>
              <Input id="student-faculty" placeholder="For Grade 11–12" value={form.current_faculty} onChange={(event) => setField("current_faculty", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-phone">Phone</label>
              <Input id="student-phone" type="tel" value={form.phone} onChange={(event) => setField("phone", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-email">Email</label>
              <Input id="student-email" type="email" value={form.email} onChange={(event) => setField("email", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-address">Permanent address</label>
              <Input id="student-address" value={form.address_permanent} onChange={(event) => setField("address_permanent", event.target.value)} />
            </div>
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-temp-address">Current address</label>
              <Input id="student-temp-address" value={form.address_temporary} onChange={(event) => setField("address_temporary", event.target.value)} />
            </div>
            {mode === "edit" && (
              <div className={fieldClass}>
                <label className={labelClass} htmlFor="student-status">Status</label>
                <select id="student-status" className={selectClass} value={form.status} onChange={(event) => setField("status", event.target.value)}>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="transferred">Transferred</option>
                  <option value="graduated">Graduated</option>
                  <option value="dropped_out">Dropped out</option>
                </select>
              </div>
            )}
            <div className={fieldClass}>
              <label className={labelClass} htmlFor="student-photo">Profile photo</label>
              <Input id="student-photo" type="file" accept="image/jpeg,image/png" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} />
              <p className="text-xs text-muted-foreground">JPEG or PNG, up to 10 MB.</p>
            </div>
          </div>

          {mode === "create" && (
            <fieldset className="rounded-md border p-4">
              <legend className="px-2 text-sm font-semibold">Primary guardian (optional)</legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="guardian-name">Full name</label>
                  <Input id="guardian-name" value={form.guardian_name} onChange={(event) => setField("guardian_name", event.target.value)} />
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="guardian-relation">Relation</label>
                  <select id="guardian-relation" className={selectClass} value={form.guardian_relation} onChange={(event) => setField("guardian_relation", event.target.value)}>
                    {['father', 'mother', 'guardian', 'grandfather', 'grandmother', 'uncle', 'aunt', 'other'].map((relation) => (
                      <option key={relation} value={relation}>{relation.replace('_', ' ')}</option>
                    ))}
                  </select>
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="guardian-phone">Phone</label>
                  <Input id="guardian-phone" type="tel" value={form.guardian_phone} onChange={(event) => setField("guardian_phone", event.target.value)} />
                </div>
                <div className={fieldClass}>
                  <label className={labelClass} htmlFor="guardian-email">Email</label>
                  <Input id="guardian-email" type="email" value={form.guardian_email} onChange={(event) => setField("guardian_email", event.target.value)} />
                </div>
              </div>
            </fieldset>
          )}

          <DialogFooter>
            <DialogClose asChild><Button type="button" variant="outline" disabled={saving}>Cancel</Button></DialogClose>
            <Button type="submit" disabled={saving}>{saving ? "Saving…" : mode === "create" ? "Add student" : "Save changes"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

interface StudentDetailsDialogProps {
  open: boolean
  student?: Student | null
  loading: boolean
  onOpenChange: (open: boolean) => void
}

function Detail({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-sm">{value || "—"}</dd>
    </div>
  )
}

export function StudentDetailsDialog({ open, student, loading, onOpenChange }: StudentDetailsDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Student details</DialogTitle>
          <DialogDescription>Profile, academic placement and guardian information.</DialogDescription>
        </DialogHeader>
        {loading ? (
          <div className="py-12 text-center text-muted-foreground">Loading student…</div>
        ) : student ? (
          <div className="space-y-6">
            <dl className="grid gap-4 sm:grid-cols-3">
              <Detail label="Name" value={student.full_name_en} />
              <Detail label="Nepali name" value={student.full_name_np} />
              <Detail label="Status" value={student.status.replaceAll("_", " ")} />
              <Detail label="EMIS ID" value={student.emis_student_id} />
              <Detail label="Admission no." value={student.admission_number} />
              <Detail label="Roll no." value={student.roll_number} />
              <Detail label="Grade" value={student.current_grade} />
              <Detail label="Section" value={student.current_section} />
              <Detail label="Faculty" value={student.current_faculty} />
              <Detail label="Gender" value={student.gender} />
              <Detail label="DOB (AD)" value={student.date_of_birth_ad} />
              <Detail label="DOB (BS)" value={student.date_of_birth_bs} />
              <Detail label="Phone" value={student.phone} />
              <Detail label="Email" value={student.email} />
              <Detail label="Nationality" value={student.nationality} />
              <Detail label="Permanent address" value={student.address_permanent} />
              <Detail label="Current address" value={student.address_temporary} />
            </dl>
            <div>
              <h3 className="mb-3 text-sm font-semibold">Guardians</h3>
              {student.guardians?.length ? (
                <div className="space-y-2">
                  {student.guardians.map((guardian) => (
                    <div key={guardian.id ?? `${guardian.relation}-${guardian.full_name_en}`} className="rounded-md border p-3 text-sm">
                      <p className="font-medium">{guardian.full_name_en}</p>
                      <p className="text-muted-foreground">{guardian.relation} · {guardian.phone || guardian.email || "No contact provided"}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No guardian information recorded.</p>
              )}
            </div>
          </div>
        ) : (
          <div className="py-12 text-center text-destructive">Unable to load student details.</div>
        )}
      </DialogContent>
    </Dialog>
  )
}
