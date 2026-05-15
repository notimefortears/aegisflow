// AegisFlow shared TypeScript types — all frontend code imports from here.

export type NodeType =
  | 'webhook' | 'schedule' | 'manual'           // triggers
  | 'claude' | 'openai'                          // AI
  | 'pii_scanner' | 'injection_guard' | 'human_gate'  // security
  | 'http' | 'email' | 'database'               // integrations
  | 'condition' | 'transform' | 'merge';         // logic

export type NodeStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped' | 'waiting';
export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled';
export type UserRole = 'admin' | 'editor' | 'viewer' | 'runner';

// ── Workflow Definition ───────────────────────────────────────────────────────

export interface WorkflowNode {
  id: string;
  type: NodeType;
  name: string;
  config: Record<string, unknown>;
  position: { x: number; y: number };
  disabled?: boolean;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  sourceHandle: string;   // "output" | "true" | "false"
  target: string;
  targetHandle: string;   // "input"
}

export interface WorkflowDefinition {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  variables?: Record<string, unknown>;
}

export interface Workflow {
  id: string;
  name: string;
  description?: string;
  definition: WorkflowDefinition;
  isActive: boolean;
  tags: string[];
  createdAt: string;
  updatedAt: string;
  lastExecutedAt?: string;
  createdBy: string;
}

// ── Execution ─────────────────────────────────────────────────────────────────

export interface NodeExecutionRecord {
  nodeId: string;
  nodeName: string;
  nodeType: NodeType;
  status: NodeStatus;
  inputData: Record<string, unknown>;
  outputData?: Record<string, unknown>;
  error?: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
  logs: string[];
  retryCount: number;
}

export interface Execution {
  id: string;
  workflowId: string;
  workflowName: string;
  status: ExecutionStatus;
  trigger: string;
  nodes: Record<string, NodeExecutionRecord>;
  startedAt: string;
  completedAt?: string;
  durationMs?: number;
  error?: string;
  triggeredBy: string;
}

// ── Security ──────────────────────────────────────────────────────────────────

export type PIICategory =
  | 'email' | 'phone' | 'ssn' | 'credit_card' | 'ip_address'
  | 'name' | 'address' | 'date_of_birth' | 'passport' | 'medical';

export type PolicyAction = 'allow' | 'block' | 'redact' | 'alert' | 'require_approval';

export interface PIIMatch {
  category: PIICategory;
  value: string;
  redacted: string;
  confidence: number;
}

export interface SecurityScanResult {
  pii: { hasPii: boolean; matches: PIIMatch[]; riskScore: number };
  injection: { isSafe: boolean; riskScore: number; patternsMatched: string[] };
  blocked: boolean;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  createdAt: string;
}

export interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
}

// ── Credentials ───────────────────────────────────────────────────────────────

export type CredentialType =
  | 'anthropic_api_key'
  | 'openai_api_key'
  | 'smtp'
  | 'http_bearer'
  | 'http_basic'
  | 'postgres'
  | 'webhook_hmac';

export interface Credential {
  id: string;
  name: string;
  type: CredentialType;
  createdAt: string;
  // values are never returned to frontend after creation
}

// ── WebSocket Messages ────────────────────────────────────────────────────────

export type WSEventType =
  | 'node_started'
  | 'node_completed'
  | 'node_failed'
  | 'execution_completed'
  | 'execution_failed'
  | 'human_gate_waiting'
  | 'log_line';

export interface WSMessage {
  type: WSEventType;
  executionId: string;
  nodeId?: string;
  data?: unknown;
  timestamp: string;
}

// ── API Response Shapes ───────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasNext: boolean;
}

export interface ApiError {
  detail: string;
  code?: string;
}

// ── Dashboard Metrics ─────────────────────────────────────────────────────────

export interface DashboardStats {
  totalWorkflows: number;
  activeWorkflows: number;
  totalExecutions: number;
  successRate: number;
  avgDurationMs: number;
  piiDetections: number;
  injectionBlocks: number;
  humanGatesPending: number;
}
