import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Node, Edge } from 'reactflow';
import {
  authApi,
  workflowsApi,
  executionsApi,
  dashboardApi,
  credentialsApi,
  configureApiAuth,
} from '../api/client';
import type {
  User,
  AuthTokens,
  Workflow,
  Execution,
  Credential,
  DashboardStats,
} from '../types';

// ── Toast ──────────────────────────────────────────────────────────────────────

export interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

// ── Store Shape ───────────────────────────────────────────────────────────────

interface AppStore {
  // Auth
  user: User | null;
  tokens: AuthTokens | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setTokens: (tokens: AuthTokens) => void;

  // Workflows
  workflows: Workflow[];
  selectedWorkflow: Workflow | null;
  fetchWorkflows: () => Promise<void>;
  saveWorkflow: (workflow: Partial<Workflow>) => Promise<void>;
  selectWorkflow: (workflow: Workflow | null) => void;
  deleteWorkflow: (id: string) => Promise<void>;
  toggleWorkflowActive: (id: string, active: boolean) => Promise<void>;
  executeWorkflow: (id: string) => Promise<Execution>;

  // Editor state (React Flow)
  editorNodes: Node[];
  editorEdges: Edge[];
  selectedNodeId: string | null;
  isDirty: boolean;
  setEditorNodes: (nodes: Node[]) => void;
  setEditorEdges: (edges: Edge[]) => void;
  selectNode: (id: string | null) => void;
  markDirty: () => void;
  markClean: () => void;

  // Executions
  executions: Execution[];
  executionsPagination: { total: number; page: number; hasNext: boolean };
  activeExecution: Execution | null;
  fetchExecutions: (workflowId?: string, page?: number) => Promise<void>;
  fetchExecution: (id: string) => Promise<void>;
  updateNodeExecution: (executionId: string, nodeId: string, data: unknown) => void;
  setActiveExecution: (execution: Execution | null) => void;

  // Dashboard
  dashboardStats: DashboardStats | null;
  fetchDashboardStats: () => Promise<void>;

  // Credentials
  credentials: Credential[];
  fetchCredentials: () => Promise<void>;
  deleteCredential: (id: string) => Promise<void>;

  // UI
  sidebarExpanded: boolean;
  toggleSidebar: () => void;
  toasts: Toast[];
  toast: (message: string, type?: Toast['type']) => void;
  dismissToast: (id: string) => void;

  // Loading states
  loading: {
    workflows: boolean;
    executions: boolean;
    dashboard: boolean;
    credentials: boolean;
    saving: boolean;
    executing: boolean;
  };
}

// ── Store ─────────────────────────────────────────────────────────────────────

export const useStore = create<AppStore>()(
  persist(
    (set, get) => {
      // Wire up the api client after store is created
      const wireApiAuth = () => {
        configureApiAuth({
          getAccessToken: () => get().tokens?.accessToken ?? null,
          getRefreshToken: () => get().tokens?.refreshToken ?? null,
          onTokensRefreshed: (tokens) => set({ tokens }),
          onUnauthorized: () => {
            set({ user: null, tokens: null });
          },
        });
      };
      // Call immediately
      wireApiAuth();

      return {
        // ── Auth ────────────────────────────────────────────────────────────
        user: null,
        tokens: null,

        login: async (email, password) => {
          const result = await authApi.login(email, password);
          set({ user: result.user, tokens: result.tokens });
          wireApiAuth();
        },

        logout: () => {
          set({ user: null, tokens: null, workflows: [], executions: [], selectedWorkflow: null });
        },

        setTokens: (tokens) => set({ tokens }),

        // ── Workflows ───────────────────────────────────────────────────────
        workflows: [],
        selectedWorkflow: null,

        fetchWorkflows: async () => {
          set((s) => ({ loading: { ...s.loading, workflows: true } }));
          try {
            const data = await workflowsApi.list();
            set({ workflows: data });
          } catch (err) {
            get().toast((err as Error).message, 'error');
          } finally {
            set((s) => ({ loading: { ...s.loading, workflows: false } }));
          }
        },

        saveWorkflow: async (workflow) => {
          set((s) => ({ loading: { ...s.loading, saving: true } }));
          try {
            let saved: Workflow;
            if (workflow.id) {
              saved = await workflowsApi.update(workflow.id, workflow);
            } else {
              saved = await workflowsApi.create(workflow);
            }
            set((s) => {
              const existing = s.workflows.findIndex((w) => w.id === saved.id);
              const next = existing >= 0
                ? s.workflows.map((w) => (w.id === saved.id ? saved : w))
                : [...s.workflows, saved];
              return { workflows: next, selectedWorkflow: saved, isDirty: false };
            });
            get().toast('Workflow saved', 'success');
          } catch (err) {
            get().toast((err as Error).message, 'error');
            throw err;
          } finally {
            set((s) => ({ loading: { ...s.loading, saving: false } }));
          }
        },

        selectWorkflow: (workflow) => set({ selectedWorkflow: workflow }),

        deleteWorkflow: async (id) => {
          await workflowsApi.delete(id);
          set((s) => ({
            workflows: s.workflows.filter((w) => w.id !== id),
            selectedWorkflow: s.selectedWorkflow?.id === id ? null : s.selectedWorkflow,
          }));
          get().toast('Workflow deleted', 'success');
        },

        toggleWorkflowActive: async (id, active) => {
          const updated = active
            ? await workflowsApi.activate(id)
            : await workflowsApi.deactivate(id);
          set((s) => ({
            workflows: s.workflows.map((w) => (w.id === id ? updated : w)),
            selectedWorkflow: s.selectedWorkflow?.id === id ? updated : s.selectedWorkflow,
          }));
        },

        executeWorkflow: async (id) => {
          set((s) => ({ loading: { ...s.loading, executing: true } }));
          try {
            const execution = await workflowsApi.execute(id);
            set((s) => ({ executions: [execution, ...s.executions] }));
            return execution;
          } finally {
            set((s) => ({ loading: { ...s.loading, executing: false } }));
          }
        },

        // ── Editor state ───────────────────────────────────────────────────
        editorNodes: [],
        editorEdges: [],
        selectedNodeId: null,
        isDirty: false,

        setEditorNodes: (nodes) => set({ editorNodes: nodes }),
        setEditorEdges: (edges) => set({ editorEdges: edges }),
        selectNode: (id) => set({ selectedNodeId: id }),
        markDirty: () => set({ isDirty: true }),
        markClean: () => set({ isDirty: false }),

        // ── Executions ─────────────────────────────────────────────────────
        executions: [],
        executionsPagination: { total: 0, page: 1, hasNext: false },
        activeExecution: null,

        fetchExecutions: async (workflowId, page = 1) => {
          set((s) => ({ loading: { ...s.loading, executions: true } }));
          try {
            const result = await executionsApi.list({ workflowId, page, pageSize: 50 });
            set({
              executions: result.items,
              executionsPagination: { total: result.total, page: result.page, hasNext: result.hasNext },
            });
          } catch (err) {
            get().toast((err as Error).message, 'error');
          } finally {
            set((s) => ({ loading: { ...s.loading, executions: false } }));
          }
        },

        fetchExecution: async (id) => {
          const execution = await executionsApi.get(id);
          set({ activeExecution: execution });
        },

        updateNodeExecution: (executionId, nodeId, data) => {
          set((s) => {
            if (s.activeExecution?.id !== executionId) return {};
            return {
              activeExecution: {
                ...s.activeExecution,
                nodes: {
                  ...s.activeExecution.nodes,
                  [nodeId]: { ...s.activeExecution.nodes[nodeId], ...data },
                },
              },
            };
          });
        },

        setActiveExecution: (execution) => set({ activeExecution: execution }),

        // ── Dashboard ──────────────────────────────────────────────────────
        dashboardStats: null,

        fetchDashboardStats: async () => {
          set((s) => ({ loading: { ...s.loading, dashboard: true } }));
          try {
            const stats = await dashboardApi.stats();
            set({ dashboardStats: stats });
          } catch {
            // Silently fail for stats
          } finally {
            set((s) => ({ loading: { ...s.loading, dashboard: false } }));
          }
        },

        // ── Credentials ────────────────────────────────────────────────────
        credentials: [],

        fetchCredentials: async () => {
          set((s) => ({ loading: { ...s.loading, credentials: true } }));
          try {
            const data = await credentialsApi.list();
            set({ credentials: data });
          } catch (err) {
            get().toast((err as Error).message, 'error');
          } finally {
            set((s) => ({ loading: { ...s.loading, credentials: false } }));
          }
        },

        deleteCredential: async (id) => {
          await credentialsApi.delete(id);
          set((s) => ({ credentials: s.credentials.filter((c) => c.id !== id) }));
          get().toast('Credential deleted', 'success');
        },

        // ── UI ─────────────────────────────────────────────────────────────
        sidebarExpanded: true,

        toggleSidebar: () => set((s) => ({ sidebarExpanded: !s.sidebarExpanded })),

        toasts: [],

        toast: (message, type = 'info') => {
          const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
          set((s) => ({ toasts: [...s.toasts, { id, message, type }] }));
          setTimeout(() => {
            set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
          }, 5000);
        },

        dismissToast: (id) => {
          set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
        },

        // ── Loading ────────────────────────────────────────────────────────
        loading: {
          workflows: false,
          executions: false,
          dashboard: false,
          credentials: false,
          saving: false,
          executing: false,
        },
      };
    },
    {
      name: 'aegisflow-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        user: state.user,
        tokens: state.tokens,
        sidebarExpanded: state.sidebarExpanded,
      }),
    }
  )
);
