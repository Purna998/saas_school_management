'use client';

import { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, Search, Download, Upload, Edit, Trash2, Eye } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { toast } from 'sonner';

export default function StudentsPage() {
  const [students, setStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    fetchStudents();
  }, [currentPage]);

  const fetchStudents = async () => {
    setLoading(true);
    try {
      const response = await apiClient.students.list({
        page: currentPage,
        limit: 20,
      });

      if (response.success) {
        setStudents(response.data.items || response.data);
        setTotalPages(response.data.total_pages || 1);
      } else {
        toast.error('Failed to fetch students');
      }
    } catch (error) {
      toast.error('Error fetching students');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      fetchStudents();
      return;
    }

    try {
      const response = await apiClient.students.search(searchQuery);
      if (response.success) {
        setStudents(response.data);
      }
    } catch (error) {
      toast.error('Error searching students');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this student?')) return;

    try {
      const response = await apiClient.students.delete(id);
      if (response.success) {
        toast.success('Student deleted successfully');
        fetchStudents();
      } else {
        toast.error('Failed to delete student');
      }
    } catch (error) {
      toast.error('Error deleting student');
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Students</h1>
            <p className="text-muted-foreground">
              Manage student information and enrollment
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline">
              <Upload className="mr-2 h-4 w-4" />
              Import
            </Button>
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              Export
            </Button>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Student
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search students by name, EMIS ID, or roll number..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="pl-10"
                />
              </div>
              <Button onClick={handleSearch}>Search</Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex h-64 items-center justify-center">
                <div className="text-muted-foreground">Loading students...</div>
              </div>
            ) : students.length === 0 ? (
              <div className="flex h-64 flex-col items-center justify-center">
                <p className="text-muted-foreground">No students found</p>
                <Button className="mt-4">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Your First Student
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
                          <td className="px-4 py-3 text-sm">{student.roll_number || '-'}</td>
                          <td className="px-4 py-3 text-sm font-medium">
                            {student.full_name_en || student.full_name}
                          </td>
                          <td className="px-4 py-3 text-sm">{student.emis_id || '-'}</td>
                          <td className="px-4 py-3 text-sm">{student.grade || '-'}</td>
                          <td className="px-4 py-3 text-sm">{student.section || '-'}</td>
                          <td className="px-4 py-3 text-sm">{student.dob_bs || '-'}</td>
                          <td className="px-4 py-3 text-sm">
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                                student.status === 'active'
                                  ? 'bg-green-100 text-green-700'
                                  : 'bg-red-100 text-red-700'
                              }`}
                            >
                              {student.status || 'active'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <div className="flex justify-end gap-2">
                              <Button variant="ghost" size="icon">
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="icon">
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDelete(student.id)}
                              >
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {totalPages > 1 && (
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Page {currentPage} of {totalPages}
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        disabled={currentPage === 1}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        disabled={currentPage === totalPages}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
