import type { BillingResult, FeeAward, FeeHead, FeePayment, FeeReceipt, FeeRefund, FeeStatement, FeeStructure, FeeStudent, FeeSummary, OutstandingFees } from './fees';
import type { LibraryBook, LibraryBorrower, LibraryCopy, LibraryEvent, LibraryLoan, LibraryPolicy, LibraryStats } from './library';
import type { Hostel, HostelRoom, HostelBed, Resident, HostelStudent, HostelStats, HostelLeave, HostelVisit, RegisterRow, HostelEvent, HostelFeeOptions, HostelBill } from './hostel';
import type { TransportVehicle,TransportRoute,TransportStop,TransportRun,TransportStudent,TransportAssignment,TransportTrip,TransportPassenger,TransportMaintenance,TransportPosition,TransportStats,TransportEvent,TransportFeeOptions,TransportBill } from './transport';
import type { FamilyAccess, PhoneGrant, TrackingFeed } from './tracking';
import type { ReportCatalog, ReportFilters, ReportPreview, SavedReport, ReportDetail, ReportStudentOption, ReportExamOption } from './reports';

export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T;
  meta?: {
    page?: number;
    limit?: number;
    total?: number;
    total_pages?: number;
    has_next?: boolean;
    has_previous?: boolean;
  } | null;
  error?: {
    code?: string;
    message: string;
    details?: unknown;
  } | null;
}

export interface StudentRosterEntry {
  id: string;
  full_name_en: string;
  roll_number: number | null;
  admission_number: string | null;
  emis_student_id: string | null;
}

export interface StudentRoster {
  students: StudentRosterEntry[];
  total: number;
}

type QueryValue = string | number | boolean | null | undefined;
type QueryParams = Record<string, QueryValue | QueryValue[]>;

interface RequestOptions {
  responseType?: 'json' | 'blob';
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  path: string;
  data?: unknown;
  params?: QueryParams;
  retryingAfterRefresh?: boolean;
}

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? '/backend').replace(/\/$/, '');

type ApiModule =
  | 'auth'
  | 'tenant'
  | 'student'
  | 'academic'
  | 'attendance'
  | 'exam'
  | 'fee'
  | 'staff'
  | 'library'
  | 'hostel'
  | 'transport'
  | 'report'
  | 'calendar';

interface LoginPayload {
  user: {
    id: string;
    email: string;
    full_name_en: string;
    full_name_np?: string;
    school_id: string;
    roles: string[];
    permissions?: string[];
  };
  tokens: {
    access_token: string;
    refresh_token: string;
    token_type: string;
    expires_in: number;
  };
}

function buildUrl(path: string, params?: QueryParams): string {
  const search = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, rawValue]) => {
    const values = Array.isArray(rawValue) ? rawValue : [rawValue];
    values.forEach((value) => {
      if (value !== undefined && value !== null && value !== '') {
        search.append(key, String(value));
      }
    });
  });
  const query = search.toString();
  return `${API_BASE_URL}${path}${query ? `?${query}` : ''}`;
}

function normalizeResponse<T>(payload: unknown, ok: boolean): ApiResponse<T> {
  if (payload && typeof payload === 'object' && 'success' in payload) {
    return payload as ApiResponse<T>;
  }

  if (payload && typeof payload === 'object' && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (detail && typeof detail === 'object' && 'success' in detail) {
      return detail as ApiResponse<T>;
    }
  }

  if (ok) return { success: true, data: payload as T, error: null };

  const detail = payload && typeof payload === 'object' && 'detail' in payload
    ? (payload as { detail?: unknown }).detail
    : undefined;
  return {
    success: false,
    data: null as T,
    error: {
      code: 'HTTP_ERROR',
      message: typeof detail === 'string' ? detail : Array.isArray(detail)
        ? detail.slice(0, 3).map((issue: { loc?: Array<string | number>; msg?: string }) => {
          const field = issue.loc?.at(-1);
          const label = typeof field === 'string' ? `${field.replaceAll('_', ' ')}: ` : '';
          return `${label}${(issue.msg ?? 'Invalid value').replace(/^Value error,\s*/, '')}`;
        }).join('; ') : 'Request failed',
      details: detail,
    },
  };
}

class ApiClient {
  private readonly inFlightGets = new Map<string, Promise<ApiResponse<unknown>>>();
  private refreshPromise: Promise<string> | null = null;

  private clearSession(): void {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    localStorage.removeItem('tenant_id');
  }

  private async refreshAccessToken(): Promise<string> {
    if (this.refreshPromise) return this.refreshPromise;

    this.refreshPromise = (async () => {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) throw new Error('No refresh token');

      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      const payload = normalizeResponse<{
        access_token: string;
        refresh_token: string;
      }>(await response.json(), response.ok);

      if (!response.ok || !payload.success) {
        throw new Error(payload.error?.message ?? 'Token refresh failed');
      }

      localStorage.setItem('access_token', payload.data.access_token);
      localStorage.setItem('refresh_token', payload.data.refresh_token);
      return payload.data.access_token;
    })().finally(() => {
      this.refreshPromise = null;
    });

    return this.refreshPromise;
  }

  private async performRequest<T>(_module: ApiModule, options: RequestOptions): Promise<ApiResponse<T>> {
    const method = options.method ?? 'GET';
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 30_000);
    const token = localStorage.getItem('access_token');
    const tenantId = localStorage.getItem('tenant_id');
    const headers: Record<string, string> = { Accept: 'application/json' };

    const isFormData = options.data instanceof FormData;
    const body: BodyInit | undefined = options.data === undefined
      ? undefined
      : options.data instanceof FormData
        ? options.data
        : JSON.stringify(options.data);
    if (options.data !== undefined && !isFormData) headers['Content-Type'] = 'application/json';
    if (token) headers.Authorization = `Bearer ${token}`;
    if (tenantId) headers['X-Tenant-ID'] = tenantId;

    try {
      const response = await fetch(buildUrl(options.path, options.params), {
        method,
        headers,
        body,
        signal: controller.signal,
      });

      if (response.status === 401 && !options.retryingAfterRefresh) {
        try {
          await this.refreshAccessToken();
          return this.performRequest<T>(_module, { ...options, retryingAfterRefresh: true });
        } catch (error) {
          this.clearSession();
          // A full same-origin navigation discards the expired session's
          // in-memory queries and pending UI state, including on refresh failure.
          if (window.location.pathname !== '/auth/login') {
            window.location.assign(new URL('/auth/login', window.location.origin).href);
          }
          throw error;
        }
      }

      const payload = response.status === 204 ? null : options.responseType === 'blob' && response.ok ? await response.blob() : await response.json();
      return normalizeResponse<T>(payload, response.ok);
    } catch (error) {
      return {
        success: false,
        data: null as T,
        error: {
          code: error instanceof DOMException && error.name === 'AbortError' ? 'TIMEOUT' : 'NETWORK_ERROR',
          message: error instanceof Error ? error.message : 'Network error occurred',
        },
      };
    } finally {
      window.clearTimeout(timeoutId);
    }
  }

  request<T = unknown>(module: ApiModule, options: RequestOptions): Promise<ApiResponse<T>> {
    const method = options.method ?? 'GET';
    if (method !== 'GET') return this.performRequest<T>(module, options);

    const url = buildUrl(options.path, options.params);
    // Deduplicate within one login only; another user in the same school must
    // never receive a request that started under the previous user's token.
    const key = `${localStorage.getItem('tenant_id') ?? ''}:${localStorage.getItem('access_token') ?? ''}:${options.responseType ?? 'json'}:${url}`;
    const existing = this.inFlightGets.get(key);
    if (existing) return existing as Promise<ApiResponse<T>>;

    const request = this.performRequest<T>(module, options);
    this.inFlightGets.set(key, request as Promise<ApiResponse<unknown>>);
    void request.finally(() => {
      if (this.inFlightGets.get(key) === request) this.inFlightGets.delete(key);
    });
    return request;
  }

  auth = {
    login: (email: string, password: string) =>
      this.request<LoginPayload>('auth', { method: 'POST', path: '/api/v1/auth/login', data: { email, password } }),
    logout: () => this.request('auth', { method: 'POST', path: '/api/v1/auth/logout', data: { revoke_all_sessions: false } }),
    getCurrentUser: () => this.request('auth', { path: '/api/v1/users/me' }),
    changePassword: (currentPassword: string, newPassword: string) =>
      this.request('auth', { method: 'POST', path: '/api/v1/users/me/change-password', data: { current_password: currentPassword, new_password: newPassword } }),
  };

  students = {
    roster: (grade: number, section?: string) => this.request<StudentRoster>('student', {
      path: '/api/v1/students/roster', params: { grade, section },
    }),
    list: (params?: QueryParams) => this.request('student', { path: '/api/v1/students', params }),
    get: (id: string) => this.request('student', { path: `/api/v1/students/${id}` }),
    create: (data: unknown) => this.request('student', { method: 'POST', path: '/api/v1/students', data }),
    update: (id: string, data: unknown) => this.request('student', { method: 'PATCH', path: `/api/v1/students/${id}`, data }),
    delete: (id: string) => this.request('student', { method: 'DELETE', path: `/api/v1/students/${id}` }),
    search: (query: string) => this.request('student', { path: '/api/v1/students/search', params: { q: query } }),
    bulkImport: (file: File) => {
      const data = new FormData();
      data.append('file', file);
      return this.request<{
        total_rows: number;
        imported: number;
        failed: number;
        errors: Array<{ row: number; error: string; data: string }>;
      }>('student', { method: 'POST', path: '/api/v1/students/bulk-import', data });
    },
    uploadPhoto: (studentId: string, file: File) => {
      const data = new FormData();
      data.append('file', file);
      return this.request<{ photo_url: string }>('student', {
        method: 'POST',
        path: `/api/v1/students/${studentId}/upload-photo`,
        data,
      });
    },
  };

  staff = {
    list: (params?: QueryParams) => this.request('staff', { path: '/api/v1/staff', params }),
    get: (id: string) => this.request('staff', { path: `/api/v1/staff/${id}` }),
    create: (data: unknown) => this.request('staff', { method: 'POST', path: '/api/v1/staff', data }),
    update: (id: string, data: unknown) => this.request('staff', { method: 'PATCH', path: `/api/v1/staff/${id}`, data }),
    delete: (id: string) => this.request('staff', { method: 'DELETE', path: `/api/v1/staff/${id}` }),
  };

  academic = {
    overview: () => this.request('academic', { path: '/api/v1/academic/overview' }),
    grades: {
      list: () => this.request('academic', { path: '/api/v1/academic/grades' }),
      get: (id: string) => this.request('academic', { path: `/api/v1/academic/grades/${id}` }),
      create: (data: unknown) => this.request('academic', { method: 'POST', path: '/api/v1/academic/grades', data }),
      update: (id: string, data: unknown) => this.request('academic', { method: 'PATCH', path: `/api/v1/academic/grades/${id}`, data }),
      delete: (id: string) => this.request('academic', { method: 'DELETE', path: `/api/v1/academic/grades/${id}` }),
    },
    sections: {
      list: (gradeId: string) => this.request('academic', { path: `/api/v1/academic/grades/${gradeId}/sections` }),
      create: (data: unknown) => this.request('academic', { method: 'POST', path: '/api/v1/academic/sections', data }),
      update: (id: string, data: unknown) => this.request('academic', { method: 'PATCH', path: `/api/v1/academic/sections/${id}`, data }),
      delete: (id: string) => this.request('academic', { method: 'DELETE', path: `/api/v1/academic/sections/${id}` }),
    },
    subjects: {
      list: (gradeId: string) => this.request('academic', { path: `/api/v1/academic/grades/${gradeId}/subjects` }),
      create: (data: unknown) => this.request('academic', { method: 'POST', path: '/api/v1/academic/subjects', data }),
      update: (id: string, data: unknown) => this.request('academic', { method: 'PATCH', path: `/api/v1/academic/subjects/${id}`, data }),
      delete: (id: string) => this.request('academic', { method: 'DELETE', path: `/api/v1/academic/subjects/${id}` }),
    },
    faculties: {
      list: () => this.request('academic', { path: '/api/v1/academic/faculties' }),
      create: (data: unknown) => this.request('academic', { method: 'POST', path: '/api/v1/academic/faculties', data }),
      update: (id: string, data: unknown) => this.request('academic', { method: 'PATCH', path: `/api/v1/academic/faculties/${id}`, data }),
      delete: (id: string) => this.request('academic', { method: 'DELETE', path: `/api/v1/academic/faculties/${id}` }),
    },
    streams: {
      create: (data: unknown) => this.request('academic', { method: 'POST', path: '/api/v1/academic/streams', data }),
      update: (id: string, data: unknown) => this.request('academic', { method: 'PATCH', path: `/api/v1/academic/streams/${id}`, data }),
      delete: (id: string) => this.request('academic', { method: 'DELETE', path: `/api/v1/academic/streams/${id}` }),
    },
  };

  attendance = {
    mark: (data: unknown) => this.request('attendance', { method: 'POST', path: '/api/v1/attendance/mark', data }),
    getByClass: (params: { date_ad: string; grade: string; section: string; period_number?: number }) =>
      this.request('attendance', { path: '/api/v1/attendance/date', params }),
    getStudentHistory: (studentId: string, startDate: string, endDate: string) =>
      this.request('attendance', {
        path: `/api/v1/attendance/student/${studentId}`,
        params: { start_date: startDate, end_date: endDate },
      }),
    getReport: (params: { grade: string; section: string; year_bs: number; month_bs: number }) =>
      this.request('attendance', { path: '/api/v1/attendance/summary', params }),
    update: (id: string, data: unknown) =>
      this.request('attendance', { method: 'PATCH', path: `/api/v1/attendance/${id}`, data }),
  };

  exams = {
    list: (params?: QueryParams) => this.request('exam', { path: '/api/v1/exams/', params }),
    get: (examId: string) => this.request('exam', { path: `/api/v1/exams/${examId}` }),
    create: (data: unknown) => this.request('exam', { method: 'POST', path: '/api/v1/exams/', data }),
    update: (examId: string, data: unknown) => this.request('exam', { method: 'PATCH', path: `/api/v1/exams/${examId}`, data }),
    delete: (examId: string) => this.request('exam', { method: 'DELETE', path: `/api/v1/exams/${examId}` }),
    updateStatus: (examId: string, status: string) => this.request('exam', { method: 'PATCH', path: `/api/v1/exams/${examId}/status`, data: { status } }),
    enterMarks: (data: unknown) => this.request('exam', { method: 'POST', path: '/api/v1/exams/marks', data }),
    getMarks: (examSubjectId: string) => this.request('exam', { path: `/api/v1/exams/marks/subject/${examSubjectId}` }),
    getResults: (examId: string, params?: QueryParams) => this.request('exam', { path: `/api/v1/exams/${examId}/results`, params }),
    getReportCard: (studentId: string, examId: string) => this.request('exam', { path: `/api/v1/exams/report-card/${studentId}`, params: { exam_id: examId } }),
    calculate: (examId: string) => this.request('exam', { method: 'POST', path: `/api/v1/exams/${examId}/calculate` }),
    publish: (examId: string) => this.request('exam', { method: 'POST', path: `/api/v1/exams/${examId}/publish` }),
  };

  fees = {
    structures: {
      list: (params?: QueryParams) => this.request<FeeStructure[]>('fee', { path: '/api/v1/fees/structures', params }),
      create: (data: unknown) => this.request<FeeStructure>('fee', { method: 'POST', path: '/api/v1/fees/structures', data }),
      update: (id: string, data: unknown) => this.request<FeeStructure>('fee', { method: 'PATCH', path: `/api/v1/fees/structures/${id}`, data }),
      addHead: (id: string, data: unknown) => this.request<FeeHead>('fee', { method: 'POST', path: `/api/v1/fees/structures/${id}/heads`, data }),
      updateHead: (id: string, headId: string, data: unknown) => this.request<FeeHead>('fee', { method: 'PUT', path: `/api/v1/fees/structures/${id}/heads/${headId}`, data }),
      deleteHead: (id: string, headId: string) => this.request('fee', { method: 'DELETE', path: `/api/v1/fees/structures/${id}/heads/${headId}` }),
    },
    students: (params?: QueryParams) => this.request<FeeStudent[]>('fee', { path: '/api/v1/fees/students', params }),
    roster: (grade: number, section?: string) => this.request<StudentRoster>('fee', { path: '/api/v1/fees/roster', params: { grade, section } }),
    generate: (data: unknown) => this.request<BillingResult>('fee', { method: 'POST', path: '/api/v1/fees/generate-ledger', data }),
    collect: (data: unknown) => this.request<FeePayment>('fee', { method: 'POST', path: '/api/v1/fees/collect', data }),
    ledger: (studentId: string, year?: string) => this.request<FeeStatement>('fee', { path: `/api/v1/fees/student/${studentId}`, params: { academic_year_bs: year } }),
    payments: (params?: QueryParams) => this.request<{ payments: FeePayment[]; total: number; page: number; limit: number }>('fee', { path: '/api/v1/fees/payments', params }),
    receipt: (id: string) => this.request<FeeReceipt>('fee', { path: `/api/v1/fees/payments/${id}/receipt` }),
    refund: (id: string, data: unknown) => this.request<FeeRefund>('fee', { method: 'POST', path: `/api/v1/fees/payments/${id}/refunds`, data }),
    summary: (year: string) => this.request<FeeSummary>('fee', { path: '/api/v1/fees/collection-summary', params: { academic_year_bs: year } }),
    outstanding: (params?: QueryParams) => this.request<OutstandingFees>('fee', { path: '/api/v1/fees/outstanding', params }),
    scholarships: (params?: QueryParams) => this.request<{ scholarships: FeeAward[]; total: number; page: number; limit: number }>('fee', { path: '/api/v1/fees/scholarships', params }),
    award: (data: unknown) => this.request<FeeAward>('fee', { method: 'POST', path: '/api/v1/fees/scholarships', data }),
    reverseAward: (id: string, reason: string) => this.request<FeeAward>('fee', { method: 'POST', path: `/api/v1/fees/scholarships/${id}/reverse`, data: { reason } }),
  };

  library = {
    books: {
      list: (params?: QueryParams) => this.request<{ books: LibraryBook[]; total: number; page: number; limit: number }>('library', { path: '/api/v1/library/books', params }),
      get: (id: string) => this.request<LibraryBook>('library', { path: `/api/v1/library/books/${id}` }),
      create: (data: unknown) => this.request<LibraryBook>('library', { method: 'POST', path: '/api/v1/library/books', data }),
      update: (id: string, data: unknown) => this.request<LibraryBook>('library', { method: 'PATCH', path: `/api/v1/library/books/${id}`, data }),
    },
    copies: (id: string, params?: QueryParams) => this.request<{ copies: LibraryCopy[]; total: number; page: number; limit: number }>('library', { path: `/api/v1/library/books/${id}/copies`, params }),
    addCopies: (id: string, data: unknown) => this.request<LibraryBook>('library', { method: 'POST', path: `/api/v1/library/books/${id}/copies`, data }),
    updateCopy: (id: string, data: unknown) => this.request<LibraryCopy>('library', { method: 'PATCH', path: `/api/v1/library/copies/${id}`, data }),
    borrowers: (params?: QueryParams) => this.request<{ borrowers: LibraryBorrower[]; total: number; page: number; limit: number }>('library', { path: '/api/v1/library/borrowers', params }),
    issue: (data: unknown) => this.request<LibraryLoan>('library', { method: 'POST', path: '/api/v1/library/issue', data }),
    return: (data: unknown) => this.request<LibraryLoan>('library', { method: 'POST', path: '/api/v1/library/return', data }),
    loans: (params?: QueryParams) => this.request<{ issues: LibraryLoan[]; total: number; page: number; limit: number }>('library', { path: '/api/v1/library/issued', params }),
    loan: (id: string) => this.request<LibraryLoan>('library', { path: `/api/v1/library/issued/${id}` }),
    renew: (id: string, data: unknown) => this.request<LibraryLoan>('library', { method: 'POST', path: `/api/v1/library/issued/${id}/renew`, data }),
    lost: (id: string, data: unknown) => this.request<LibraryLoan>('library', { method: 'POST', path: `/api/v1/library/issued/${id}/lost`, data }),
    policy: () => this.request<LibraryPolicy>('library', { path: '/api/v1/library/policy' }),
    updatePolicy: (data: unknown) => this.request<LibraryPolicy>('library', { method: 'PUT', path: '/api/v1/library/policy', data }),
    stats: () => this.request<LibraryStats>('library', { path: '/api/v1/library/stats' }),
    history: (params?: QueryParams) => this.request<{ events: LibraryEvent[]; total: number; page: number; limit: number }>('library', { path: '/api/v1/library/history', params }),
    export: (params: QueryParams) => this.request<Blob>('library', { path: '/api/v1/library/export', params, responseType: 'blob' }),
  };

  hostel = {
    get: (id: string) => this.request<Hostel>('hostel', { path: `/api/v1/hostel/hostels/${id}` }),
    hostels: (params?: QueryParams) => this.request<{ hostels: Hostel[]; total: number }>('hostel', { path: '/api/v1/hostel/hostels', params }),
    create: (data: unknown) => this.request<Hostel>('hostel', { method: 'POST', path: '/api/v1/hostel/hostels', data }),
    update: (id: string, data: unknown) => this.request<Hostel>('hostel', { method: 'PATCH', path: `/api/v1/hostel/hostels/${id}`, data }),
    rooms: (params?: QueryParams) => this.request<{ rooms: HostelRoom[]; total: number }>('hostel', { path: '/api/v1/hostel/rooms', params }),
    createRoom: (data: unknown) => this.request<HostelRoom>('hostel', { method: 'POST', path: '/api/v1/hostel/rooms', data }),
    updateRoom: (id: string, data: unknown) => this.request<HostelRoom>('hostel', { method: 'PATCH', path: `/api/v1/hostel/rooms/${id}`, data }),
    beds: (id: string, params?: QueryParams) => this.request<{ room: HostelRoom; hostel: Hostel; beds: HostelBed[]; total: number }>('hostel', { path: `/api/v1/hostel/rooms/${id}/beds`, params }),
    addBeds: (id: string, data: unknown) => this.request<HostelRoom>('hostel', { method: 'POST', path: `/api/v1/hostel/rooms/${id}/beds`, data }),
    updateBed: (id: string, data: unknown) => this.request<HostelBed>('hostel', { method: 'PATCH', path: `/api/v1/hostel/beds/${id}`, data }),
    students: (params?: QueryParams) => this.request<{ students: HostelStudent[]; total: number }>('hostel', { path: '/api/v1/hostel/students', params }),
    residents: (params?: QueryParams) => this.request<{ residents: Resident[]; total: number }>('hostel', { path: '/api/v1/hostel/allocations', params }),
    resident: (id: string) => this.request<Resident>('hostel', { path: `/api/v1/hostel/allocations/${id}` }),
    allocate: (data: unknown) => this.request<Resident>('hostel', { method: 'POST', path: '/api/v1/hostel/allocate', data }),
    transfer: (id: string, data: unknown) => this.request<Resident>('hostel', { method: 'POST', path: `/api/v1/hostel/allocations/${id}/transfer`, data }),
    vacate: (id: string, data: unknown) => this.request<Resident>('hostel', { method: 'POST', path: `/api/v1/hostel/vacate/${id}`, data }),
    leaves: (params?: QueryParams) => this.request<{ records: HostelLeave[]; total: number }>('hostel', { path: '/api/v1/hostel/leaves', params }),
    leave: (id: string, data: unknown) => this.request<HostelLeave>('hostel', { method: 'POST', path: `/api/v1/hostel/allocations/${id}/leave`, data }),
    returnLeave: (id: string, data: unknown) => this.request<HostelLeave>('hostel', { method: 'POST', path: `/api/v1/hostel/leaves/${id}/return`, data }),
    visits: (params?: QueryParams) => this.request<{ records: HostelVisit[]; total: number }>('hostel', { path: '/api/v1/hostel/visits', params }),
    visit: (data: unknown) => this.request<HostelVisit>('hostel', { method: 'POST', path: '/api/v1/hostel/visits', data }),
    depart: (id: string, data: unknown) => this.request<HostelVisit>('hostel', { method: 'POST', path: `/api/v1/hostel/visits/${id}/depart`, data }),
    register: (params?: QueryParams) => this.request<{ entries: RegisterRow[]; total: number; date_ad: string; date_bs: string; session: string }>('hostel', { path: '/api/v1/hostel/register', params }),
    saveRegister: (data: unknown) => this.request<{ saved: number }>('hostel', { method: 'POST', path: '/api/v1/hostel/register', data }),
    feeOptions: (id: string, month: string) => this.request<HostelFeeOptions>('hostel', { path: `/api/v1/hostel/allocations/${id}/fee-options`, params: { month_bs: month } }),
    bill: (id: string, data: unknown) => this.request<HostelBill>('hostel', { method: 'POST', path: `/api/v1/hostel/allocations/${id}/bill`, data }),
    stats: (params?: QueryParams) => this.request<HostelStats>('hostel', { path: '/api/v1/hostel/occupancy', params }),
    history: (params?: QueryParams) => this.request<{ events: HostelEvent[]; total: number }>('hostel', { path: '/api/v1/hostel/history', params }),
    export: (params: QueryParams) => this.request<Blob>('hostel', { path: '/api/v1/hostel/export', params, responseType: 'blob' }),
  };

  tracking = {
    live: (page = 1) => this.request<TrackingFeed>('transport', { path: '/api/v1/transport/live', params: { page } }),
    families: (page = 1) => this.request<{links: FamilyAccess[]; total: number}>('transport', { path: '/api/v1/transport/family-access', params: { page } }),
    link: (data: unknown) => this.request<Pick<FamilyAccess, 'id' | 'student_name' | 'parent_email' | 'notes'>>('transport', { method: 'POST', path: '/api/v1/transport/family-access', data }),
    unlink: (id: string, data: unknown) => this.request('transport', { method: 'POST', path: `/api/v1/transport/family-access/${id}/revoke`, data }),
    issuePhone: (id: string, label: string) => this.request<PhoneGrant>('transport', { method: 'POST', path: `/api/v1/transport/trips/${id}/phone`, data: { label } }),
    revokePhone: (id: string) => this.request('transport', { method: 'POST', path: `/api/v1/transport/trips/${id}/phone/revoke` }),
  };

  transport = {
    vehicles: {
      list: (params?:QueryParams) => this.request<{vehicles:TransportVehicle[];total:number}>('transport', { path: '/api/v1/transport/vehicles',params }),
      get:(id:string)=>this.request<TransportVehicle>('transport',{path:`/api/v1/transport/vehicles/${id}`}),
      create: (data: unknown) => this.request<TransportVehicle>('transport', { method: 'POST', path: '/api/v1/transport/vehicles', data }),
      update:(id:string,data:unknown)=>this.request<TransportVehicle>('transport',{method:'PATCH',path:`/api/v1/transport/vehicles/${id}`,data}),
    },
    routes: {
      list: (params?:QueryParams) => this.request<{routes:TransportRoute[];total:number}>('transport', { path: '/api/v1/transport/routes',params }),
      get:(id:string)=>this.request<TransportRoute>('transport',{path:`/api/v1/transport/routes/${id}`}),
      create: (data: unknown) => this.request<TransportRoute>('transport', { method: 'POST', path: '/api/v1/transport/routes', data }),
      update:(id:string,data:unknown)=>this.request<TransportRoute>('transport',{method:'PATCH',path:`/api/v1/transport/routes/${id}`,data}),
    },
    createStop:(id:string,data:unknown)=>this.request<TransportStop>('transport',{method:'POST',path:`/api/v1/transport/routes/${id}/stops`,data}),
    updateStop:(id:string,data:unknown)=>this.request<TransportStop>('transport',{method:'PATCH',path:`/api/v1/transport/stops/${id}`,data}),
    reorder:(id:string,data:unknown)=>this.request('transport',{method:'POST',path:`/api/v1/transport/routes/${id}/stop-order`,data}),
    runs:(params?:QueryParams)=>this.request<{runs:TransportRun[];total:number}>('transport',{path:'/api/v1/transport/runs',params}),
    run:(id:string)=>this.request<TransportRun>('transport',{path:`/api/v1/transport/runs/${id}`}),
    createRun:(data:unknown)=>this.request<TransportRun>('transport',{method:'POST',path:'/api/v1/transport/runs',data}),
    updateRun:(id:string,data:unknown)=>this.request<TransportRun>('transport',{method:'PATCH',path:`/api/v1/transport/runs/${id}`,data}),
    students:(params?:QueryParams)=>this.request<{students:TransportStudent[];total:number}>('transport',{path:'/api/v1/transport/students',params}),
    quote:(data:unknown)=>this.request<{monthly_fee:string|null;requires_agreed_price:boolean}>('transport',{method:'POST',path:'/api/v1/transport/quote',data}),
    assignments:(params?:QueryParams)=>this.request<{assignments:TransportAssignment[];total:number}>('transport',{path:'/api/v1/transport/assignments',params}),
    assignment:(id:string)=>this.request<TransportAssignment>('transport',{path:`/api/v1/transport/assignments/${id}`}),
    assign:(data:unknown)=>this.request<TransportAssignment>('transport',{method:'POST',path:'/api/v1/transport/assign',data}),
    change:(id:string,data:unknown)=>this.request<TransportAssignment>('transport',{method:'POST',path:`/api/v1/transport/assignments/${id}/change`,data}),
    end:(id:string,data:unknown)=>this.request<TransportAssignment>('transport',{method:'POST',path:`/api/v1/transport/assignments/${id}/end`,data}),
    trips:(params?:QueryParams)=>this.request<{trips:TransportTrip[];total:number}>('transport',{path:'/api/v1/transport/trips',params}),
    trip:(id:string,params?:QueryParams)=>this.request<{trip:TransportTrip;passengers:TransportPassenger[];total:number;counts:Record<string,number>}>('transport',{path:`/api/v1/transport/trips/${id}`,params}),
    startTrip:(data:unknown)=>this.request<TransportTrip>('transport',{method:'POST',path:'/api/v1/transport/trips',data}),
    passenger:(id:string,data:unknown)=>this.request<TransportPassenger>('transport',{method:'POST',path:`/api/v1/transport/passengers/${id}`,data}),
    complete:(id:string,data:unknown)=>this.request<TransportTrip>('transport',{method:'POST',path:`/api/v1/transport/trips/${id}/complete`,data}),
    cancel:(id:string,data:unknown)=>this.request<TransportTrip>('transport',{method:'POST',path:`/api/v1/transport/trips/${id}/cancel`,data}),
    maintenance:(id:string,params?:QueryParams)=>this.request<{records:TransportMaintenance[];total:number}>('transport',{path:`/api/v1/transport/vehicles/${id}/maintenance`,params}),
    recordMaintenance:(id:string,data:unknown)=>this.request<TransportMaintenance>('transport',{method:'POST',path:`/api/v1/transport/vehicles/${id}/maintenance`,data}),
    location:(id:string)=>this.request<{position:TransportPosition|null}>('transport',{path:`/api/v1/transport/vehicles/${id}/location`}),
    position:(id:string,data:unknown)=>this.request<TransportPosition>('transport',{method:'POST',path:`/api/v1/transport/vehicles/${id}/location`,data}),
    feeOptions:(id:string,month:string)=>this.request<TransportFeeOptions>('transport',{path:`/api/v1/transport/assignments/${id}/fee-options`,params:{month_bs:month}}),
    bill:(id:string,data:unknown)=>this.request<TransportBill>('transport',{method:'POST',path:`/api/v1/transport/assignments/${id}/bill`,data}),
    stats:()=>this.request<TransportStats>('transport',{path:'/api/v1/transport/stats'}),
    history:(params?:QueryParams)=>this.request<{events:TransportEvent[];total:number}>('transport',{path:'/api/v1/transport/history',params}),
    export:(params:QueryParams)=>this.request<Blob>('transport',{path:'/api/v1/transport/export',params,responseType:'blob'}),
  };

  calendar = {
    convertBsToAd: (date: string) => {
      const [year, month, day] = date.split('-').map(Number);
      return this.request('calendar', { path: '/api/v1/calendar/convert/bs-to-ad', params: { year, month, day } });
    },
    convertAdToBs: (date: string) => {
      const [year, month, day] = date.split('-').map(Number);
      return this.request('calendar', { path: '/api/v1/calendar/convert/ad-to-bs', params: { year, month, day } });
    },
    getCurrentBs: () => this.request('calendar', { path: '/api/v1/calendar/current-bs' }),
    getCurrentAcademicYear: () => this.request('calendar', { path: '/api/v1/calendar/current-academic-year' }),
  };

  tenant = {
    list: (params?: QueryParams) => this.request('tenant', { path: '/api/v1/tenants/', params }),
    create: (data: unknown) => this.request('tenant', { method: 'POST', path: '/api/v1/tenants/', data }),
    get: (id: string) => this.request('tenant', { path: `/api/v1/tenants/${id}` }),
    update: (id: string, data: unknown) => this.request('tenant', { method: 'PATCH', path: `/api/v1/tenants/${id}`, data }),
    toggleHigherSecondary: (id: string, enabled: boolean) =>
      this.request('tenant', { method: 'PATCH', path: `/api/v1/tenants/${id}/settings/higher-secondary`, data: { hs_enabled: enabled } }),
  };

  reports = {
    catalog: () => this.request<ReportCatalog>('report', { path: '/api/v1/reports/catalog' }),
    preview: (data: ReportFilters, page = 1) => this.request<ReportPreview>('report', { method: 'POST', path: '/api/v1/reports/preview', data, params: { page } }),
    generate: (data: ReportFilters & { request_id: string; title?: string; file_format: 'csv' | 'excel' }) => this.request<SavedReport>('report', { method: 'POST', path: '/api/v1/reports/generate', data }),
    list: (params?: QueryParams) => this.request<{ reports: SavedReport[]; total: number; page: number; limit: number }>('report', { path: '/api/v1/reports', params }),
    get: (id: string, page = 1) => this.request<ReportDetail>('report', { path: `/api/v1/reports/${id}`, params: { page } }),
    print: (id: string) => this.request<ReportDetail>('report', { path: `/api/v1/reports/${id}/print` }),
    download: (id: string, format: 'csv' | 'excel') => this.request<Blob>('report', { path: `/api/v1/reports/${id}/download`, params: { format }, responseType: 'blob' }),
    archive: (id: string, data: { request_id: string; notes: string }) => this.request<SavedReport>('report', { method: 'POST', path: `/api/v1/reports/${id}/archive`, data }),
    students: (search: string, page: number) => this.request<{ items: ReportStudentOption[]; total: number }>('report', { path: '/api/v1/reports/students', params: { search, page } }),
    exams: (search: string, page: number) => this.request<{ items: ReportExamOption[]; total: number }>('report', { path: '/api/v1/reports/exams', params: { search, page } }),
  };
}

export const apiClient = new ApiClient();
