"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Award, Calculator, CheckCircle2, Edit, Eye, FilePlus2, Loader2, Play, Save, Send, Trash2 } from "lucide-react"
import { toast } from "sonner"

import { AcademicGrade, AcademicSubject } from "@/components/academic/AcademicDialog"
import { Exam, ExamDialog, ExamSubject } from "@/components/exams/ExamDialog"
import { Student } from "@/components/students/StudentDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { apiClient } from "@/lib/api/client"

type Tab = "exams" | "marks" | "results"

interface ExamList { exams: Exam[]; total: number; page: number; limit: number }
interface StudentList { students: Student[]; total: number }
interface Mark { id: string; student_id: string; marks_obtained: number; is_absent: boolean; grade_point?: number | null; remarks?: string | null }
interface MarkList { exam_subject_id: string; subject_id: string; full_marks: number; pass_marks: number; marks: Mark[]; total: number }
interface MarkValue { marks: string; absent: boolean; remarks: string }
interface Result { id: string; student_id: string; total_marks?: number | null; percentage?: number | null; gpa?: number | null; division?: string | null; rank?: number | null; status: string }
interface ResultList { exam_id: string; exam_name: string; grade: number; results: Result[]; total: number }
interface ReportSubject { subject_id: string; subject_name?: string | null; full_marks: number; pass_marks: number; marks_obtained: number; is_absent: boolean; grade_point?: number | null; remarks?: string | null }
interface ReportCard { student_id: string; student_name?: string | null; exam_name: string; exam_type: string; academic_year_bs: string; grade: number; subjects: ReportSubject[]; total_marks?: number | null; full_marks_total?: number | null; percentage?: number | null; gpa?: number | null; division?: string | null; rank?: number | null; status: string; grading_system: string }

const selectClass = "h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
const statusOrder: Record<string, string | undefined> = { draft: "scheduled", scheduled: "ongoing", ongoing: "completed" }
const statusAction: Record<string, string> = { draft: "Schedule", scheduled: "Start exam", ongoing: "Complete" }

function humanize(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase()) }

export default function ExamsPage() {
  const [tab, setTab] = useState<Tab>("exams")
  const [gradeFilter, setGradeFilter] = useState("")
  const [statusFilter, setStatusFilter] = useState("")
  const [selectedExamId, setSelectedExamId] = useState("")
  const [selectedSubjectId, setSelectedSubjectId] = useState("")
  const [sectionName, setSectionName] = useState("")
  const [editor, setEditor] = useState<{ exam: Exam | null } | null>(null)
  const [markChanges, setMarkChanges] = useState<Record<string, Record<string, MarkValue>>>({})
  const [reportStudentId, setReportStudentId] = useState("")
  const queryClient = useQueryClient()

  const gradesQuery = useQuery({
    queryKey: ["academic", "grades"],
    queryFn: async () => {
      const response = await apiClient.academic.grades.list()
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load grades")
      return response.data as AcademicGrade[]
    },
  })

  const examsQuery = useQuery({
    queryKey: ["exams", gradeFilter, statusFilter],
    queryFn: async () => {
      const response = await apiClient.exams.list({ page: 1, limit: 100, grade: gradeFilter ? Number(gradeFilter) : undefined, status: statusFilter || undefined })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load exams")
      return response.data as ExamList
    },
  })

  const grades = gradesQuery.data ?? []
  const exams = examsQuery.data?.exams ?? []
  const effectiveExamId = exams.some((exam) => exam.id === selectedExamId) ? selectedExamId : exams[0]?.id ?? ""
  const selectedExam = exams.find((exam) => exam.id === effectiveExamId)
  const examGrade = grades.find((grade) => grade.grade_number === selectedExam?.grade)
  const sections = examGrade?.sections.filter((section) => section.is_active) ?? []
  const effectiveSection = sections.some((section) => section.name === sectionName) ? sectionName : sections[0]?.name ?? ""
  const effectiveSubjectId = selectedExam?.subjects.some((subject) => subject.id === selectedSubjectId) ? selectedSubjectId : selectedExam?.subjects[0]?.id ?? ""
  const selectedExamSubject = selectedExam?.subjects.find((subject) => subject.id === effectiveSubjectId)

  const subjectsQuery = useQuery({
    queryKey: ["academic", "subjects", examGrade?.id],
    queryFn: async () => {
      const response = await apiClient.academic.subjects.list(examGrade!.id)
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load subject names")
      return response.data as AcademicSubject[]
    },
    enabled: Boolean(examGrade?.id),
  })
  const academicSubjects = subjectsQuery.data ?? []
  const subjectName = (subject: ExamSubject) => academicSubjects.find((item) => item.id === subject.subject_id)?.name_en ?? "Subject"

  const rosterQuery = useQuery({
    queryKey: ["exams", "roster", selectedExam?.grade, effectiveSection],
    queryFn: async () => {
      const response = await apiClient.students.list({ page: 1, limit: 100, grade: selectedExam!.grade, section: effectiveSection, status: "active" })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load students")
      return response.data as StudentList
    },
    enabled: tab === "marks" && Boolean(selectedExam && effectiveSection),
  })

  const allStudentsQuery = useQuery({
    queryKey: ["exams", "grade-students", selectedExam?.grade],
    queryFn: async () => {
      const response = await apiClient.students.list({ page: 1, limit: 100, grade: selectedExam!.grade, status: "active" })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load student names")
      return response.data as StudentList
    },
    enabled: tab === "results" && Boolean(selectedExam),
  })

  const marksQuery = useQuery({
    queryKey: ["exams", "marks", effectiveSubjectId],
    queryFn: async () => {
      const response = await apiClient.exams.getMarks(effectiveSubjectId)
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load saved marks")
      return response.data as MarkList
    },
    enabled: tab === "marks" && Boolean(effectiveSubjectId),
  })

  const resultsQuery = useQuery({
    queryKey: ["exams", "results", effectiveExamId],
    queryFn: async () => {
      const response = await apiClient.exams.getResults(effectiveExamId, { page: 1, limit: 200 })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load results")
      return response.data as ResultList
    },
    enabled: tab === "results" && Boolean(effectiveExamId),
  })

  const saveExam = useMutation({
    mutationFn: async ({ exam, payload }: { exam: Exam | null; payload: Record<string, unknown> }) => {
      const response = exam ? await apiClient.exams.update(exam.id, payload) : await apiClient.exams.create(payload)
      if (!response.success) throw new Error(response.error?.message ?? `Unable to ${exam ? "update" : "create"} exam`)
      return Boolean(exam)
    },
    onSuccess: async (editing) => { toast.success(editing ? "Exam updated" : "Exam created"); setEditor(null); await queryClient.invalidateQueries({ queryKey: ["exams"] }) },
    onError: (error) => toast.error(error.message),
  })

  const deleteExam = useMutation({
    mutationFn: async (exam: Exam) => { const response = await apiClient.exams.delete(exam.id); if (!response.success) throw new Error(response.error?.message ?? "Unable to delete exam") },
    onSuccess: async () => { toast.success("Draft exam deleted"); setSelectedExamId(""); await queryClient.invalidateQueries({ queryKey: ["exams"] }) },
    onError: (error) => toast.error(error.message),
  })

  const changeStatus = useMutation({
    mutationFn: async ({ exam, status }: { exam: Exam; status: string }) => { const response = await apiClient.exams.updateStatus(exam.id, status); if (!response.success) throw new Error(response.error?.message ?? "Unable to change exam status") },
    onSuccess: async () => { toast.success("Exam status updated"); await queryClient.invalidateQueries({ queryKey: ["exams"] }) },
    onError: (error) => toast.error(error.message),
  })

  const existingMarks = useMemo(() => new Map((marksQuery.data?.marks ?? []).map((mark) => [mark.student_id, mark])), [marksQuery.data])
  const markKey = `${effectiveSubjectId}:${effectiveSection}`
  const activeChanges = markChanges[markKey] ?? {}
  const markFor = (studentId: string): MarkValue => activeChanges[studentId] ?? (() => {
    const existing = existingMarks.get(studentId)
    return { marks: existing ? String(existing.marks_obtained) : "", absent: existing?.is_absent ?? false, remarks: existing?.remarks ?? "" }
  })()
  const updateMark = (studentId: string, patch: Partial<MarkValue>) => setMarkChanges((current) => ({ ...current, [markKey]: { ...(current[markKey] ?? {}), [studentId]: { ...markFor(studentId), ...patch } } }))

  const saveMarks = useMutation({
    mutationFn: async () => {
      const students = rosterQuery.data?.students ?? []
      if (!selectedExamSubject || !students.length) throw new Error("Select a subject and a section with students")
      for (const student of students) {
        const value = markFor(student.id)
        if (!value.absent && (value.marks === "" || Number(value.marks) > Number(selectedExamSubject.full_marks))) throw new Error(`Enter valid marks for ${student.full_name_en}`)
      }
      const response = await apiClient.exams.enterMarks({ exam_subject_id: selectedExamSubject.id, entries: students.map((student) => { const value = markFor(student.id); return { student_id: student.id, marks_obtained: value.absent ? null : Number(value.marks), is_absent: value.absent, remarks: value.remarks.trim() || null } }) })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to save marks")
    },
    onSuccess: async () => { toast.success("Marks saved successfully"); setMarkChanges((current) => { const next = { ...current }; delete next[markKey]; return next }); await queryClient.invalidateQueries({ queryKey: ["exams", "marks"] }) },
    onError: (error) => toast.error(error.message),
  })

  const calculateResults = useMutation({
    mutationFn: async (exam: Exam) => { const response = await apiClient.exams.calculate(exam.id); if (!response.success) throw new Error(response.error?.message ?? "Unable to calculate results") },
    onSuccess: async () => { toast.success("Results calculated"); await queryClient.invalidateQueries({ queryKey: ["exams", "results"] }) },
    onError: (error) => toast.error(error.message),
  })

  const publishResults = useMutation({
    mutationFn: async (exam: Exam) => { const response = await apiClient.exams.publish(exam.id); if (!response.success) throw new Error(response.error?.message ?? "Unable to publish results") },
    onSuccess: async () => { toast.success("Results published and marks locked"); await Promise.all([queryClient.invalidateQueries({ queryKey: ["exams"] }), queryClient.invalidateQueries({ queryKey: ["exams", "results"] })]) },
    onError: (error) => toast.error(error.message),
  })

  const reportQuery = useQuery({
    queryKey: ["exams", "report-card", reportStudentId, effectiveExamId],
    queryFn: async () => { const response = await apiClient.exams.getReportCard(reportStudentId, effectiveExamId); if (!response.success) throw new Error(response.error?.message ?? "Unable to load report card"); return response.data as ReportCard },
    enabled: Boolean(reportStudentId && effectiveExamId),
  })

  const studentNames = useMemo(() => new Map((allStudentsQuery.data?.students ?? []).map((student) => [student.id, student.full_name_en])), [allStudentsQuery.data])
  const resultSummary = (resultsQuery.data?.results ?? []).reduce((summary, result) => ({ ...summary, [result.status]: (summary[result.status] ?? 0) + 1 }), {} as Record<string, number>)
  const busy = saveExam.isPending || deleteExam.isPending || changeStatus.isPending

  return <div className="space-y-6">
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"><div><h1 className="text-2xl font-semibold tracking-tight">Exams &amp; Results</h1><p className="text-muted-foreground">Plan examinations, enter marks, calculate grades, and publish report cards.</p></div><Button onClick={() => setEditor({ exam: null })}><FilePlus2 />Create exam</Button></div>

    <div className="section-tabs" role="group" aria-label="Exam sections"><Button  data-active={tab === "exams"} aria-pressed={tab === "exams"} variant={tab === "exams" ? "secondary" : "ghost"} onClick={() => setTab("exams")}>Exams</Button><Button  data-active={tab === "marks"} aria-pressed={tab === "marks"} variant={tab === "marks" ? "secondary" : "ghost"} onClick={() => setTab("marks")}>Marks entry</Button><Button  data-active={tab === "results"} aria-pressed={tab === "results"} variant={tab === "results" ? "secondary" : "ghost"} onClick={() => setTab("results")}>Results</Button></div>

    <Card><CardContent className="grid gap-4 pt-6 sm:grid-cols-2 lg:grid-cols-4">
      <Field label="Exam"><select className={`${selectClass} w-full`} value={effectiveExamId} onChange={(event) => { setSelectedExamId(event.target.value); setSelectedSubjectId(""); setSectionName("") }}><option value="">Select exam</option>{exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.name} · Grade {exam.grade}</option>)}</select></Field>
      {tab === "exams" ? <><Field label="Filter by grade"><select className={`${selectClass} w-full`} value={gradeFilter} onChange={(event) => setGradeFilter(event.target.value)}><option value="">All grades</option>{grades.map((grade) => <option key={grade.id} value={grade.grade_number}>{grade.name_en}</option>)}</select></Field><Field label="Filter by status"><select className={`${selectClass} w-full`} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All statuses</option>{["draft", "scheduled", "ongoing", "completed", "published"].map((status) => <option key={status} value={status}>{humanize(status)}</option>)}</select></Field></> : <><Field label="Subject"><select className={`${selectClass} w-full`} value={effectiveSubjectId} onChange={(event) => setSelectedSubjectId(event.target.value)} disabled={!selectedExam}><option value="">Select subject</option>{selectedExam?.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subjectName(subject)}</option>)}</select></Field>{tab === "marks" && <Field label="Section"><select className={`${selectClass} w-full`} value={effectiveSection} onChange={(event) => setSectionName(event.target.value)}><option value="">Select section</option>{sections.map((section) => <option key={section.id} value={section.name}>Section {section.name}</option>)}</select></Field>}</>}
    </CardContent></Card>

    {examsQuery.isLoading || gradesQuery.isLoading ? <Card><Empty loading text="Loading exams..." /></Card> : examsQuery.error || gradesQuery.error ? <Card><Empty error={(examsQuery.error || gradesQuery.error)!.message} /></Card> : tab === "exams" ? <Card><CardHeader><CardTitle>Exam schedule</CardTitle></CardHeader><CardContent>{exams.length === 0 ? <Empty text="No exams match the selected filters." /> : <div className="overflow-x-auto"><table className="w-full min-w-[900px]"><thead><tr className="border-b"><Th>Exam</Th><Th>Grade</Th><Th>Academic year</Th><Th>Schedule</Th><Th>Subjects</Th><Th>Status</Th><Th align="right">Actions</Th></tr></thead><tbody>{exams.map((exam) => <tr key={exam.id} className="border-b last:border-0 hover:bg-accent/40"><Td><p className="font-medium">{exam.name}</p><p className="text-xs text-muted-foreground">{humanize(exam.exam_type)}</p></Td><Td>Grade {exam.grade}</Td><Td>{exam.academic_year_bs} BS</Td><Td>{exam.start_date_ad || "Not set"}{exam.end_date_ad ? ` – ${exam.end_date_ad}` : ""}</Td><Td>{exam.subjects.length}</Td><Td><Status value={exam.status} /></Td><Td align="right"><div className="flex justify-end gap-1">{exam.status === "draft" && <><Button size="icon" variant="ghost" aria-label={`Edit ${exam.name}`} onClick={() => setEditor({ exam })}><Edit /></Button><Button size="icon" variant="ghost" aria-label={`Delete ${exam.name}`} onClick={() => window.confirm(`Delete draft exam “${exam.name}”?`) && deleteExam.mutate(exam)}><Trash2 className="text-destructive" /></Button></>}{statusOrder[exam.status] && <Button size="sm" variant="outline" disabled={busy} onClick={() => changeStatus.mutate({ exam, status: statusOrder[exam.status]! })}>{exam.status === "scheduled" ? <Play /> : <CheckCircle2 />}{statusAction[exam.status]}</Button>}{exam.status === "completed" && <Button size="sm" variant="outline" onClick={() => { setSelectedExamId(exam.id); setTab("results") }}><Award />Results</Button>}{exam.status === "published" && <Button size="sm" variant="outline" onClick={() => { setSelectedExamId(exam.id); setTab("results") }}><Eye />View</Button>}</div></Td></tr>)}</tbody></table></div>}</CardContent></Card>
    : tab === "marks" ? <Card><CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Marks entry</CardTitle><p className="mt-1 text-sm text-muted-foreground">{selectedExamSubject ? `${subjectName(selectedExamSubject)} · ${selectedExamSubject.full_marks} full marks · ${selectedExamSubject.pass_marks} pass marks` : "Select an exam and subject."}</p></div><Button disabled={!rosterQuery.data?.students.length || selectedExam?.is_locked || saveMarks.isPending} onClick={() => saveMarks.mutate()}>{saveMarks.isPending ? <Loader2 className="animate-spin" /> : <Save />}Save marks</Button></CardHeader><CardContent>{!selectedExam ? <Empty text="Select an exam to enter marks." /> : selectedExam.is_locked ? <Empty text="This exam is published and its marks are locked." /> : !effectiveSection ? <Empty text="Configure a section for this grade in Academic Structure." /> : rosterQuery.isLoading || marksQuery.isLoading ? <Empty loading text="Loading mark sheet..." /> : rosterQuery.error || marksQuery.error ? <Empty error={(rosterQuery.error || marksQuery.error)!.message} /> : !rosterQuery.data?.students.length ? <Empty text="No active students are assigned to this section." /> : <div className="overflow-x-auto"><table className="w-full min-w-[780px]"><thead><tr className="border-b"><Th>Roll</Th><Th>Student</Th><Th>Marks</Th><Th>Absent</Th><Th>Remarks</Th></tr></thead><tbody>{rosterQuery.data.students.map((student) => { const value = markFor(student.id); return <tr key={student.id} className="border-b last:border-0"><Td>{student.roll_number ?? "—"}</Td><Td strong>{student.full_name_en}</Td><Td><Input className="w-28" aria-label={`Marks for ${student.full_name_en}`} type="number" min={0} max={selectedExamSubject?.full_marks} step="0.01" disabled={value.absent} value={value.absent ? "" : value.marks} onChange={(event) => updateMark(student.id, { marks: event.target.value })} /></Td><Td><label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={value.absent} onChange={(event) => updateMark(student.id, { absent: event.target.checked })} />Absent</label></Td><Td><Input maxLength={500} placeholder="Optional remark" value={value.remarks} onChange={(event) => updateMark(student.id, { remarks: event.target.value })} /></Td></tr> })}</tbody></table></div>}</CardContent></Card>
    : <div className="space-y-4"><div className="pastel-summary grid grid-cols-2 gap-4 sm:grid-cols-4"><Summary label="Students" value={resultsQuery.data?.total ?? 0} /><Summary label="Passed" value={resultSummary.pass ?? 0} tone="text-emerald-600" /><Summary label="Failed" value={resultSummary.fail ?? 0} tone="text-red-600" /><Summary label="Absent" value={resultSummary.absent ?? 0} tone="text-amber-600" /></div><Card><CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Calculated results</CardTitle><p className="mt-1 text-sm text-muted-foreground">Grades 1–10 use GPA; Grades 11–12 use percentage and division.</p></div><div className="flex flex-wrap gap-2">{selectedExam && selectedExam.status !== "published" && <Button variant="outline" disabled={calculateResults.isPending} onClick={() => calculateResults.mutate(selectedExam)}>{calculateResults.isPending ? <Loader2 className="animate-spin" /> : <Calculator />}Calculate</Button>}{selectedExam?.status === "completed" && <Button disabled={!resultsQuery.data?.total || publishResults.isPending} onClick={() => window.confirm("Publish these results? Marks will be locked permanently.") && publishResults.mutate(selectedExam)}>{publishResults.isPending ? <Loader2 className="animate-spin" /> : <Send />}Publish results</Button>}</div></CardHeader><CardContent>{!selectedExam ? <Empty text="Select an exam to view results." /> : resultsQuery.isLoading || allStudentsQuery.isLoading ? <Empty loading text="Loading results..." /> : resultsQuery.error || allStudentsQuery.error ? <Empty error={(resultsQuery.error || allStudentsQuery.error)!.message} /> : !resultsQuery.data?.results.length ? <Empty text="No calculated results yet. Enter every subject’s marks, then calculate results." /> : <div className="overflow-x-auto"><table className="w-full min-w-[760px]"><thead><tr className="border-b"><Th>Rank</Th><Th>Student</Th><Th>Total</Th><Th>{selectedExam.grade >= 11 ? "Percentage" : "GPA"}</Th><Th>Division</Th><Th>Status</Th><Th align="right">Report card</Th></tr></thead><tbody>{resultsQuery.data.results.map((result) => <tr key={result.id} className="border-b last:border-0"><Td>{result.rank ?? "—"}</Td><Td strong>{studentNames.get(result.student_id) ?? result.student_id.slice(0, 8)}</Td><Td>{result.total_marks ?? "—"}</Td><Td>{selectedExam.grade >= 11 ? result.percentage != null ? `${result.percentage}%` : "—" : result.gpa ?? "—"}</Td><Td>{result.division ? humanize(result.division) : "—"}</Td><Td><Status value={result.status} /></Td><Td align="right"><Button size="sm" variant="outline" onClick={() => setReportStudentId(result.student_id)}><Eye />View</Button></Td></tr>)}</tbody></table></div>}</CardContent></Card></div>}

    {editor && <ExamDialog key={editor.exam?.id ?? "new"} exam={editor.exam} grades={grades} saving={saveExam.isPending} onClose={() => setEditor(null)} onSave={async (payload) => { await saveExam.mutateAsync({ exam: editor.exam, payload }) }} />}
    <Dialog open={Boolean(reportStudentId)} onOpenChange={(open) => !open && setReportStudentId("")}><DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl"><DialogHeader><DialogTitle>Student report card</DialogTitle><DialogDescription>Subject marks and calculated result for the selected examination.</DialogDescription></DialogHeader>{reportQuery.isLoading ? <Empty loading text="Loading report card..." /> : reportQuery.error ? <Empty error={reportQuery.error.message} /> : reportQuery.data && <ReportCardView report={reportQuery.data} />}</DialogContent></Dialog>
  </div>
}

function ReportCardView({ report }: { report: ReportCard }) { return <div className="space-y-5"><div className="rounded-lg border p-4"><h3 className="text-lg font-semibold">{report.student_name ?? "Student"}</h3><p className="text-sm text-muted-foreground">{report.exam_name} · Grade {report.grade} · {report.academic_year_bs} BS</p></div><div className="pastel-summary grid grid-cols-2 gap-3 sm:grid-cols-4"><Summary label="Total" value={`${report.total_marks ?? 0}/${report.full_marks_total ?? 0}`} /><Summary label={report.grading_system === "gpa" ? "GPA" : "Percentage"} value={report.grading_system === "gpa" ? report.gpa ?? "—" : `${report.percentage ?? 0}%`} /><Summary label="Rank" value={report.rank ?? "—"} /><Summary label="Result" value={humanize(report.status)} tone={report.status === "pass" ? "text-emerald-600" : "text-red-600"} /></div><div className="overflow-x-auto"><table className="w-full"><thead><tr className="border-b"><Th>Subject</Th><Th>Full</Th><Th>Pass</Th><Th>Obtained</Th><Th>Grade point</Th><Th>Remarks</Th></tr></thead><tbody>{report.subjects.map((subject) => <tr key={subject.subject_id} className="border-b last:border-0"><Td strong>{subject.subject_name ?? "Subject"}</Td><Td>{subject.full_marks}</Td><Td>{subject.pass_marks}</Td><Td>{subject.is_absent ? "Absent" : subject.marks_obtained}</Td><Td>{subject.grade_point ?? "—"}</Td><Td>{subject.remarks || "—"}</Td></tr>)}</tbody></table></div></div> }
function Status({ value }: { value: string }) { const tone = value === "published" || value === "pass" ? "bg-emerald-100 text-emerald-800" : value === "fail" ? "bg-red-100 text-red-800" : value === "absent" ? "bg-amber-100 text-amber-800" : "bg-muted text-muted-foreground"; return <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>{humanize(value)}</span> }
function Summary({ label, value, tone = "" }: { label: string; value: number | string; tone?: string }) { return <Card><CardContent className="pt-5"><p className="text-sm text-muted-foreground">{label}</p><p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p></CardContent></Card> }
function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="space-y-1.5"><span className="text-sm font-medium">{label}</span>{children}</label> }
function Empty({ text, error, loading = false }: { text?: string; error?: string; loading?: boolean }) { return <CardContent className={`flex items-center justify-center gap-2 py-12 text-center text-sm ${error ? "text-destructive" : "text-muted-foreground"}`}>{loading && <Loader2 className="animate-spin" />}{error ?? text}</CardContent> }
function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) { return <th className={`px-3 py-3 text-sm font-medium ${align === "right" ? "text-right" : "text-left"}`}>{children}</th> }
function Td({ children, align = "left", strong = false }: { children: React.ReactNode; align?: "left" | "right"; strong?: boolean }) { return <td className={`px-3 py-3 text-sm ${align === "right" ? "text-right" : "text-left"} ${strong ? "font-medium" : ""}`}>{children}</td> }
