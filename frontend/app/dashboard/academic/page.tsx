'use client';

import { useState, useEffect } from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Plus, GraduationCap, BookOpen, Users } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { toast } from 'sonner';

export default function AcademicPage() {
  const [grades, setGrades] = useState<any[]>([]);
  const [faculties, setFaculties] = useState<any[]>([]);

  useEffect(() => {
    fetchAcademicData();
  }, []);

  const fetchAcademicData = async () => {
    try {
      const [gradesRes, facultiesRes] = await Promise.all([
        apiClient.academic.grades.list(),
        apiClient.academic.faculties.list(),
      ]);

      if (gradesRes.success) {
        setGrades(gradesRes.data || []);
      }
      if (facultiesRes.success) {
        setFaculties(facultiesRes.data || []);
      }
    } catch (error) {
      toast.error('Error fetching academic data');
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Academic Management</h1>
            <p className="text-muted-foreground">
              Manage grades, sections, subjects, and curricula
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Grades</CardTitle>
              <GraduationCap className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">15</div>
              <p className="text-xs text-muted-foreground">Nursery to Grade 12</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Sections</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">45</div>
              <p className="text-xs text-muted-foreground">Across all grades</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Subjects</CardTitle>
              <BookOpen className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">32</div>
              <p className="text-xs text-muted-foreground">Active subjects</p>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Grades & Sections</CardTitle>
              <div className="flex gap-2">
                <Button variant="outline">
                  <Plus className="mr-2 h-4 w-4" />
                  Add Section
                </Button>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Grade
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {[
                { grade: 'Nursery', sections: 2, students: 45 },
                { grade: 'LKG', sections: 2, students: 52 },
                { grade: 'UKG', sections: 2, students: 48 },
                { grade: 'Grade 1', sections: 3, students: 95 },
                { grade: 'Grade 2', sections: 3, students: 88 },
                { grade: 'Grade 3', sections: 3, students: 92 },
                { grade: 'Grade 4', sections: 3, students: 85 },
                { grade: 'Grade 5', sections: 3, students: 90 },
                { grade: 'Grade 6', sections: 3, students: 82 },
                { grade: 'Grade 7', sections: 3, students: 78 },
                { grade: 'Grade 8', sections: 3, students: 75 },
                { grade: 'Grade 9', sections: 3, students: 72 },
                { grade: 'Grade 10', sections: 3, students: 68 },
                { grade: 'Grade 11', sections: 2, students: 45 },
                { grade: 'Grade 12', sections: 2, students: 35 },
              ].map((item) => (
                <div
                  key={item.grade}
                  className="flex items-center justify-between rounded-lg border p-4 hover:bg-accent/50"
                >
                  <div>
                    <h3 className="font-medium">{item.grade}</h3>
                    <p className="text-sm text-muted-foreground">
                      {item.sections} sections • {item.students} students
                    </p>
                  </div>
                  <Button variant="outline" size="sm">
                    Manage
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {faculties.length > 0 && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Higher Secondary Faculties (Grade 11-12)</CardTitle>
                <Button>
                  <Plus className="mr-2 h-4 w-4" />
                  Add Faculty
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {[
                  { name: 'Science', streams: ['Physics', 'Biology'], students: 42 },
                  { name: 'Management', streams: ['Accounting', 'Business'], students: 38 },
                  { name: 'Humanities', streams: ['Sociology', 'Psychology'], students: 0 },
                ].map((faculty) => (
                  <div key={faculty.name} className="rounded-lg border p-4">
                    <h3 className="font-medium">{faculty.name}</h3>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {faculty.streams.join(', ')}
                    </p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {faculty.students} students enrolled
                    </p>
                    <Button variant="outline" size="sm" className="mt-4 w-full">
                      Manage Streams
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
