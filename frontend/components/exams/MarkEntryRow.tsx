"use client"

import { memo } from "react"
import { Input } from "@/components/ui/input"
import type { StudentRosterEntry } from "@/lib/api/client"

export interface MarkValue { marks: string; absent: boolean; remarks: string }

interface MarkEntryRowProps extends MarkValue {
  student: StudentRosterEntry
  fullMarks: number | undefined
  onChange: (studentId: string, patch: Partial<MarkValue>) => void
}

export const MarkEntryRow = memo(function MarkEntryRow({ student, marks, absent, remarks, fullMarks, onChange }: MarkEntryRowProps) {
  return (
    <tr className="border-b last:border-0">
      <td className="px-3 py-3 text-sm text-left">{student.roll_number ?? "—"}</td>
      <td className="px-3 py-3 text-sm text-left font-medium">{student.full_name_en}</td>
      <td className="px-3 py-3 text-sm text-left"><Input className="w-28" aria-label={`Marks for ${student.full_name_en}`} type="number" min={0} max={fullMarks} step="0.01" disabled={absent} value={absent ? "" : marks} onChange={(event) => onChange(student.id, { marks: event.target.value })} /></td>
      <td className="px-3 py-3 text-sm text-left"><label className="inline-flex items-center gap-2 text-sm"><input type="checkbox" checked={absent} onChange={(event) => onChange(student.id, { absent: event.target.checked })} />Absent</label></td>
      <td className="px-3 py-3 text-sm text-left"><Input aria-label={`Remarks for ${student.full_name_en}`} maxLength={500} placeholder="Optional remark" value={remarks} onChange={(event) => onChange(student.id, { remarks: event.target.value })} /></td>
    </tr>
  )
})
