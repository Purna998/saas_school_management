"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BookOpen, Edit, GraduationCap, Loader2, Plus, School, Trash2, Users } from "lucide-react"
import { useState } from "react"
import { toast } from "sonner"

import {
  AcademicEditorDialog,
  AcademicEntity,
  AcademicFaculty,
  AcademicGrade,
  AcademicSection,
  AcademicStream,
  AcademicSubject,
  TeacherOption,
} from "@/components/academic/AcademicDialog"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { apiClient } from "@/lib/api/client"

interface AcademicOverview { grades: number; sections: number; subjects: number; faculties: number }
type AcademicItem = AcademicGrade | AcademicSection | AcademicSubject | AcademicFaculty | AcademicStream
type Tab = "grades" | "subjects" | "faculties"

interface EditorState {
  entity: AcademicEntity
  item: AcademicItem | null
  parentId?: string
}

function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase())
}

export default function AcademicPage() {
  const [tab, setTab] = useState<Tab>("grades")
  const [selectedGradeId, setSelectedGradeId] = useState("")
  const [editor, setEditor] = useState<EditorState | null>(null)
  const queryClient = useQueryClient()

  const overviewQuery = useQuery({
    queryKey: ["academic", "overview"],
    queryFn: async () => {
      const response = await apiClient.academic.overview()
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load academic overview")
      return response.data as AcademicOverview
    },
  })

  const gradesQuery = useQuery({
    queryKey: ["academic", "grades"],
    queryFn: async () => {
      const response = await apiClient.academic.grades.list()
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load grades")
      return response.data as AcademicGrade[]
    },
  })

  const facultiesQuery = useQuery({
    queryKey: ["academic", "faculties"],
    queryFn: async () => {
      const response = await apiClient.academic.faculties.list()
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load faculties")
      return response.data as AcademicFaculty[]
    },
  })

  const teachersQuery = useQuery({
    queryKey: ["academic", "teacher-options"],
    queryFn: async () => {
      const response = await apiClient.staff.list({ page: 1, limit: 100, staff_type: "teaching", status: "active" })
      return response.success ? response.data as TeacherOption[] : []
    },
  })

  const grades = gradesQuery.data ?? []
  const faculties = facultiesQuery.data ?? []
  const teachers = teachersQuery.data ?? []
  const effectiveGradeId = selectedGradeId || grades[0]?.id || ""
  const selectedGrade = grades.find((grade) => grade.id === effectiveGradeId)

  const subjectsQuery = useQuery({
    queryKey: ["academic", "subjects", effectiveGradeId],
    queryFn: async () => {
      const response = await apiClient.academic.subjects.list(effectiveGradeId)
      if (!response.success) throw new Error(response.error?.message ?? "Unable to load subjects")
      return response.data as AcademicSubject[]
    },
    enabled: Boolean(effectiveGradeId),
  })

  const saveEntity = useMutation({
    mutationFn: async ({ state, payload }: { state: EditorState; payload: Record<string, unknown> }) => {
      const { entity, item } = state
      let response
      if (entity === "grade") response = item ? await apiClient.academic.grades.update(item.id, payload) : await apiClient.academic.grades.create(payload)
      else if (entity === "section") response = item ? await apiClient.academic.sections.update(item.id, payload) : await apiClient.academic.sections.create(payload)
      else if (entity === "subject") response = item ? await apiClient.academic.subjects.update(item.id, payload) : await apiClient.academic.subjects.create(payload)
      else if (entity === "faculty") response = item ? await apiClient.academic.faculties.update(item.id, payload) : await apiClient.academic.faculties.create(payload)
      else response = item ? await apiClient.academic.streams.update(item.id, payload) : await apiClient.academic.streams.create(payload)
      if (!response.success) throw new Error(response.error?.message ?? `Unable to save ${entity}`)
      return { entity, editing: Boolean(item) }
    },
    onSuccess: async ({ entity, editing }) => {
      toast.success(`${humanize(entity)} ${editing ? "updated" : "added"} successfully`)
      setEditor(null)
      await queryClient.invalidateQueries({ queryKey: ["academic"] })
    },
    onError: (error) => toast.error(error.message),
  })

  const deleteEntity = useMutation({
    mutationFn: async ({ entity, item }: { entity: AcademicEntity; item: AcademicItem }) => {
      let response
      if (entity === "grade") response = await apiClient.academic.grades.delete(item.id)
      else if (entity === "section") response = await apiClient.academic.sections.delete(item.id)
      else if (entity === "subject") response = await apiClient.academic.subjects.delete(item.id)
      else if (entity === "faculty") response = await apiClient.academic.faculties.delete(item.id)
      else response = await apiClient.academic.streams.delete(item.id)
      if (!response.success) throw new Error(response.error?.message ?? `Unable to remove ${entity}`)
      return entity
    },
    onSuccess: async (entity) => {
      toast.success(`${humanize(entity)} removed from the active structure`)
      await queryClient.invalidateQueries({ queryKey: ["academic"] })
    },
    onError: (error) => toast.error(error.message),
  })

  const remove = (entity: AcademicEntity, item: AcademicItem, label: string) => {
    if (window.confirm(`Remove ${label} from the active academic structure? Existing historical records will remain.`)) deleteEntity.mutate({ entity, item })
  }

  const openSubjects = (gradeId: string) => {
    setSelectedGradeId(gradeId)
    setTab("subjects")
  }

  const overview = overviewQuery.data
  const loading = gradesQuery.isLoading || facultiesQuery.isLoading
  const error = gradesQuery.error || facultiesQuery.error || overviewQuery.error

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Academic Structure</h1>
        <p className="text-muted-foreground">Configure Grade 1-12 classes, sections, subjects, and higher-secondary faculties.</p>
      </div>

      <div className="pastel-summary grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Summary title="Active grades" value={overview?.grades} icon={<GraduationCap />} loading={overviewQuery.isLoading} />
        <Summary title="Sections" value={overview?.sections} icon={<Users />} loading={overviewQuery.isLoading} />
        <Summary title="Subjects" value={overview?.subjects} icon={<BookOpen />} loading={overviewQuery.isLoading} />
        <Summary title="Faculties" value={overview?.faculties} icon={<School />} loading={overviewQuery.isLoading} />
      </div>

      <div className="section-tabs" role="group" aria-label="Academic structure sections">
        <Button  data-active={tab === "grades"} aria-pressed={tab === "grades"} variant={tab === "grades" ? "secondary" : "ghost"} onClick={() => setTab("grades")}>Grades &amp; Sections</Button>
        <Button  data-active={tab === "subjects"} aria-pressed={tab === "subjects"} variant={tab === "subjects" ? "secondary" : "ghost"} onClick={() => setTab("subjects")}>Subjects</Button>
        <Button  data-active={tab === "faculties"} aria-pressed={tab === "faculties"} variant={tab === "faculties" ? "secondary" : "ghost"} onClick={() => setTab("faculties")}>Faculties &amp; Streams</Button>
      </div>

      {error ? <Card><CardContent className="py-10 text-center text-destructive">{error.message}</CardContent></Card> : loading ? <Card><CardContent className="py-10 text-center text-muted-foreground">Loading academic structure...</CardContent></Card> : null}

      {!loading && !error && tab === "grades" && (
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Grades &amp; Sections</CardTitle><p className="mt-1 text-sm text-muted-foreground">Organize classes and assign class teachers.</p></div><Button onClick={() => setEditor({ entity: "grade", item: null })}><Plus />Add Grade</Button></CardHeader>
          <CardContent className="space-y-4">
            {grades.length === 0 ? <Empty text="No grades configured yet." action="Add the first grade" onClick={() => setEditor({ entity: "grade", item: null })} /> : grades.map((grade) => (
              <div key={grade.id} className="rounded-lg border">
                <div className="flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div><h3 className="font-semibold">{grade.name_en} {grade.name_np && <span className="font-normal text-muted-foreground">· {grade.name_np}</span>}</h3><p className="text-sm text-muted-foreground">{grade.sections.length} sections · Academic year {grade.academic_year_bs || "not set"}{grade.is_hs ? " · Higher secondary" : ""}</p></div>
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => openSubjects(grade.id)}><BookOpen />Subjects</Button>
                    <Button size="sm" variant="outline" onClick={() => setEditor({ entity: "section", item: null, parentId: grade.id })}><Plus />Section</Button>
                    <Button size="icon" variant="ghost" aria-label={`Edit ${grade.name_en}`} onClick={() => setEditor({ entity: "grade", item: grade })}><Edit /></Button>
                    <Button size="icon" variant="ghost" aria-label={`Remove ${grade.name_en}`} onClick={() => remove("grade", grade, grade.name_en)}><Trash2 className="text-destructive" /></Button>
                  </div>
                </div>
                <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-3">
                  {grade.sections.length === 0 ? <p className="text-sm text-muted-foreground">No sections added.</p> : grade.sections.map((section) => (
                    <div key={section.id} className="flex items-center justify-between rounded-md bg-muted/50 p-3">
                      <div><p className="font-medium">Section {section.name}{section.stream_id ? ` · ${faculties.flatMap((faculty) => faculty.streams).find((stream) => stream.id === section.stream_id)?.code ?? "Stream"}` : ""}</p><p className="text-xs text-muted-foreground">Capacity {section.capacity} · {teachers.find((teacher) => teacher.id === section.class_teacher_id)?.full_name_en || "No class teacher"}</p></div>
                      <div className="flex"><Button size="icon" variant="ghost" aria-label={`Edit section ${section.name}`} onClick={() => setEditor({ entity: "section", item: section, parentId: grade.id })}><Edit /></Button><Button size="icon" variant="ghost" aria-label={`Remove section ${section.name}`} onClick={() => remove("section", section, `Section ${section.name}`)}><Trash2 className="text-destructive" /></Button></div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {!loading && !error && tab === "subjects" && (
        <Card>
          <CardHeader className="space-y-4"><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Subjects</CardTitle><p className="mt-1 text-sm text-muted-foreground">Curriculum, marks, credits, faculty, and teacher assignment.</p></div><Button disabled={!effectiveGradeId} onClick={() => setEditor({ entity: "subject", item: null, parentId: effectiveGradeId })}><Plus />Add Subject</Button></div>
            <select className="h-10 w-full max-w-sm rounded-md border border-input bg-background px-3 text-sm" aria-label="Select grade" value={effectiveGradeId} onChange={(event) => setSelectedGradeId(event.target.value)}><option value="">Select grade</option>{grades.map((grade) => <option key={grade.id} value={grade.id}>{grade.name_en}</option>)}</select>
          </CardHeader>
          <CardContent>
            {!effectiveGradeId ? <Empty text="Add a grade before configuring subjects." /> : subjectsQuery.isLoading ? <p className="py-10 text-center text-muted-foreground">Loading subjects...</p> : subjectsQuery.error ? <p className="py-10 text-center text-destructive">{subjectsQuery.error.message}</p> : (subjectsQuery.data?.length ?? 0) === 0 ? <Empty text={`No subjects configured for ${selectedGrade?.name_en ?? "this grade"}.`} action="Add subject" onClick={() => setEditor({ entity: "subject", item: null, parentId: effectiveGradeId })} /> : (
              <div className="overflow-x-auto"><table className="w-full"><thead><tr className="border-b"><Th>Code</Th><Th>Subject</Th><Th>Requirement</Th><Th>Faculty / streams</Th><Th>Marks</Th><Th>Teacher</Th><Th align="right">Actions</Th></tr></thead><tbody>{subjectsQuery.data!.map((subject) => {
                const faculty = faculties.find((candidate) => candidate.id === subject.faculty_id)
                const streamNames = faculty?.streams.filter((stream) => subject.stream_ids.includes(stream.id)).map((stream) => stream.code) ?? []
                return <tr key={subject.id} className="border-b hover:bg-accent/50"><Td>{subject.code}</Td><Td strong>{subject.name_en}</Td><Td>{humanize(subject.subject_type)}{subject.optional_group ? ` · ${subject.optional_group}` : ""}</Td><Td>{faculty ? `${faculty.name_en}${streamNames.length ? ` · ${streamNames.join(", ")}` : " · All streams"}` : "Common to all"}</Td><Td>{subject.pass_marks}/{subject.full_marks}</Td><Td>{teachers.find((teacher) => teacher.id === subject.teacher_id)?.full_name_en || "Not assigned"}</Td><Td align="right"><div className="flex justify-end"><Button size="icon" variant="ghost" aria-label={`Edit ${subject.name_en}`} onClick={() => setEditor({ entity: "subject", item: subject, parentId: effectiveGradeId })}><Edit /></Button><Button size="icon" variant="ghost" aria-label={`Remove ${subject.name_en}`} onClick={() => remove("subject", subject, subject.name_en)}><Trash2 className="text-destructive" /></Button></div></Td></tr>
              })}</tbody></table></div>
            )}
          </CardContent>
        </Card>
      )}

      {!loading && !error && tab === "faculties" && (
        <Card>
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Higher Secondary Faculties &amp; Streams</CardTitle><p className="mt-1 text-sm text-muted-foreground">Configure Grade 11-12 study groups such as Science or Management.</p></div><Button onClick={() => setEditor({ entity: "faculty", item: null })}><Plus />Add Faculty</Button></CardHeader>
          <CardContent className="grid gap-4 lg:grid-cols-2">
            {faculties.length === 0 ? <div className="lg:col-span-2"><Empty text="No higher-secondary faculties configured." action="Add faculty" onClick={() => setEditor({ entity: "faculty", item: null })} /></div> : faculties.map((faculty) => (
              <div key={faculty.id} className="rounded-lg border p-4">
                <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{faculty.name_en} <span className="text-sm font-normal text-muted-foreground">({faculty.code})</span></h3><p className="mt-1 text-sm text-muted-foreground">{faculty.description || `Capacity ${faculty.max_students}`}</p></div><div className="flex"><Button size="icon" variant="ghost" aria-label={`Edit ${faculty.name_en}`} onClick={() => setEditor({ entity: "faculty", item: faculty })}><Edit /></Button><Button size="icon" variant="ghost" aria-label={`Remove ${faculty.name_en}`} onClick={() => remove("faculty", faculty, faculty.name_en)}><Trash2 className="text-destructive" /></Button></div></div>
                <div className="mt-4 space-y-2"><div className="flex items-center justify-between"><p className="text-sm font-medium">Streams</p><Button size="sm" variant="outline" onClick={() => setEditor({ entity: "stream", item: null, parentId: faculty.id })}><Plus />Add</Button></div>{faculty.streams.length === 0 ? <p className="text-sm text-muted-foreground">No streams added.</p> : faculty.streams.map((stream) => <div key={stream.id} className="flex items-center justify-between rounded-md bg-muted/50 px-3 py-2"><span className="text-sm">{stream.name_en} <span className="text-muted-foreground">({stream.code})</span></span><div className="flex"><Button size="icon" variant="ghost" aria-label={`Edit ${stream.name_en}`} onClick={() => setEditor({ entity: "stream", item: stream, parentId: faculty.id })}><Edit /></Button><Button size="icon" variant="ghost" aria-label={`Remove ${stream.name_en}`} onClick={() => remove("stream", stream, stream.name_en)}><Trash2 className="text-destructive" /></Button></div></div>)}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {editor && <AcademicEditorDialog key={`${editor.entity}-${editor.item?.id ?? editor.parentId ?? "new"}`} entity={editor.entity} item={editor.item} parentId={editor.parentId} grades={grades} faculties={faculties} teachers={teachers} saving={saveEntity.isPending} onOpenChange={(open) => !open && setEditor(null)} onSave={async (payload) => { await saveEntity.mutateAsync({ state: editor, payload }) }} />}
      {deleteEntity.isPending && <div className="fixed bottom-5 right-5 flex items-center gap-2 rounded-md border bg-background px-4 py-3 text-sm shadow-lg"><Loader2 className="animate-spin" />Updating academic structure...</div>}
    </div>
  )
}

function Summary({ title, value, icon, loading }: { title: string; value?: number; icon: React.ReactNode; loading: boolean }) {
  return <Card><CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2"><CardTitle className="text-sm font-medium">{title}</CardTitle><span className="text-muted-foreground [&_svg]:h-4 [&_svg]:w-4">{icon}</span></CardHeader><CardContent><div className="text-2xl font-bold">{loading ? "..." : value ?? 0}</div></CardContent></Card>
}

function Empty({ text, action, onClick }: { text: string; action?: string; onClick?: () => void }) {
  return <div className="py-10 text-center"><p className="text-sm text-muted-foreground">{text}</p>{action && onClick && <Button className="mt-4" size="sm" onClick={onClick}><Plus />{action}</Button>}</div>
}

function Th({ children, align = "left" }: { children: React.ReactNode; align?: "left" | "right" }) { return <th className={`px-3 py-3 text-sm font-medium ${align === "right" ? "text-right" : "text-left"}`}>{children}</th> }
function Td({ children, align = "left", strong = false }: { children: React.ReactNode; align?: "left" | "right"; strong?: boolean }) { return <td className={`px-3 py-3 text-sm ${align === "right" ? "text-right" : "text-left"} ${strong ? "font-medium" : ""}`}>{children}</td> }
