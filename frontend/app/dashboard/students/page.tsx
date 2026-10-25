'use client';

import { useRef, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Edit, Eye, Loader2, Plus, Search, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';

import {
  Student,
  StudentDetailsDialog,
  StudentEditorDialog,
  StudentSaveRequest,
} from '@/components/students/StudentDialog';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { apiClient } from '@/lib/api/client';

interface StudentListPayload {
  students: Student[];
  total: number;
  page: number;
  limit: number;
}

interface ImportResult {
  total_rows: number;
  imported: number;
  failed: number;
  errors: Array<{ row: number; error: string; data: string }>;
}

const PAGE_SIZE = 20;
const selectClass = 'h-10 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring';

function csvCell(value: unknown): string {
  const text = value === null || value === undefined ? '' : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function downloadCsv(filename: string, rows: unknown[][]) {
  const content = `\uFEFF${rows.map((row) => row.map(csvCell).join(',')).join('\r\n')}`;
  const url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function StudentsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [submittedSearch, setSubmittedSearch] = useState('');
  const [grade, setGrade] = useState('');
  const [studentStatus, setStudentStatus] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [editor, setEditor] = useState<{ mode: 'create' | 'edit'; student: Student | null } | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState<Student | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const filters = {
    search: submittedSearch || undefined,
    grade: grade ? Number(grade) : undefined,
    status: studentStatus || undefined,
  };

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ['students', currentPage, filters],
    queryFn: async () => {
      const response = await apiClient.students.list({
        page: currentPage,
        limit: PAGE_SIZE,
        ...filters,
      });
      if (!response.success) throw new Error(response.error?.message ?? 'Unable to load students');
      return response.data as StudentListPayload;
    },
    placeholderData: keepPreviousData,
  });

  const saveStudent = useMutation({
    mutationFn: async ({ mode, student, request }: {
      mode: 'create' | 'edit';
      student: Student | null;
      request: StudentSaveRequest;
    }) => {
      const response = mode === 'create'
        ? await apiClient.students.create(request.payload)
        : await apiClient.students.update(student!.id, request.payload);

      if (!response.success) {
        throw new Error(response.error?.message ?? `Unable to ${mode} student`);
      }

      const savedStudent = response.data as Student;
      let photoWarning: string | null = null;
      if (request.photo) {
        const photoResponse = await apiClient.students.uploadPhoto(savedStudent.id, request.photo);
        if (!photoResponse.success) {
          photoWarning = photoResponse.error?.message ?? 'The student was saved, but the photo upload failed.';
        }
      }
      return { mode, photoWarning };
    },
    onSuccess: async ({ mode, photoWarning }) => {
      toast.success(mode === 'create' ? 'Student added successfully' : 'Student updated successfully');
      if (photoWarning) toast.warning(photoWarning);
      setEditor(null);
      await queryClient.invalidateQueries({ queryKey: ['students'] });
    },
    onError: (mutationError) => toast.error(mutationError.message),
  });

  const deleteStudent = useMutation({
    mutationFn: async (id: string) => {
      const response = await apiClient.students.delete(id);
      if (!response.success) throw new Error(response.error?.message ?? 'Unable to delete student');
    },
    onSuccess: async () => {
      toast.success('Student deleted successfully');
      if (students.length === 1 && currentPage > 1) setCurrentPage((page) => page - 1);
      await queryClient.invalidateQueries({ queryKey: ['students'] });
    },
    onError: (mutationError) => toast.error(mutationError.message),
  });

  const importStudents = useMutation({
    mutationFn: async (file: File) => {
      const response = await apiClient.students.bulkImport(file);
      if (!response.success) throw new Error(response.error?.message ?? 'Unable to import students');
      return response.data as ImportResult;
    },
    onSuccess: async (result) => {
      setImportResult(result);
      if (result.failed) {
        toast.warning(`Imported ${result.imported} students; ${result.failed} rows failed`);
      } else {
        toast.success(`Imported ${result.imported} students successfully`);
      }
      await queryClient.invalidateQueries({ queryKey: ['students'] });
    },
    onError: (mutationError) => toast.error(mutationError.message),
  });

  const students = data?.students ?? [];
  const totalPages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE));

  const handleSearch = () => {
    setCurrentPage(1);
    setSubmittedSearch(searchQuery.trim());
  };

  const clearFilters = () => {
    setSearchQuery('');
    setSubmittedSearch('');
    setGrade('');
    setStudentStatus('');
    setCurrentPage(1);
  };

  const handleView = async (studentId: string) => {
    setSelectedStudent(null);
    setDetailsOpen(true);
    setDetailsLoading(true);
    const response = await apiClient.students.get(studentId);
    setDetailsLoading(false);
    if (!response.success) {
      toast.error(response.error?.message ?? 'Unable to load student details');
      return;
    }
    setSelectedStudent(response.data as Student);
  };

  const handleDelete = (student: Student) => {
    if (!window.confirm(`Delete ${student.full_name_en}? This will deactivate the student record.`)) return;
    deleteStudent.mutate(student.id);
  };

  const handleImportFile = (file?: File) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.csv')) {
      toast.error('Please select a CSV file');
      return;
    }
    importStudents.mutate(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const downloadTemplate = () => {
    downloadCsv('student-import-template.csv', [
      ['full_name_en', 'full_name_np', 'gender', 'date_of_birth_ad', 'current_grade', 'current_section', 'roll_number', 'emis_student_id', 'admission_number', 'phone', 'caste_ethnicity'],
      ['Aarav Sharma', '', 'male', '2015-05-15', '5', 'A', '1', '', 'ADM-001', '9841000000', 'brahmin_hill'],
    ]);
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const exported: Student[] = [];
      let page = 1;
      let total = 0;
      do {
        const response = await apiClient.students.list({ page, limit: 100, ...filters });
        if (!response.success) throw new Error(response.error?.message ?? 'Unable to export students');
        const payload = response.data as StudentListPayload;
        exported.push(...payload.students);
        total = payload.total;
        page += 1;
      } while (exported.length < total);

      downloadCsv(`students-${new Date().toISOString().slice(0, 10)}.csv`, [
        ['full_name_en', 'full_name_np', 'gender', 'date_of_birth_ad', 'date_of_birth_bs', 'current_grade', 'current_section', 'roll_number', 'emis_student_id', 'admission_number', 'phone', 'email', 'status'],
        ...exported.map((student) => [
          student.full_name_en,
          student.full_name_np,
          student.gender,
          student.date_of_birth_ad,
          student.date_of_birth_bs,
          student.current_grade,
          student.current_section,
          student.roll_number,
          student.emis_student_id,
          student.admission_number,
          student.phone,
          student.email,
          student.status,
        ]),
      ]);
      toast.success(`Exported ${exported.length} students`);
    } catch (exportError) {
      toast.error(exportError instanceof Error ? exportError.message : 'Unable to export students');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Students</h1>
          <p className="text-muted-foreground">Manage student information and enrollment</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => { setImportResult(null); setImportOpen(true); }}>
            <Upload className="mr-2 h-4 w-4" />Import
          </Button>
          <Button variant="outline" onClick={handleExport} disabled={isExporting}>
            {isExporting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
            Export
          </Button>
          <Button onClick={() => setEditor({ mode: 'create', student: null })}>
            <Plus className="mr-2 h-4 w-4" />Add Student
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="mb-3 flex items-center gap-2"><h2 className="text-[17px] font-semibold tracking-tight">Student directory</h2><span className="rounded-full bg-accent px-2.5 py-1 text-[10px] font-medium text-primary">{data?.total ?? "…"} {data?.total === 1 ? "student" : "students"}</span></div>
          <div className="flex flex-col gap-3 lg:flex-row">
            <div className="relative min-w-0 flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                aria-label="Search students"
                placeholder="Search by name, ID, admission or roll number…"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                onKeyDown={(event) => event.key === 'Enter' && handleSearch()}
                className="pl-10"
              />
            </div>
            <select
              aria-label="Filter by grade"
              className={selectClass}
              value={grade}
              onChange={(event) => { setGrade(event.target.value); setCurrentPage(1); }}
            >
              <option value="">All grades</option>
              {Array.from({ length: 12 }, (_, index) => index + 1).map((value) => <option key={value} value={value}>Grade {value}</option>)}
            </select>
            <select
              aria-label="Filter by status"
              className={selectClass}
              value={studentStatus}
              onChange={(event) => { setStudentStatus(event.target.value); setCurrentPage(1); }}
            >
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
              <option value="transferred">Transferred</option>
              <option value="graduated">Graduated</option>
              <option value="dropped_out">Dropped out</option>
            </select>
            <Button onClick={handleSearch} disabled={isFetching}>Search</Button>
            {(submittedSearch || grade || studentStatus) && <Button variant="ghost" onClick={clearFilters}>Clear</Button>}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center text-muted-foreground"><Loader2 className="mr-2 h-5 w-5 animate-spin" />Loading students…</div>
          ) : error ? (
            <div className="flex h-64 items-center justify-center text-destructive">{error.message}</div>
          ) : students.length === 0 ? (
            <div className="flex h-64 flex-col items-center justify-center">
              <p className="text-muted-foreground">No students found</p>
              <Button className="mt-4" onClick={() => setEditor({ mode: 'create', student: null })}>
                <Plus className="mr-2 h-4 w-4" />Add Your First Student
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b">
                      <th className="px-4 py-3 text-left text-sm font-medium">Roll No</th>
                      <th className="px-4 py-3 text-left text-sm font-medium">Name</th>
                      <th className="px-4 py-3 text-left text-sm font-medium">EMIS ID</th>
                      <th className="px-4 py-3 text-left text-sm font-medium">Grade</th>
                      <th className="px-4 py-3 text-left text-sm font-medium">Section</th>
                      <th className="px-4 py-3 text-left text-sm font-medium">DOB (BS)</th>
                      <th className="px-4 py-3 text-left text-sm font-medium">Status</th>
                      <th className="px-4 py-3 text-right text-sm font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {students.map((student) => (
                      <tr key={student.id} className="border-b hover:bg-accent/50">
                        <td className="px-4 py-3 text-sm">{student.roll_number ?? '-'}</td>
                        <td className="px-4 py-3 text-sm font-medium"><div className="flex items-center gap-3"><span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-[#eee3fa] text-xs font-medium text-primary" aria-hidden="true">{student.full_name_en.split(" ").slice(0, 2).map((part) => part[0]).join("")}</span><span className="whitespace-nowrap">{student.full_name_en}</span></div></td>
                        <td className="px-4 py-3 text-sm">{student.emis_student_id || '-'}</td>
                        <td className="px-4 py-3 text-sm">{student.current_grade ?? '-'}</td>
                        <td className="px-4 py-3 text-sm">{student.current_section || '-'}</td>
                        <td className="px-4 py-3 text-sm">{student.date_of_birth_bs || '-'}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`inline-flex rounded-full px-2 py-1 text-xs font-medium ${student.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-800'}`}>
                            {student.status.replaceAll('_', ' ')}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="icon" title="View student" aria-label={`View ${student.full_name_en}`} onClick={() => handleView(student.id)}>
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" title="Edit student" aria-label={`Edit ${student.full_name_en}`} onClick={() => setEditor({ mode: 'edit', student })}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" title="Delete student" aria-label={`Delete ${student.full_name_en}`} onClick={() => handleDelete(student)} disabled={deleteStudent.isPending && deleteStudent.variables === student.id}>
                              {deleteStudent.isPending && deleteStudent.variables === student.id
                                ? <Loader2 className="h-4 w-4 animate-spin" />
                                : <Trash2 className="h-4 w-4 text-destructive" />}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex flex-col gap-3 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-muted-foreground">
                  {data?.total ?? 0} {data?.total === 1 ? "student" : "students"} · Page {currentPage} of {totalPages}
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setCurrentPage((page) => Math.max(1, page - 1))} disabled={currentPage === 1 || isFetching}>Previous</Button>
                  <Button variant="outline" size="sm" onClick={() => setCurrentPage((page) => Math.min(totalPages, page + 1))} disabled={currentPage === totalPages || isFetching}>Next</Button>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {editor && (
        <StudentEditorDialog
          key={`${editor.mode}-${editor.student?.id ?? 'new'}`}
          open
          mode={editor.mode}
          student={editor.student}
          saving={saveStudent.isPending}
          onOpenChange={(open) => !open && setEditor(null)}
          onSave={async (request) => {
            await saveStudent.mutateAsync({ mode: editor.mode, student: editor.student, request });
          }}
        />
      )}
      <StudentDetailsDialog open={detailsOpen} student={selectedStudent} loading={detailsLoading} onOpenChange={setDetailsOpen} />

      <Dialog open={importOpen} onOpenChange={(open) => !importStudents.isPending && setImportOpen(open)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Import students</DialogTitle>
            <DialogDescription>Upload a UTF-8 CSV file. Download the template to see the accepted columns and values.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Button variant="outline" onClick={downloadTemplate}><Download className="mr-2 h-4 w-4" />Download CSV template</Button>
            <input ref={fileInputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(event) => handleImportFile(event.target.files?.[0])} />
            <Button className="w-full" onClick={() => fileInputRef.current?.click()} disabled={importStudents.isPending}>
              {importStudents.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
              {importStudents.isPending ? 'Importing…' : 'Choose CSV file'}
            </Button>
            {importResult && (
              <div className="rounded-md border p-4 text-sm">
                <p><strong>{importResult.imported}</strong> imported, <strong>{importResult.failed}</strong> failed out of {importResult.total_rows} rows.</p>
                {importResult.errors.length > 0 && (
                  <ul className="mt-3 max-h-40 list-disc space-y-1 overflow-y-auto pl-5 text-destructive">
                    {importResult.errors.map((item) => <li key={`${item.row}-${item.data}`}>Row {item.row}: {item.error}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>
          <DialogFooter><DialogClose asChild><Button variant="outline">Close</Button></DialogClose></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
