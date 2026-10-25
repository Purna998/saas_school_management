"use client"

import { memo } from "react"
import { History } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { StudentRosterEntry } from "@/lib/api/client"

export type AttendanceStatus = "present" | "absent" | "late" | "leave" | "holiday"
type MarkValue = { status: AttendanceStatus; remarks: string }

const statusOptions: Array<{ value: AttendanceStatus; label: string }> = [
  { value: "present", label: "Present" },
  { value: "absent", label: "Absent" },
  { value: "late", label: "Late" },
  { value: "leave", label: "Leave" },
  { value: "holiday", label: "Holiday" },
]

export function statusTone(status: AttendanceStatus) {
  return status === "present" ? "text-emerald-700" : status === "absent" ? "text-red-700" : status === "late" ? "text-amber-700" : status === "leave" ? "text-blue-700" : "text-slate-600"
}

interface AttendanceRowProps extends MarkValue {
  student: StudentRosterEntry
  onChange: (studentId: string, patch: Partial<MarkValue>) => void
  onHistory: (student: StudentRosterEntry) => void
}

// Primitive editable props and stable callbacks let unchanged rows skip render.
export const AttendanceRow = memo(function AttendanceRow({ student, status, remarks, onChange, onHistory }: AttendanceRowProps) {
  return (
    <tr className="border-b last:border-0 hover:bg-accent/40">
      <td className="px-3 py-3 text-sm text-left">{student.roll_number ?? "—"}</td>
      <td className="px-3 py-3 text-sm text-left"><p className="font-medium">{student.full_name_en}</p><p className="text-xs text-muted-foreground">{student.admission_number || student.emis_student_id || "No student ID"}</p></td>
      <td className="px-3 py-3 text-sm text-left"><select aria-label={`Attendance status for ${student.full_name_en}`} className={`h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring min-w-32 capitalize ${statusTone(status)}`} value={status} onChange={(event) => onChange(student.id, { status: event.target.value as AttendanceStatus })}>{statusOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></td>
      <td className="px-3 py-3 text-sm text-left"><Input aria-label={`Remarks for ${student.full_name_en}`} maxLength={500} placeholder="Optional note" value={remarks} onChange={(event) => onChange(student.id, { remarks: event.target.value })} /></td>
      <td className="px-3 py-3 text-sm text-right"><Button size="icon" variant="ghost" aria-label={`View attendance history for ${student.full_name_en}`} onClick={() => onHistory(student)}><History /></Button></td>
    </tr>
  )
})
