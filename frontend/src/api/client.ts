import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';
import type {
  Workflow,
  Execution,
  Credential,
  DashboardStats,
  AuthTokens,
  User,
  PaginatedResponse,
  ApiResponse,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

// We keep a reference to the store's auth state without a circular import
// by using a callback pattern.
let getAccessToken: (() => string | null) | null = null;
let getRefreshToken: (() => string | null) | null = null;
let onTokensRefreshed: ((tokens: AuthTokens) => void) | null = null;
let onUnauthorized: (() => void) | null = null;

export function configureApiAuth(opts: {
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  onTokensRefreshed: (tokens: AuthTokens) => void;
  onUnauthorized: () => void;
}) {
  getAccessToken = opts.getAccessToken;
  getRefreshToken = opts.getRefreshToken;
  onTokensRefreshed = opts.onTokensRefreshed;
  onUnauthorized = opts.onUnauthorized;
}

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
});

// Request interceptor — attach bearer token
client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAccessToken?.();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Track in-flight refresh to avoid concurrent refresh calls
let refreshPromise: Promise<AuthTokens> | null = null;

// Response interceptor — handle 401 with token refresh
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const refreshToken = getRefreshToken?.();
      if (!refreshToken) {
        onUnauthorized?.();
        return Promise.reject(new Error('No refresh token available'));
      }

      try {
        if (!refreshPromise) {
          refreshPromise = axios
            .post<AuthTokens>(`${BASE_URL}/auth/refresh`, { refreshToken })
            .then((r) => r.data)
            .finally(() => {
              refreshPromise = null;
            });
        }

        const tokens = await refreshPromise;
        onTokensRefreshed?.(tokens);

        if (originalRequest.headers) {
          (originalRequest.headers as Record<string, string>).Authorization =
            `Bearer ${tokens.accessToken}`;
        }
        return client(originalRequest);
      } catch {
        onUnauthorized?.();
        return Promise.reject(new Error('Session expired — please log in again'));
      }
    }

    // Extract error detail from API error response
    const detail =
      (error.response?.data as { detail?: string } | undefined)?.detail ??
      error.message ??
      'An unexpected error occurred';

    return Promise.reject(new Error(detail));
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    client
      .post<{ tokens: AuthTokens; user: User }>('/auth/login', { email, password })
      .then((r) => r.data),

  refresh: (refreshToken: string) =>
    client.post<AuthTokens>('/auth/refresh', { refreshToken }).then((r) => r.data),

  me: () => client.get<ApiResponse<User>>('/auth/me').then((r) => r.data.data),
};

// ── Workflows ─────────────────────────────────────────────────────────────────

export const workflowsApi = {
  list: () =>
    client.get<ApiResponse<Workflow[]>>('/workflows').then((r) => r.data.data),

  get: (id: string) =>
    client.get<ApiResponse<Workflow>>(`/workflows/${id}`).then((r) => r.data.data),

  create: (data: Partial<Workflow>) =>
    client.post<ApiResponse<Workflow>>('/workflows', data).then((r) => r.data.data),

  update: (id: string, data: Partial<Workflow>) =>
    client.put<ApiResponse<Workflow>>(`/workflows/${id}`, data).then((r) => r.data.data),

  delete: (id: string) =>
    client.delete(`/workflows/${id}`).then((r) => r.data),

  activate: (id: string) =>
    client.post<ApiResponse<Workflow>>(`/workflows/${id}/activate`).then((r) => r.data.data),

  deactivate: (id: string) =>
    client.post<ApiResponse<Workflow>>(`/workflows/${id}/deactivate`).then((r) => r.data.data),

  execute: (id: string, payload?: Record<string, unknown>) =>
    client
      .post<ApiResponse<Execution>>(`/workflows/${id}/execute`, payload ?? {})
      .then((r) => r.data.data),
};

// ── Executions ────────────────────────────────────────────────────────────────

export const executionsApi = {
  list: (params?: { workflowId?: string; page?: number; pageSize?: number }) =>
    client
      .get<PaginatedResponse<Execution>>('/executions', { params })
      .then((r) => r.data),

  get: (id: string) =>
    client.get<ApiResponse<Execution>>(`/executions/${id}`).then((r) => r.data.data),

  cancel: (id: string) =>
    client.post(`/executions/${id}/cancel`).then((r) => r.data),

  approveGate: (executionId: string, nodeId: string, approved: boolean) =>
    client
      .post(`/executions/${executionId}/nodes/${nodeId}/gate`, { approved })
      .then((r) => r.data),
};

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const dashboardApi = {
  stats: () =>
    client.get<ApiResponse<DashboardStats>>('/dashboard/stats').then((r) => r.data.data),
};

// ── Credentials ───────────────────────────────────────────────────────────────

export const credentialsApi = {
  list: () =>
    client.get<ApiResponse<Credential[]>>('/credentials').then((r) => r.data.data),

  create: (data: { name: string; type: string; values: Record<string, string> }) =>
    client.post<ApiResponse<Credential>>('/credentials', data).then((r) => r.data.data),

  delete: (id: string) =>
    client.delete(`/credentials/${id}`).then((r) => r.data),

  test: (id: string) =>
    client.post<ApiResponse<{ ok: boolean; message: string }>>(`/credentials/${id}/test`).then((r) => r.data.data),
};

export default client;
