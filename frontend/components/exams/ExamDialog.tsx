"use client"

import { FormEvent, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"

import { AcademicGrade, AcademicSubject } from "@/components/academic/AcademicDialog"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { apiClient } from "@/lib/api/client"

export interface ExamSubject {
  id: string
  exam_id: string
  subject_id: string
  full_marks: number
  pass_marks: number
  exam_date_ad?: string | null
  start_time?: string | null
  end_time?: string | null
}

export interface Exam {
  id: string
  name: string
  exam_type: string
  academic_year_bs: string
  grade: number
  start_date_ad?: string | null
  end_date_ad?: string | null
  status: string
  is_locked: boolean
  subjects: ExamSubject[]
  created_at: string
  updated_at: string
}

const selectClass = "h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"

export function ExamDialog({ exam, grades, saving, onClose, onSave }: {
  exam?: Exam | null
  grades: AcademicGrade[]
  saving: boolean
  onClose: () => void
  onSave: (payload: Record<string, unknown>) => Promise<void>
}) {
  const [name, setName] = useState(exam?.name ?? "")
  const [examType, setExamType] = useState(exam?.exam_type ?? "terminal")
  const [academicYear, setAcademicYear] = useState(exam?.academic_year_bs ?? grades[0]?.academic_year_bs ?? "2083")
  const [gradeId, setGradeId] = useState(grades.find((grade) => grade.grade_number === exam?.grade)?.id ?? grades[0]?.id ?? "")
  const [startDate, setStartDate] = useState(exam?.start_date_ad ?? "")
  const [endDate, setEndDate] = useState(exam?.end_date_ad ?? "")
  const [selected, setSelected] = useState<Record<string, boolean>>({})
  const [configuration, setConfiguration] = useState<Record<string, { full: string; pass: string; date: string; start: string; end: string }>>({})

  const selectedGrade = grades.find((grade) => grade.id === gradeId)
  const subjectsQuery = useQuery({
    queryKey: ["academic", "subjects", gradeId],
    queryFn: async () => {
      const response = await apiClient.academic.subjects.list(gradeId)
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load subjects")
      return response.data as AcademicSubject[]
    },
    enabled: Boolean(gradeId && !exam),
  })
  const subjects = subjectsQuery.data ?? []

  const valuesFor = (subject: AcademicSubject) => configuration[subject.id] ?? {
    full: String(subject.full_marks),
    pass: String(subject.pass_marks),
    date: "",
    start: "10:00",
    end: "13:00",
  }

  const updateSubject = (subject: AcademicSubject, field: "full" | "pass" | "date" | "start" | "end", value: string) => {
    setConfiguration((current) => ({ ...current, [subject.id]: { ...valuesFor(subject), [field]: value } }))
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (exam) {
      await onSave({ name: name.trim(), start_date_ad: startDate || null, end_date_ad: endDate || null })
      return
    }
    const examSubjects = subjects.filter((subject) => selected[subject.id] !== false).map((subject) => {
      const values = valuesFor(subject)
      return {
        subject_id: subject.id,
        full_marks: Number(values.full),
        pass_marks: Number(values.pass),
        exam_date_ad: values.date || null,
        start_time: values.start ? `${values.start}:00` : null,
        end_time: values.end ? `${values.end}:00` : null,
      }
    })
    await onSave({ name: name.trim(), exam_type: examType, academic_year_bs: academicYear.trim(), grade: selectedGrade?.grade_number, start_date_ad: startDate || null, end_date_ad: endDate || null, subjects: examSubjects })
  }

  return <Dialog open onOpenChange={(open) => !open && !saving && onClose()}>
    <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-4xl">
      <DialogHeader><DialogTitle>{exam ? "Edit exam" : "Create exam"}</DialogTitle><DialogDescription>{exam ? "Draft exam details can be corrected before scheduling." : "Choose the grade, schedule, and subjects included in this examination."}</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Exam name *"><Input minLength={3} value={name} onChange={(event) => setName(event.target.value)} placeholder="First Terminal Exam 2083" required /></Field>
          {!exam && <Field label="Exam type *"><select className={selectClass} value={examType} onChange={(event) => setExamType(event.target.value)}><option value="terminal">Terminal</option><option value="unit_test">Unit test</option><option value="final">Final</option><option value="pre_board">Pre-board</option><option value="send_up">Send-up</option></select></Field>}
          {!exam && <Field label="Academic year (BS) *"><Input value={academicYear} onChange={(event) => setAcademicYear(event.target.value)} required /></Field>}
          {!exam && <Field label="Grade *"><select className={selectClass} value={gradeId} onChange={(event) => { setGradeId(event.target.value); setSelected({}); setConfiguration({}) }} required><option value="">Select grade</option>{grades.map((grade) => <option key={grade.id} value={grade.id}>{grade.name_en}</option>)}</select></Field>}
          <Field label="Start date (AD)"><Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></Field>
          <Field label="End date (AD)"><Input type="date" min={startDate} value={endDate} onChange={(event) => setEndDate(event.target.value)} /></Field>
        </div>

        {!exam && <div className="space-y-3">
          <div><h3 className="font-medium">Exam subjects</h3><p className="text-sm text-muted-foreground">All active subjects are selected initially. Uncheck any subject not included.</p></div>
          {subjectsQuery.isLoading ? <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="animate-spin" />Loading subjects...</p> : subjectsQuery.error ? <p className="py-6 text-sm text-destructive">{subjectsQuery.error.message}</p> : subjects.length === 0 ? <p className="rounded-md border border-dashed p-5 text-sm text-muted-foreground">Configure subjects for this grade in Academic Structure first.</p> : <div className="space-y-3">{subjects.map((subject) => {
            const values = valuesFor(subject)
            const checked = selected[subject.id] !== false
            return <div key={subject.id} className={`rounded-lg border p-3 ${checked ? "" : "opacity-60"}`}>
              <label className="flex items-center gap-3 font-medium"><input type="checkbox" checked={checked} onChange={(event) => setSelected((current) => ({ ...current, [subject.id]: event.target.checked }))} />{subject.name_en} <span className="text-xs font-normal text-muted-foreground">{subject.code}</span></label>
              {checked && <div className="mt-3 grid gap-3 sm:grid-cols-5"><Field label="Full marks"><Input type="number" min={1} max={100} value={values.full} onChange={(event) => updateSubject(subject, "full", event.target.value)} required /></Field><Field label="Pass marks"><Input type="number" min={1} max={Number(values.full) || 100} value={values.pass} onChange={(event) => updateSubject(subject, "pass", event.target.value)} required /></Field><Field label="Exam date"><Input type="date" value={values.date} onChange={(event) => updateSubject(subject, "date", event.target.value)} /></Field><Field label="Starts"><Input type="time" value={values.start} onChange={(event) => updateSubject(subject, "start", event.target.value)} /></Field><Field label="Ends"><Input type="time" value={values.end} onChange={(event) => updateSubject(subject, "end", event.target.value)} /></Field></div>}
            </div>
          })}</div>}
        </div>}

        <DialogFooter><Button type="button" variant="outline" onClick={onClose} disabled={saving}>Cancel</Button><Button type="submit" disabled={saving || (!exam && subjects.length === 0)}>{saving && <Loader2 className="animate-spin" />}{exam ? "Save changes" : "Create exam"}</Button></DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="space-y-1.5"><span className="text-sm font-medium">{label}</span>{children}</label> }
