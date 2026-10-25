import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AttendancePage from '../app/dashboard/attendance/page';
import ExamsPage from '../app/dashboard/exams/page';

afterEach(cleanup);

function roster(size = 125) {
  const reads = Array<number>(size).fill(0);
  const students = Array.from({ length: size }, (_, index) => ({
    id: `student-${index + 1}`, roll_number: index + 1,
    admission_number: `ADM-${index + 1}`, emis_student_id: null,
    // Accesses occur inside real row renders. Reset after mounting to catch
    // regressions in both memoization and the parent callback's stability.
    get full_name_en() { reads[index] += 1; return `Test Student ${index + 1}`; },
  }));
  return { students, reads, total: size };
}

function client() {
  const queryClient = new QueryClient({ defaultOptions: { queries: {
    staleTime: Infinity, retry: false, gcTime: Infinity,
    // Keep the monitored synthetic roster objects when seeding cache data.
    structuralSharing: false,
  } } });
  queryClient.setQueryData(['academic', 'grades'], [{
    id: 'grade-2', grade_number: 2, name_en: 'Grade 2', is_active: true,
    sections: [{ id: 'section-a', name: 'A', is_active: true }],
  }]);
  return queryClient;
}

test('attendance edits render one row, retain all 125 students and preserve other edits', () => {
  const queryClient = client();
  const data = roster();
  const date = new Date();
  const today = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  queryClient.setQueryData(['students', 'roster', 2, 'A'], data);
  queryClient.setQueryData(['calendar', 'ad-to-bs', today], {
    bs_date: { year: 2083, month: 7, day: 8 }, ad_date: { iso_date: today },
  });
  queryClient.setQueryData(['attendance', 'date', 2, 'A', today, 'daily'], { records: [] });
  const view = render(<QueryClientProvider client={queryClient}><AttendancePage /></QueryClientProvider>);
  assert.equal(view.getAllByLabelText(/^Attendance status for/).length, 125);
  data.reads.fill(0);
  const remarks = view.getByLabelText('Remarks for Test Student 1') as HTMLInputElement;
  fireEvent.change(remarks, { target: { value: 'Parent informed' } });
  assert.equal(remarks.value, 'Parent informed');
  assert.ok(data.reads[0] > 0);
  assert.equal(data.reads.slice(1).reduce((sum, count) => sum + count, 0), 0);
  fireEvent.change(view.getByLabelText('Attendance status for Test Student 1'), { target: { value: 'late' } });
  assert.equal(remarks.value, 'Parent informed');
  assert.equal((view.getByLabelText('Attendance status for Test Student 2') as HTMLSelectElement).value, 'present');
  queryClient.clear();
});

test('marks edits render one row and absence preserves entered marks and remarks', () => {
  const queryClient = client();
  const data = roster();
  queryClient.setQueryData(['students', 'roster', 2, 'A'], data);
  queryClient.setQueryData(['exams', '', ''], { exams: [{
    id: 'exam-1', name: 'Test Exam', exam_type: 'terminal', grade: 2, academic_year_bs: '2083',
    status: 'ongoing', is_locked: false,
    subjects: [{ id: 'exam-subject-1', subject_id: 'subject-1', full_marks: 100, pass_marks: 40 }],
  }], total: 1 });
  queryClient.setQueryData(['academic', 'subjects', 'grade-2'], [{ id: 'subject-1', name_en: 'Mathematics' }]);
  queryClient.setQueryData(['exams', 'marks', 'exam-subject-1'], { marks: [] });
  const view = render(<QueryClientProvider client={queryClient}><ExamsPage /></QueryClientProvider>);
  fireEvent.click(view.getByRole('button', { name: 'Marks entry' }));
  assert.equal(view.getAllByLabelText(/^Marks for/).length, 125);
  data.reads.fill(0);
  const marks = view.getByLabelText('Marks for Test Student 1') as HTMLInputElement;
  fireEvent.change(marks, { target: { value: '89.5' } });
  assert.equal(marks.value, '89.5');
  assert.ok(data.reads[0] > 0);
  assert.equal(data.reads.slice(1).reduce((sum, count) => sum + count, 0), 0);
  const remarks = view.getByLabelText('Remarks for Test Student 1') as HTMLInputElement;
  fireEvent.change(remarks, { target: { value: 'Checked' } });
  const absence = view.getAllByRole('checkbox')[0];
  fireEvent.click(absence);
  assert.equal(marks.disabled, true);
  fireEvent.click(absence);
  assert.equal(marks.value, '89.5');
  assert.equal(remarks.value, 'Checked');
  queryClient.clear();
});
