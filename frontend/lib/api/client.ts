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
      message: typeof detail === 'string' ? detail : 'Request failed',
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

      const payload = response.status === 204 ? null : await response.json();
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
    const key = `${localStorage.getItem('tenant_id') ?? ''}:${localStorage.getItem('access_token') ?? ''}:${url}`;
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
      list: () => this.request('fee', { path: '/api/v1/fees/structures' }),
      create: (data: unknown) => this.request('fee', { method: 'POST', path: '/api/v1/fees/structures', data }),
    },
    collect: (data: unknown) => this.request('fee', { method: 'POST', path: '/api/v1/fees/collect', data }),
    ledger: (studentId: string) => this.request('fee', { path: `/api/v1/fees/students/${studentId}/ledger` }),
  };

  library = {
    books: {
      list: (params?: QueryParams) => this.request('library', { path: '/api/v1/library/books', params }),
      create: (data: unknown) => this.request('library', { method: 'POST', path: '/api/v1/library/books', data }),
    },
    issue: (data: unknown) => this.request('library', { method: 'POST', path: '/api/v1/library/issue', data }),
    return: (issueId: string) => this.request('library', { method: 'POST', path: `/api/v1/library/return/${issueId}` }),
  };

  transport = {
    vehicles: {
      list: () => this.request('transport', { path: '/api/v1/transport/vehicles' }),
      create: (data: unknown) => this.request('transport', { method: 'POST', path: '/api/v1/transport/vehicles', data }),
    },
    routes: {
      list: () => this.request('transport', { path: '/api/v1/transport/routes' }),
      create: (data: unknown) => this.request('transport', { method: 'POST', path: '/api/v1/transport/routes', data }),
    },
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
    generate: (reportType: string, params: Record<string, unknown>) =>
      this.request('report', { method: 'POST', path: '/api/v1/reports/generate', data: { report_type: reportType, ...params } }),
    list: () => this.request('report', { path: '/api/v1/reports' }),
  };
}

export const apiClient = new ApiClient();
