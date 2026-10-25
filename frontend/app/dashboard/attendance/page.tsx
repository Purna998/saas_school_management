"use client"

import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BarChart3, CalendarDays, Check, Clock3, History, Loader2, Save, UserCheck, UserX } from "lucide-react"
import { toast } from "sonner"

import { AcademicGrade } from "@/components/academic/AcademicDialog"
import { Student } from "@/components/students/StudentDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { apiClient } from "@/lib/api/client"

type AttendanceStatus = "present" | "absent" | "late" | "leave" | "holiday"
type AttendanceTab = "register" | "report"

interface AttendanceRecord {
  id: string
  student_id: string
  date_bs: string
  date_ad: string
  status: AttendanceStatus
  remarks?: string | null
  period_number?: number | null
}

interface AttendanceList {
  date_bs: string
  date_ad: string
  grade: string
  section: string
  period_number?: number | null
  total_students: number
  records: AttendanceRecord[]
}

interface StudentList {
  students: Student[]
  total: number
}

interface CalendarConversion {
  bs_date: { year: number; month: number; day: number }
  ad_date: { iso_date: string }
}

interface DailySummary {
  date_bs: string
  date_ad: string
  present_count: number
  absent_count: number
  late_count: number
  leave_count: number
  holiday_count: number
  total: number
}

interface MonthlyReport {
  grade: string
  section: string
  year_bs: number
  month_bs: number
  total_school_days: number
  average_attendance_percentage: number
  daily_summaries: DailySummary[]
}

interface StudentHistory {
  student_id: string
  total_days: number
  present_count: number
  absent_count: number
  late_count: number
  leave_count: number
  attendance_percentage: number
  records: AttendanceRecord[]
}

interface MarkValue { status: AttendanceStatus; remarks: string }

const statusOptions: Array<{ value: AttendanceStatus; label: string }> = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late", label: "Late" },
  { value: "leave", label: "Leave" },
  { value: "holiday", label: "Holiday" },
]

const bsMonths = ["Baisakh", "Jestha", "Ashadh", "Shrawan", "Bhadra", "Ashwin", "Kartik", "Mangsir", "Poush", "Magh", "Falgun", "Chaitra"]
const selectClass = "h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"

function localDate(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function dateBefore(days: number) {
  const value = new Date()
  value.setDate(value.getDate() - days)
  return localDate(value)
}

function formatBsDate(value: CalendarConversion | undefined) {
  if (!value) return ""
  return `${value.bs_date.year}-${String(value.bs_date.month).padStart(2, "0")}-${String(value.bs_date.day).padStart(2, "0")}`
}

function percentage(present: number, late: number, total: number) {
  return total ? Math.round(((present + late) / total) * 1000) / 10 : 0
}

export default function AttendancePage() {
  const [tab, setTab] = useState<AttendanceTab>("register")
  const [gradeId, setGradeId] = useState("")
  const [sectionName, setSectionName] = useState("")
  const [attendanceDate, setAttendanceDate] = useState(localDate())
  const [period, setPeriod] = useState("")
  const [changes, setChanges] = useState<Record<string, Record<string, MarkValue>>>({})
  const [reportYear, setReportYear] = useState("")
  const [reportMonth, setReportMonth] = useState("")
  const [historyStudent, setHistoryStudent] = useState<Student | null>(null)
  const [historyStart, setHistoryStart] = useState(dateBefore(30))
  const [historyEnd, setHistoryEnd] = useState(localDate())
  const queryClient = useQueryClient()

  const gradesQuery = useQuery({
    queryKey: ["academic", "grades"],
    queryFn: async () => {
      const response = await apiClient.academic.grades.list()
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load grades")
      return response.data as AcademicGrade[]
    },
  })

  const grades = gradesQuery.data ?? []
  const effectiveGradeId = grades.some((grade) => grade.id === gradeId) ? gradeId : grades[0]?.id ?? ""
  const selectedGrade = grades.find((grade) => grade.id === effectiveGradeId)
  const activeSections = selectedGrade?.sections.filter((section) => section.is_active) ?? []
  const effectiveSection = activeSections.some((section) => section.name === sectionName) ? sectionName : activeSections[0]?.name ?? ""
  const gradeNumber = selectedGrade?.grade_number
  const isHigherSecondary = gradeNumber === 11 || gradeNumber === 12
  const selectedPeriod = isHigherSecondary && period ? Number(period) : undefined

  const conversionQuery = useQuery({
    queryKey: ["calendar", "ad-to-bs", attendanceDate],
    queryFn: async () => {
      const response = await apiClient.calendar.convertAdToBs(attendanceDate)
      if (!response.success) throw new Error(response.error?.message ?? "Unable to convert the attendance date")
      return response.data as CalendarConversion
    },
    enabled: Boolean(attendanceDate),
  })
  const dateBs = formatBsDate(conversionQuery.data)

  const rosterQuery = useQuery({
    queryKey: ["attendance", "roster", gradeNumber, effectiveSection],
    queryFn: async () => {
      const response = await apiClient.students.list({ page: 1, limit: 100, grade: gradeNumber, section: effectiveSection, status: "active" })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load the class roster")
      return response.data as StudentList
    },
    enabled: Boolean(gradeNumber && effectiveSection),
  })

  const attendanceQuery = useQuery({
    queryKey: ["attendance", "date", gradeNumber, effectiveSection, attendanceDate, selectedPeriod ?? "daily"],
    queryFn: async () => {
      const response = await apiClient.attendance.getByClass({
        date_ad: attendanceDate,
        grade: String(gradeNumber),
        section: effectiveSection,
        period_number: selectedPeriod,
      })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load attendance")
      return response.data as AttendanceList
    },
    enabled: Boolean(gradeNumber && effectiveSection && attendanceDate),
  })

  const selectionKey = `${gradeNumber ?? ""}:${effectiveSection}:${attendanceDate}:${selectedPeriod ?? "daily"}`
  const selectionChanges = changes[selectionKey] ?? {}
  const existingByStudent = useMemo(() => new Map((attendanceQuery.data?.records ?? []).map((record) => [record.student_id, record])), [attendanceQuery.data])
  const students = rosterQuery.data?.students ?? []
  const valueFor = (studentId: string): MarkValue => selectionChanges[studentId] ?? {
    status: existingByStudent.get(studentId)?.status ?? "present",
    remarks: existingByStudent.get(studentId)?.remarks ?? "",
  }

  const counts = students.reduce<Record<AttendanceStatus, number>>((result, student) => {
    result[valueFor(student.id).status] += 1
    return result
  }, { present: 0, absent: 0, late: 0, leave: 0, holiday: 0 })

  const updateMark = (studentId: string, patch: Partial<MarkValue>) => {
    setChanges((current) => ({
      ...current,
      [selectionKey]: {
        ...(current[selectionKey] ?? {}),
        [studentId]: { ...valueFor(studentId), ...patch },
      },
    }))
  }

  const markAll = (status: AttendanceStatus) => {
    setChanges((current) => ({
      ...current,
      [selectionKey]: Object.fromEntries(students.map((student) => [student.id, { ...valueFor(student.id), status }])),
    }))
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!gradeNumber || !effectiveSection || !dateBs || students.length === 0) throw new Error("Select a class with active students first")
      const response = await apiClient.attendance.mark({
        date_bs: dateBs,
        date_ad: attendanceDate,
        grade: String(gradeNumber),
        section: effectiveSection,
        period_number: selectedPeriod ?? null,
        entries: students.map((student) => ({ student_id: student.id, ...valueFor(student.id), remarks: valueFor(student.id).remarks.trim() || null })),
      })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to save attendance")
    },
    onSuccess: async () => {
      toast.success(`Attendance saved for ${students.length} students`)
      setChanges((current) => {
        const next = { ...current }
        delete next[selectionKey]
        return next
      })
      await queryClient.invalidateQueries({ queryKey: ["attendance"] })
    },
    onError: (error) => toast.error(error.message),
  })

  const defaultBsYear = conversionQuery.data?.bs_date.year
  const defaultBsMonth = conversionQuery.data?.bs_date.month
  const effectiveReportYear = Number(reportYear || defaultBsYear || 0)
  const effectiveReportMonth = Number(reportMonth || defaultBsMonth || 0)
  const reportQuery = useQuery({
    queryKey: ["attendance", "report", gradeNumber, effectiveSection, effectiveReportYear, effectiveReportMonth],
    queryFn: async () => {
      const response = await apiClient.attendance.getReport({ grade: String(gradeNumber), section: effectiveSection, year_bs: effectiveReportYear, month_bs: effectiveReportMonth })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load monthly report")
      return response.data as MonthlyReport
    },
    enabled: tab === "report" && Boolean(gradeNumber && effectiveSection && effectiveReportYear && effectiveReportMonth),
  })

  const historyQuery = useQuery({
    queryKey: ["attendance", "student-history", historyStudent?.id, historyStart, historyEnd],
    queryFn: async () => {
      const response = await apiClient.attendance.getStudentHistory(historyStudent!.id, historyStart, historyEnd)
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load student history")
      return response.data as StudentHistory
    },
    enabled: Boolean(historyStudent && historyStart && historyEnd && historyStart <= historyEnd),
  })

  const loadingRegister = rosterQuery.isLoading || attendanceQuery.isLoading
  const registerError = rosterQuery.error || attendanceQuery.error || conversionQuery.error

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Student Attendance</h1>
          <p className="text-muted-foreground">Mark daily or period attendance and review monthly class records.</p>
        </div>
        <div className="section-tabs" role="group" aria-label="Attendance views">
          <Button  data-active={tab === "register"} aria-pressed={tab === "register"} variant={tab === "register" ? "secondary" : "ghost"} onClick={() => setTab("register")}><UserCheck />Register</Button>
          <Button  data-active={tab === "report"} aria-pressed={tab === "report"} variant={tab === "report" ? "secondary" : "ghost"} onClick={() => setTab("report")}><BarChart3 />Monthly report</Button>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-4 pt-6 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Grade">
            <select className={`${selectClass} w-full`} value={effectiveGradeId} onChange={(event) => { setGradeId(event.target.value); setSectionName(""); setPeriod("") }} disabled={gradesQuery.isLoading}>
              {grades.length === 0 && <option value="">No grades configured</option>}
              {grades.map((grade) => <option key={grade.id} value={grade.id}>{grade.name_en}</option>)}
            </select>
          </Field>
          <Field label="Section">
            <select className={`${selectClass} w-full`} value={effectiveSection} onChange={(event) => setSectionName(event.target.value)} disabled={!selectedGrade}>
              {activeSections.length === 0 && <option value="">No active sections</option>}
              {activeSections.map((section) => <option key={section.id} value={section.name}>Section {section.name}</option>)}
            </select>
          </Field>
          <Field label="Date (AD)"><Input type="date" value={attendanceDate} onChange={(event) => setAttendanceDate(event.target.value)} /></Field>
          <Field label="Date (BS)"><Input value={conversionQuery.isLoading ? "Converting..." : dateBs} readOnly aria-label="Converted Bikram Sambat date" /></Field>
          <Field label="Period">
            <select className={`${selectClass} w-full`} value={period} onChange={(event) => setPeriod(event.target.value)} disabled={!isHigherSecondary}>
              <option value="">{isHigherSecondary ? "Daily attendance" : "Not applicable"}</option>
              {isHigherSecondary && Array.from({ length: 8 }, (_, index) => <option key={index + 1} value={index + 1}>Period {index + 1}</option>)}
            </select>
          </Field>
        </CardContent>
      </Card>

      {tab === "register" && <>
        <div className="pastel-summary grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
          <Summary title="Students" value={students.length} icon={<UserCheck />} />
          <Summary title="Present" value={counts.present} icon={<Check />} tone="text-emerald-600" />
          <Summary title="Absent" value={counts.absent} icon={<UserX />} tone="text-red-600" />
          <Summary title="Late" value={counts.late} icon={<Clock3 />} tone="text-amber-600" />
          <Summary title="Leave" value={counts.leave} icon={<CalendarDays />} tone="text-blue-600" />
          <Summary title="Attendance" value={`${percentage(counts.present, counts.late, students.length)}%`} icon={<BarChart3 />} />
        </div>

        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div><CardTitle>Class register</CardTitle><p className="mt-1 text-sm text-muted-foreground">{selectedGrade?.name_en ?? "Select grade"}{effectiveSection ? ` · Section ${effectiveSection}` : ""}{selectedPeriod ? ` · Period ${selectedPeriod}` : " · Daily"}</p></div>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={!students.length || saveMutation.isPending} onClick={() => markAll("present")}><Check />Mark all present</Button>
              <Button disabled={!students.length || !dateBs || saveMutation.isPending} onClick={() => saveMutation.mutate()}>{saveMutation.isPending ? <Loader2 className="animate-spin" /> : <Save />}Save attendance</Button>
            </div>
          </CardHeader>
          <CardContent>
            {gradesQuery.error ? <EmptyState error={gradesQuery.error.message} /> : registerError ? <EmptyState error={registerError.message} /> : loadingRegister ? <EmptyState loading text="Loading class register..." /> : !effectiveSection ? <EmptyState text="Add an active section to this grade before marking attendance." /> : students.length === 0 ? <EmptyState text="No active students are assigned to this grade and section." /> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[800px]">
                  <thead><tr className="border-b"><Th>Roll</Th><Th>Student</Th><Th>Status</Th><Th>Remarks</Th><Th align="right">History</Th></tr></thead>
                  <tbody>{students.map((student) => {
                    const mark = valueFor(student.id)
                    return <tr key={student.id} className="border-b last:border-0 hover:bg-accent/40">
                      <Td>{student.roll_number ?? "—"}</Td>
                      <Td><p className="font-medium">{student.full_name_en}</p><p className="text-xs text-muted-foreground">{student.admission_number || student.emis_student_id || "No student ID"}</p></Td>
                      <Td><select aria-label={`Attendance status for ${student.full_name_en}`} className={`${selectClass} min-w-32 capitalize ${statusTone(mark.status)}`} value={mark.status} onChange={(event) => updateMark(student.id, { status: event.target.value as AttendanceStatus })}>{statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></Td>
                      <Td><Input aria-label={`Remarks for ${student.full_name_en}`} maxLength={500} placeholder="Optional note" value={mark.remarks} onChange={(event) => updateMark(student.id, { remarks: event.target.value })} /></Td>
                      <Td align="right"><Button size="icon" variant="ghost" aria-label={`View attendance history for ${student.full_name_en}`} onClick={() => setHistoryStudent(student)}><History /></Button></Td>
                    </tr>
                  })}</tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </>}

      {tab === "report" && <Card>
        <CardHeader className="space-y-4">
          <div><CardTitle>Monthly attendance report</CardTitle><p className="mt-1 text-sm text-muted-foreground">Daily totals for the selected Bikram Sambat month. Late students count as attended.</p></div>
          <div className="flex flex-wrap gap-3">
            <select aria-label="BS year" className={selectClass} value={effectiveReportYear || ""} onChange={(event) => setReportYear(event.target.value)}>{Array.from({ length: 5 }, (_, index) => (defaultBsYear ?? 2083) - 2 + index).map((year) => <option key={year} value={year}>{year} BS</option>)}</select>
            <select aria-label="BS month" className={selectClass} value={effectiveReportMonth || ""} onChange={(event) => setReportMonth(event.target.value)}>{bsMonths.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}</select>
          </div>
        </CardHeader>
        <CardContent>
          {reportQuery.isLoading ? <EmptyState loading text="Loading monthly report..." /> : reportQuery.error ? <EmptyState error={reportQuery.error.message} /> : !reportQuery.data?.daily_summaries.length ? <EmptyState text="No attendance has been recorded for this class and month." /> : <>
            <div className="mb-5 grid gap-4 sm:grid-cols-2"><Summary title="School days recorded" value={reportQuery.data.total_school_days} icon={<CalendarDays />} /><Summary title="Average attendance" value={`${reportQuery.data.average_attendance_percentage}%`} icon={<BarChart3 />} /></div>
            <div className="overflow-x-auto"><table className="w-full min-w-[700px]"><thead><tr className="border-b"><Th>Date (BS)</Th><Th>Date (AD)</Th><Th>Present</Th><Th>Absent</Th><Th>Late</Th><Th>Leave</Th><Th>Holiday</Th><Th align="right">Rate</Th></tr></thead><tbody>{reportQuery.data.daily_summaries.map((day) => <tr key={`${day.date_ad}-${day.date_bs}`} className="border-b last:border-0"><Td strong>{day.date_bs}</Td><Td>{day.date_ad}</Td><Td>{day.present_count}</Td><Td>{day.absent_count}</Td><Td>{day.late_count}</Td><Td>{day.leave_count}</Td><Td>{day.holiday_count}</Td><Td align="right"><span className="font-medium">{percentage(day.present_count, day.late_count, day.total)}%</span></Td></tr>)}</tbody></table></div>
          </>}
        </CardContent>
      </Card>}

      <Dialog open={Boolean(historyStudent)} onOpenChange={(open) => !open && setHistoryStudent(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
          <DialogHeader><DialogTitle>{historyStudent?.full_name_en} · Attendance history</DialogTitle><DialogDescription>Review this student&apos;s attendance over an AD date range.</DialogDescription></DialogHeader>
          <div className="grid gap-4 sm:grid-cols-2"><Field label="From"><Input type="date" value={historyStart} onChange={(event) => setHistoryStart(event.target.value)} /></Field><Field label="To"><Input type="date" value={historyEnd} onChange={(event) => setHistoryEnd(event.target.value)} /></Field></div>
          {historyStart > historyEnd ? <EmptyState error="The start date must be before the end date." /> : historyQuery.isLoading ? <EmptyState loading text="Loading attendance history..." /> : historyQuery.error ? <EmptyState error={historyQuery.error.message} /> : historyQuery.data ? <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5"><MiniStat label="Days" value={historyQuery.data.total_days} /><MiniStat label="Present" value={historyQuery.data.present_count} /><MiniStat label="Absent" value={historyQuery.data.absent_count} /><MiniStat label="Late" value={historyQuery.data.late_count} /><MiniStat label="Rate" value={`${historyQuery.data.attendance_percentage}%`} /></div>
            {historyQuery.data.records.length === 0 ? <EmptyState text="No records in this date range." /> : <div className="overflow-x-auto"><table className="w-full"><thead><tr className="border-b"><Th>Date</Th><Th>BS date</Th><Th>Status</Th><Th>Period</Th><Th>Remarks</Th></tr></thead><tbody>{historyQuery.data.records.map((record) => <tr key={record.id} className="border-b last:border-0"><Td>{record.date_ad}</Td><Td>{record.date_bs}</Td><Td><span className={`capitalize ${statusTone(record.status)}`}>{record.status}</span></Td><Td>{record.period_number ?? "Daily"}</Td><Td>{record.remarks || "—"}</Td></tr>)}</tbody></table></div>}
          </> : null}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function statusTone(status: AttendanceStatus) {
  return status === "present" ? "text-emerald-700" : status === "absent" ? "text-red-700" : status === "late" ? "text-amber-700" : status === "leave" ? "text-blue-700" : "text-slate-600"
}

function Field({ label, children }: { label: string; children: React.ReactNode }) { return <label className="space-y-1.5"><span className="text-sm font-medium">{label}</span>{children}</label> }
function Summary({ title, value, icon, tone = "" }: { title: string; value: number | string; icon: React.ReactNode; tone?: string }) { return <Card><CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2"><CardTitle className="text-sm font-medium">{title}</CardTitle><span className={`${tone} [&_svg]:h-4 [&_svg]:w-4`}>{icon}</span></CardHeader><CardContent><p className={`text-2xl font-bold ${tone}`}>{value}</p></CardContent></Card> }
function MiniStat({ label, value }: { label: string; value: number | string }) { return <div className="rounded-md bg-muted/60 p-3 text-center"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 font-semibold">{value}</p></div> }
function EmptyState({ text, error, loading = false }: { text?: string; error?: string; loading?: boolean }) { return <div className={`flex items-center justify-center gap-2 py-12 text-center text-sm ${error ? "text-destructive" : "text-muted-foreground"}`}>{loading && <Loader2 className="animate-spin" />}{error ?? text}</div> }
function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) { return <th className={`px-3 py-3 text-sm font-medium ${align === "right" ? "text-right" : "text-left"}`}>{children}</th> }
function Td({ children, align = "left", strong = false }: { children: React.ReactNode; align?: "left" | "right"; strong?: boolean }) { return <td className={`px-3 py-3 text-sm ${align === "right" ? "text-right" : "text-left"} ${strong ? "font-medium" : ""}`}>{children}</td> }
