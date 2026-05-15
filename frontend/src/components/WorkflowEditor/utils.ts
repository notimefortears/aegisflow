import type { Node, Edge } from 'reactflow';
import type { WorkflowDefinition, WorkflowNode, WorkflowEdge, NodeType } from '../../types';

// Map NodeType → React Flow node type name (must match nodeTypes object in index.tsx)
export function toRFNodeType(nodeType: NodeType): string {
  if (['claude', 'openai'].includes(nodeType)) return 'aiNode';
  if (['pii_scanner', 'injection_guard', 'human_gate'].includes(nodeType)) return 'securityNode';
  if (['webhook', 'schedule', 'manual'].includes(nodeType)) return 'triggerNode';
  if (['condition', 'transform', 'merge'].includes(nodeType)) return 'logicNode';
  return 'integrationNode';
}

export function definitionToFlow(def: WorkflowDefinition): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = def.nodes.map((n) => ({
    id: n.id,
    type: toRFNodeType(n.type),
    position: n.position,
    data: { ...n },  // includes type, name, config, disabled
  }));

  const edges: Edge[] = def.edges.map((e) => ({
    id: e.id,
    source: e.source,
    sourceHandle: e.sourceHandle,
    target: e.target,
    targetHandle: e.targetHandle,
    type: 'smoothstep',
    style: { stroke: '#3a3a3a', strokeWidth: 2 },
    animated: false,
  }));

  return { nodes, edges };
}

export function flowToDefinition(
  nodes: Node[],
  edges: Edge[],
  existing?: WorkflowDefinition,
): WorkflowDefinition {
  return {
    nodes: nodes.map<WorkflowNode>((n) => ({
      id: n.id,
      type: n.data.type as NodeType,
      name: n.data.name ?? 'Untitled',
      config: n.data.config ?? {},
      position: n.position,
      disabled: n.data.disabled ?? false,
    })),
    edges: edges.map<WorkflowEdge>((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle ?? 'output',
      target: e.target,
      targetHandle: e.targetHandle ?? 'input',
    })),
    variables: existing?.variables ?? {},
  };
}

// Node category metadata (used by palette and node colors)
export type NodeCategory = 'trigger' | 'ai' | 'security' | 'integration' | 'logic';

export interface NodeMeta {
  type: NodeType;
  label: string;
  category: NodeCategory;
  description: string;
}

export const NODE_CATALOG: NodeMeta[] = [
  // Triggers
  { type: 'webhook', label: 'Webhook', category: 'trigger', description: 'Trigger on HTTP request' },
  { type: 'schedule', label: 'Schedule', category: 'trigger', description: 'Run on a cron schedule' },
  { type: 'manual', label: 'Manual', category: 'trigger', description: 'Triggered manually or via API' },
  // AI
  { type: 'claude', label: 'Claude', category: 'ai', description: 'Anthropic Claude model call' },
  { type: 'openai', label: 'OpenAI', category: 'ai', description: 'OpenAI GPT model call' },
  // Security
  { type: 'pii_scanner', label: 'PII Scanner', category: 'security', description: 'Detect and redact PII' },
  { type: 'injection_guard', label: 'Injection Guard', category: 'security', description: 'Block prompt injection' },
  { type: 'human_gate', label: 'Human Gate', category: 'security', description: 'Pause for human approval' },
  // Integrations
  { type: 'http', label: 'HTTP Request', category: 'integration', description: 'Call any REST API' },
  { type: 'email', label: 'Email', category: 'integration', description: 'Send an email via SMTP' },
  { type: 'database', label: 'Database', category: 'integration', description: 'Query a SQL database' },
  // Logic
  { type: 'condition', label: 'Condition', category: 'logic', description: 'Branch based on a rule' },
  { type: 'transform', label: 'Transform', category: 'logic', description: 'Reshape data with templates' },
  { type: 'merge', label: 'Merge', category: 'logic', description: 'Combine multiple inputs' },
];

export const CATEGORY_COLORS: Record<NodeCategory, { ring: string; bg: string; text: string; badge: string }> = {
  trigger: {
    ring: 'border-success',
    bg: 'bg-success/10',
    text: 'text-success',
    badge: 'bg-success/20 text-success',
  },
  ai: {
    ring: 'border-primary',
    bg: 'bg-primary/10',
    text: 'text-primary',
    badge: 'bg-primary/20 text-primary-light',
  },
  security: {
    ring: 'border-warning',
    bg: 'bg-warning/10',
    text: 'text-warning',
    badge: 'bg-warning/20 text-warning',
  },
  integration: {
    ring: 'border-info',
    bg: 'bg-info/10',
    text: 'text-info',
    badge: 'bg-info/20 text-info',
  },
  logic: {
    ring: 'border-border-2',
    bg: 'bg-surface-2',
    text: 'text-text-secondary',
    badge: 'bg-surface-2 text-text-secondary',
  },
};
