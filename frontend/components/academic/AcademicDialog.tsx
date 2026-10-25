"use client"

import { FormEvent, useState } from "react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"

export interface AcademicSection { id: string; grade_id: string; name: string; capacity: number; class_teacher_id?: string | null; stream_id?: string | null; is_active: boolean }
export interface AcademicGrade { id: string; grade_number: number; name_en: string; name_np?: string | null; academic_year_bs?: string | null; is_hs: boolean; is_active: boolean; sections: AcademicSection[] }
export interface AcademicSubject { id: string; grade_id: string; code: string; name_en: string; name_np?: string | null; subject_type: string; full_marks: number; pass_marks: number; credit_hours: number; optional_group?: string | null; teacher_id?: string | null; faculty_id?: string | null; stream_ids: string[]; is_active: boolean }
export interface AcademicStream { id: string; faculty_id: string; name_en: string; name_np?: string | null; code: string; is_active: boolean }
export interface AcademicFaculty { id: string; name_en: string; name_np?: string | null; code: string; description?: string | null; max_students: number; is_active: boolean; streams: AcademicStream[] }
export interface TeacherOption { id: string; full_name_en: string }

export type AcademicEntity = "grade" | "section" | "subject" | "faculty" | "stream"
type AcademicItem = AcademicGrade | AcademicSection | AcademicSubject | AcademicFaculty | AcademicStream

const selectClass = "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
const fieldClass = "space-y-1.5"
const labelClass = "text-sm font-medium"

const titles: Record<AcademicEntity, string> = {
  grade: "grade",
  section: "section",
  subject: "subject",
  faculty: "faculty",
  stream: "stream",
}

function textValue(record: Record<string, unknown>, key: string, fallback = "") {
  const value = record[key]
  return value === null || value === undefined ? fallback : String(value)
}

function optional(value: string): string | null {
  return value.trim() || null
}

export function AcademicEditorDialog({ entity, item, parentId, grades, faculties, teachers, saving, onOpenChange, onSave }: {
  entity: AcademicEntity
  item?: AcademicItem | null
  parentId?: string
  grades: AcademicGrade[]
  faculties: AcademicFaculty[]
  teachers: TeacherOption[]
  saving: boolean
  onOpenChange: (open: boolean) => void
  onSave: (payload: Record<string, unknown>) => Promise<void>
}) {
  const record = (item ?? {}) as unknown as Record<string, unknown>
  const [form, setForm] = useState<Record<string, string>>({
    grade_number: textValue(record, "grade_number", "1"),
    name_en: textValue(record, "name_en"),
    name_np: textValue(record, "name_np"),
    academic_year_bs: textValue(record, "academic_year_bs"),
    grade_id: textValue(record, "grade_id", parentId ?? grades[0]?.id ?? ""),
    name: textValue(record, "name", "A"),
    capacity: textValue(record, "capacity", "40"),
    class_teacher_id: textValue(record, "class_teacher_id"),
    stream_id: textValue(record, "stream_id"),
    code: textValue(record, "code"),
    subject_type: textValue(record, "subject_type", "compulsory"),
    full_marks: textValue(record, "full_marks", "100"),
    pass_marks: textValue(record, "pass_marks", "40"),
    credit_hours: textValue(record, "credit_hours", "4"),
    optional_group: textValue(record, "optional_group"),
    teacher_id: textValue(record, "teacher_id"),
    faculty_id: textValue(record, "faculty_id", parentId ?? ""),
    description: textValue(record, "description"),
    max_students: textValue(record, "max_students", "60"),
  })
  const [streamIds, setStreamIds] = useState<string[]>(() => Array.isArray(record.stream_ids) ? record.stream_ids as string[] : [])

  const set = (field: string, value: string) => setForm((current) => ({ ...current, [field]: value }))

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (entity === "grade") await onSave({ grade_number: Number(form.grade_number), name_en: form.name_en.trim(), name_np: optional(form.name_np), academic_year_bs: optional(form.academic_year_bs) })
    if (entity === "section") {
      const grade = grades.find((candidate) => candidate.id === form.grade_id)
      await onSave({ ...(!item && { grade_id: form.grade_id }), name: form.name.trim().toUpperCase(), capacity: Number(form.capacity), class_teacher_id: optional(form.class_teacher_id), stream_id: grade?.is_hs ? optional(form.stream_id) : null })
    }
    if (entity === "subject") {
      const grade = grades.find((candidate) => candidate.id === form.grade_id)
      const higherSecondary = Boolean(grade?.is_hs)
      await onSave({ ...(!item && { grade_id: form.grade_id }), code: form.code.trim().toUpperCase(), name_en: form.name_en.trim(), name_np: optional(form.name_np), subject_type: form.subject_type, full_marks: Number(form.full_marks), pass_marks: Number(form.pass_marks), credit_hours: Number(form.credit_hours), optional_group: form.subject_type === "optional" ? optional(form.optional_group) : null, teacher_id: optional(form.teacher_id), faculty_id: higherSecondary ? optional(form.faculty_id) : null, stream_ids: higherSecondary && form.faculty_id ? streamIds : [] })
    }
    if (entity === "faculty") await onSave({ name_en: form.name_en.trim(), name_np: optional(form.name_np), code: form.code.trim().toUpperCase(), description: optional(form.description), max_students: Number(form.max_students) })
    if (entity === "stream") await onSave({ ...(!item && { faculty_id: form.faculty_id }), name_en: form.name_en.trim(), name_np: optional(form.name_np), code: form.code.trim().toUpperCase() })
  }

  return (
    <Dialog open onOpenChange={(open) => !saving && onOpenChange(open)}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{item ? "Edit" : "Add"} {titles[entity]}</DialogTitle>
          <DialogDescription>Configure this part of the school&apos;s academic structure.</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2">
            {entity === "grade" && <>
              <Field label="Grade number *" id="grade-number"><Input id="grade-number" type="number" min={1} max={12} value={form.grade_number} onChange={(event) => set("grade_number", event.target.value)} required /></Field>
              <Field label="English name *" id="grade-name"><Input id="grade-name" placeholder="Grade 11" value={form.name_en} onChange={(event) => set("name_en", event.target.value)} required /></Field>
              <Field label="Nepali name" id="grade-name-np"><Input id="grade-name-np" value={form.name_np} onChange={(event) => set("name_np", event.target.value)} /></Field>
              <Field label="Academic year (BS)" id="academic-year"><Input id="academic-year" placeholder="2083" value={form.academic_year_bs} onChange={(event) => set("academic_year_bs", event.target.value)} /></Field>
            </>}

            {(entity === "section" || entity === "subject") && !item && <SelectField label="Grade *" id="entity-grade" value={form.grade_id} onChange={(value) => set("grade_id", value)}><option value="">Select grade</option>{grades.map((grade) => <option key={grade.id} value={grade.id}>{grade.name_en}</option>)}</SelectField>}

            {entity === "section" && <>
              <Field label="Section name *" id="section-name"><Input id="section-name" maxLength={10} value={form.name} onChange={(event) => set("name", event.target.value)} required /></Field>
              <Field label="Capacity *" id="section-capacity"><Input id="section-capacity" type="number" min={1} max={100} value={form.capacity} onChange={(event) => set("capacity", event.target.value)} required /></Field>
              <SelectField label="Class teacher" id="class-teacher" value={form.class_teacher_id} onChange={(value) => set("class_teacher_id", value)}><option value="">Not assigned</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.full_name_en}</option>)}</SelectField>
              {(grades.find((grade) => grade.id === form.grade_id)?.is_hs ?? false) && <SelectField label="Faculty / subject combination" id="section-stream" value={form.stream_id} onChange={(value) => set("stream_id", value)}><option value="">General / not assigned</option>{faculties.map((faculty) => <optgroup key={faculty.id} label={faculty.name_en}>{faculty.streams.map((stream) => <option key={stream.id} value={stream.id}>{stream.name_en} ({stream.code})</option>)}</optgroup>)}</SelectField>}
            </>}

            {entity === "subject" && <>
              <Field label="Subject code *" id="subject-code"><Input id="subject-code" maxLength={20} placeholder="ENG-11" value={form.code} onChange={(event) => set("code", event.target.value)} required /></Field>
              <Field label="Subject name *" id="subject-name"><Input id="subject-name" value={form.name_en} onChange={(event) => set("name_en", event.target.value)} required /></Field>
              <Field label="Nepali name" id="subject-name-np"><Input id="subject-name-np" value={form.name_np} onChange={(event) => set("name_np", event.target.value)} /></Field>
              <SelectField label="Subject type *" id="subject-type" value={form.subject_type} onChange={(value) => set("subject_type", value)}><option value="compulsory">Compulsory</option><option value="optional">Optional</option><option value="additional">Additional</option></SelectField>
              {form.subject_type === "optional" && <Field label="Optional group" id="optional-group"><Input id="optional-group" placeholder="Group A, B, or school-defined basket" value={form.optional_group} onChange={(event) => set("optional_group", event.target.value)} /></Field>}
              <Field label="Full marks *" id="full-marks"><Input id="full-marks" type="number" min={1} value={form.full_marks} onChange={(event) => set("full_marks", event.target.value)} required /></Field>
              <Field label="Pass marks *" id="pass-marks"><Input id="pass-marks" type="number" min={1} max={Number(form.full_marks) || undefined} value={form.pass_marks} onChange={(event) => set("pass_marks", event.target.value)} required /></Field>
              <Field label="Credit hours *" id="credit-hours"><Input id="credit-hours" type="number" min={1} value={form.credit_hours} onChange={(event) => set("credit_hours", event.target.value)} required /></Field>
              <SelectField label="Subject teacher" id="subject-teacher" value={form.teacher_id} onChange={(value) => set("teacher_id", value)}><option value="">Not assigned</option>{teachers.map((teacher) => <option key={teacher.id} value={teacher.id}>{teacher.full_name_en}</option>)}</SelectField>
              {(grades.find((grade) => grade.id === form.grade_id)?.is_hs ?? false) && <>
                <SelectField label="Faculty / programme" id="subject-faculty" value={form.faculty_id} onChange={(value) => { set("faculty_id", value); setStreamIds([]) }}><option value="">Common to all faculties</option>{faculties.map((faculty) => <option key={faculty.id} value={faculty.id}>{faculty.name_en}</option>)}</SelectField>
                {form.faculty_id && <div className="space-y-2 sm:col-span-2"><p className={labelClass}>Applicable streams / combinations</p><p className="text-xs text-muted-foreground">Leave all unchecked when the subject applies to every stream in this faculty.</p><div className="grid gap-2 sm:grid-cols-2">{(faculties.find((faculty) => faculty.id === form.faculty_id)?.streams ?? []).map((stream) => <label key={stream.id} className="flex items-center gap-2 rounded-md border p-3 text-sm"><input type="checkbox" checked={streamIds.includes(stream.id)} onChange={(event) => setStreamIds((current) => event.target.checked ? [...current, stream.id] : current.filter((id) => id !== stream.id))} />{stream.name_en} ({stream.code})</label>)}</div></div>}
              </>}
            </>}

            {(entity === "faculty" || entity === "stream") && <>
              {entity === "stream" && !item && <SelectField label="Faculty *" id="stream-faculty" value={form.faculty_id} onChange={(value) => set("faculty_id", value)}><option value="">Select faculty</option>{faculties.map((faculty) => <option key={faculty.id} value={faculty.id}>{faculty.name_en}</option>)}</SelectField>}
              <Field label="English name *" id="academic-name"><Input id="academic-name" list={entity === "faculty" ? "faculty-presets" : "stream-presets"} value={form.name_en} onChange={(event) => set("name_en", event.target.value)} required /><datalist id={entity === "faculty" ? "faculty-presets" : "stream-presets"}>{(entity === "faculty" ? ["Science", "Management", "Law", "Humanities", "Education"] : ["PCM (Physics, Chemistry, Mathematics)", "PCB (Physics, Chemistry, Biology)", "Computer Science", "Business Mathematics", "Hotel Management"]).map((suggestion) => <option key={suggestion} value={suggestion} />)}</datalist></Field>
              <Field label="Nepali name" id="academic-name-np"><Input id="academic-name-np" value={form.name_np} onChange={(event) => set("name_np", event.target.value)} /></Field>
              <Field label="Code *" id="academic-code"><Input id="academic-code" maxLength={20} value={form.code} onChange={(event) => set("code", event.target.value)} required /></Field>
              {entity === "faculty" && <>
                <Field label="Maximum students *" id="max-students"><Input id="max-students" type="number" min={1} value={form.max_students} onChange={(event) => set("max_students", event.target.value)} required /></Field>
                <Field label="Description" id="faculty-description" wide><Input id="faculty-description" value={form.description} onChange={(event) => set("description", event.target.value)} /></Field>
              </>}
            </>}
          </div>
          <DialogFooter><DialogClose asChild><Button type="button" variant="outline" disabled={saving}>Cancel</Button></DialogClose><Button type="submit" disabled={saving}>{saving ? "Saving..." : item ? "Save changes" : `Add ${titles[entity]}`}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

function Field({ label, id, wide, children }: { label: string; id: string; wide?: boolean; children: React.ReactNode }) {
  return <div className={`${fieldClass} ${wide ? "sm:col-span-2" : ""}`}><label className={labelClass} htmlFor={id}>{label}</label>{children}</div>
}

function SelectField({ label, id, value, onChange, children }: { label: string; id: string; value: string; onChange: (value: string) => void; children: React.ReactNode }) {
  return <div className={fieldClass}><label className={labelClass} htmlFor={id}>{label}</label><select id={id} className={selectClass} value={value} onChange={(event) => onChange(event.target.value)} required={label.includes("*")}>{children}</select></div>
}
