"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Download, Edit, Eye, Loader2, Plus, Search, Trash2, UserCog } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import { StaffDetailsDialog, StaffEditorDialog, StaffMember } from "@/components/staff/StaffDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { apiClient } from "@/lib/api/client"

const PAGE_SIZE = 20
const selectClass = "h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"

type StaffScope = "all" | "teaching" | "administrative" | "non_teaching"

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? "" : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

function downloadCsv(filename: string, rows: unknown[][]) {
  const content = `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}`
  const url = URL.createObjectURL(new Blob([content], { type: "text/csv;charset=utf-8" }))
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function labelType(type: string) {
  if (type === "teaching") return "Teacher"
  if (type === "administrative") return "Administrator"
  return "Support staff"
}

export default function StaffPage() {
  const [searchQuery, setSearchQuery] = useState("")
  const [submittedSearch, setSubmittedSearch] = useState("")
  const [scope, setScope] = useState<StaffScope>("all")
  const [staffStatus, setStaffStatus] = useState("")
  const [currentPage, setCurrentPage] = useState(1)
  const [editor, setEditor] = useState<{ mode: "create" | "edit"; staff: StaffMember | null } | null>(null)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [detailsLoading, setDetailsLoading] = useState(false)
  const [selectedStaff, setSelectedStaff] = useState<StaffMember | null>(null)
  const [isExporting, setIsExporting] = useState(false)
  const queryClient = useQueryClient()

  const filters = {
    search: submittedSearch || undefined,
    staff_type: scope === "all" ? undefined : scope,
    status: staffStatus || undefined,
  }

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["staff", "list", currentPage, filters],
    queryFn: async () => {
      const response = await apiClient.staff.list({ page: currentPage, limit: PAGE_SIZE, ...filters })
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load staff")
      return {
        items: response.data as StaffMember[],
        total: response.meta?.total ?? (response.data as StaffMember[]).length,
      }
    },
    placeholderData: keepPreviousData,
  })

  const { data: counts } = useQuery({
    queryKey: ["staff", "counts"],
    queryFn: async () => {
      const [all, teachers, administrators, support] = await Promise.all([
        apiClient.staff.list({ page: 1, limit: 1 }),
        apiClient.staff.list({ page: 1, limit: 1, staff_type: "teaching" }),
        apiClient.staff.list({ page: 1, limit: 1, staff_type: "administrative" }),
        apiClient.staff.list({ page: 1, limit: 1, staff_type: "non_teaching" }),
      ])
      return {
        all: all.meta?.total ?? 0,
        teaching: teachers.meta?.total ?? 0,
        administrative: administrators.meta?.total ?? 0,
        non_teaching: support.meta?.total ?? 0,
      }
    },
  })

  const saveStaff = useMutation({
    mutationFn: async ({ mode, staff, payload }: {
      mode: "create" | "edit"
      staff: StaffMember | null
      payload: Record<string, unknown>
    }) => {
      const response = mode === "create"
        ? await apiClient.staff.create(payload)
        : await apiClient.staff.update(staff!.id, payload)
      if (!response.success) throw new Error(response.error?.message ?? `Unable to ${mode} staff member`)
      return mode
    },
    onSuccess: async (mode) => {
      toast.success(mode === "create" ? "Staff member added successfully" : "Staff member updated successfully")
      setEditor(null)
      await queryClient.invalidateQueries({ queryKey: ["staff"] })
    },
    onError: (mutationError) => toast.error(mutationError.message),
  })

  const deleteStaff = useMutation({
    mutationFn: async (id: string) => {
      const response = await apiClient.staff.delete(id)
      if (!response.success) throw new Error(response.error?.message ?? "Unable to delete staff member")
    },
    onSuccess: async () => {
      toast.success("Staff member deleted successfully")
      if (staff.length === 1 && currentPage > 1) setCurrentPage((page) => page - 1)
      await queryClient.invalidateQueries({ queryKey: ["staff"] })
    },
    onError: (mutationError) => toast.error(mutationError.message),
  })

  const staff = data?.items ?? []
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))

  const selectScope = (nextScope: StaffScope) => {
    setScope(nextScope)
    setCurrentPage(1)
  }

  const submitSearch = () => {
    setSubmittedSearch(searchQuery.trim())
    setCurrentPage(1)
  }

  const clearFilters = () => {
    setSearchQuery("")
    setSubmittedSearch("")
    setScope("all")
    setStaffStatus("")
    setCurrentPage(1)
  }

  const handleView = async (staffId: string) => {
    setSelectedStaff(null)
    setDetailsOpen(true)
    setDetailsLoading(true)
    const response = await apiClient.staff.get(staffId)
    setDetailsLoading(false)
    if (!response.success) {
      toast.error(response.error?.message ?? "Unable to load staff details")
      return
    }
    setSelectedStaff(response.data as StaffMember)
  }

  const handleDelete = (member: StaffMember) => {
    if (!window.confirm(`Delete ${member.full_name_en}? Historical records will be preserved.`)) return
    deleteStaff.mutate(member.id)
  }

  const handleExport = async () => {
    setIsExporting(true)
    try {
      const exported: StaffMember[] = []
      let page = 1
      let total = 0
      do {
        const response = await apiClient.staff.list({ page, limit: 100, ...filters })
        if (!response.success) throw new Error(response.error?.message ?? "Unable to export staff")
        const items = response.data as StaffMember[]
        exported.push(...items)
        total = response.meta?.total ?? items.length
        page += 1
      } while (exported.length < total)

      downloadCsv(`staff-${new Date().toISOString().slice(0, 10)}.csv`, [
        ["employee_id", "full_name_en", "full_name_np", "staff_type", "designation", "department", "tsc_number", "phone", "email", "qualification", "joined_date_ad", "salary", "status"],
        ...exported.map((member) => [
          member.employee_id, member.full_name_en, member.full_name_np, member.staff_type,
          member.designation, member.department, member.tsc_number, member.phone, member.email,
          member.qualification, member.joined_date_ad, member.salary, member.status,
        ]),
      ])
      toast.success(`Exported ${exported.length} staff records`)
    } catch (exportError) {
      toast.error(exportError instanceof Error ? exportError.message : "Unable to export staff")
    } finally {
      setIsExporting(false)
    }
  }

  const tabs: Array<{ value: StaffScope; label: string; count: number | undefined }> = [
    { value: "all", label: "All staff", count: counts?.all },
    { value: "teaching", label: "Teachers", count: counts?.teaching },
    { value: "administrative", label: "Administrators", count: counts?.administrative },
    { value: "non_teaching", label: "Support staff", count: counts?.non_teaching },
  ]

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Staff &amp; Teachers</h1>
          <p className="text-muted-foreground">Manage teachers, administrators, and support staff.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={handleExport} disabled={isExporting || isLoading}>
            {isExporting ? <Loader2 className="animate-spin" /> : <Download />}
            Export CSV
          </Button>
          <Button onClick={() => setEditor({ mode: "create", staff: null })}>
            <Plus />
            {scope === "teaching" ? "Add Teacher" : "Add Staff Member"}
          </Button>
        </div>
      </div>

      <div className="pastel-summary grid grid-cols-2 gap-4 xl:grid-cols-4">
        {tabs.map((tab) => (
          <Card key={tab.value} className={scope === tab.value ? "ring-1 ring-primary/40" : ""}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium"><button className="rounded text-left hover:text-primary" onClick={() => selectScope(tab.value)} aria-pressed={scope === tab.value}>{tab.label}</button></CardTitle>
              <UserCog className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent><div className="text-2xl font-bold">{tab.count ?? "..."}</div></CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="space-y-4">
          <div className="section-tabs" role="group" aria-label="Staff type">
            {tabs.map((tab) => (
              <Button key={tab.value} size="sm" data-active={scope === tab.value} aria-pressed={scope === tab.value} variant={scope === tab.value ? "secondary" : "ghost"} onClick={() => selectScope(tab.value)}>{tab.label}</Button>
            ))}
          </div>
          <div className="flex flex-col gap-3 lg:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input aria-label="Search staff" placeholder="Search by name, employee ID, or TSC number" className="pl-10" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && submitSearch()} />
            </div>
            <select className={selectClass} aria-label="Filter by status" value={staffStatus} onChange={(event) => { setStaffStatus(event.target.value); setCurrentPage(1) }}>
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="on_leave">On leave</option>
              <option value="resigned">Resigned</option>
              <option value="retired">Retired</option>
              <option value="terminated">Terminated</option>
            </select>
            <Button variant="outline" onClick={submitSearch} disabled={isFetching}>Search</Button>
            <Button variant="ghost" onClick={clearFilters}>Clear</Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead><tr className="border-b">
                <th className="px-3 py-3 text-left text-sm font-medium">Employee ID</th><th className="px-3 py-3 text-left text-sm font-medium">Name</th><th className="px-3 py-3 text-left text-sm font-medium">Type</th><th className="px-3 py-3 text-left text-sm font-medium">Designation</th><th className="px-3 py-3 text-left text-sm font-medium">Department</th><th className="px-3 py-3 text-left text-sm font-medium">Contact</th><th className="px-3 py-3 text-left text-sm font-medium">Status</th><th className="px-3 py-3 text-right text-sm font-medium">Actions</th>
              </tr></thead>
              <tbody>
                {isLoading ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-muted-foreground">Loading staff...</td></tr>
                ) : error ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-destructive">{error.message}</td></tr>
                ) : staff.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-10 text-center text-muted-foreground">No matching staff members found.</td></tr>
                ) : staff.map((member) => (
                  <tr key={member.id} className="border-b hover:bg-accent/50">
                    <td className="px-3 py-3 text-sm">{member.employee_id || "-"}</td><td className="px-3 py-3 text-sm font-medium"><div className="flex items-center gap-3"><span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#e6f3fb] text-xs font-medium text-[#559abf]" aria-hidden="true">{member.full_name_en.split(" ").slice(0, 2).map((part) => part[0]).join("")}</span><span className="whitespace-nowrap">{member.full_name_en}</span></div></td><td className="px-3 py-3 text-sm">{labelType(member.staff_type)}</td><td className="px-3 py-3 text-sm">{member.designation || "-"}</td><td className="px-3 py-3 text-sm">{member.department || "-"}</td><td className="px-3 py-3 text-sm">{member.phone || member.email || "-"}</td>
                    <td className="px-3 py-3 text-sm"><span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${member.status === "active" ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"}`}>{member.status.replaceAll("_", " ")}</span></td>
                    <td className="px-3 py-3"><div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" aria-label={`View ${member.full_name_en}`} onClick={() => handleView(member.id)}><Eye /></Button>
                      <Button variant="ghost" size="icon" aria-label={`Edit ${member.full_name_en}`} onClick={() => setEditor({ mode: "edit", staff: member })}><Edit /></Button>
                      <Button variant="ghost" size="icon" aria-label={`Delete ${member.full_name_en}`} disabled={deleteStaff.isPending && deleteStaff.variables === member.id} onClick={() => handleDelete(member)}>{deleteStaff.isPending && deleteStaff.variables === member.id ? <Loader2 className="animate-spin" /> : <Trash2 className="text-destructive" />}</Button>
                    </div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{data?.total ?? 0} records · Page {currentPage} of {totalPages}</p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setCurrentPage((page) => Math.max(1, page - 1))} disabled={currentPage === 1 || isFetching}>Previous</Button>
              <Button variant="outline" size="sm" onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))} disabled={currentPage === totalPages || isFetching}>Next</Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {editor && <StaffEditorDialog key={`${editor.mode}-${editor.staff?.id ?? scope}`} open mode={editor.mode} initialType={scope === "all" ? "teaching" : scope} staff={editor.staff} saving={saveStaff.isPending} onOpenChange={(open) => !open && setEditor(null)} onSave={async (payload) => { await saveStaff.mutateAsync({ ...editor, payload }) }} />}
      <StaffDetailsDialog open={detailsOpen} staff={selectedStaff} loading={detailsLoading} onOpenChange={setDetailsOpen} />
    </div>
  )
}
