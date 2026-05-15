import type { Node } from 'reactflow';
import { X, Settings2, ToggleLeft, ToggleRight } from 'lucide-react';
import { clsx } from 'clsx';
import ClaudeConfig from './ClaudeConfig';
import ConditionConfig from './ConditionConfig';
import SecurityNodeConfig from './SecurityNodeConfig';
import GenericConfig from './GenericConfig';
import type { NodeType } from '../../../types';

interface NodeConfigPanelProps {
  node: Node | null;
  onClose: () => void;
  onConfigChange: (nodeId: string, config: Record<string, unknown>) => void;
  onNameChange: (nodeId: string, name: string) => void;
  onToggleDisabled: (nodeId: string) => void;
}

const HTTP_FIELDS = [
  { key: 'url', label: 'URL', type: 'text' as const, placeholder: 'https://api.example.com/{{ data.id }}' },
  { key: 'method', label: 'Method', type: 'select' as const, options: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], defaultValue: 'GET' },
  { key: 'body', label: 'Body (JSON)', type: 'textarea' as const, placeholder: '{"key": "{{ data.value }}"}' },
  { key: 'timeout_seconds', label: 'Timeout (s)', type: 'number' as const, defaultValue: 30 },
];

const EMAIL_FIELDS = [
  { key: 'to', label: 'To', type: 'text' as const, placeholder: '{{ data.email }}' },
  { key: 'subject', label: 'Subject', type: 'text' as const, placeholder: 'Hello from AegisFlow' },
  { key: 'body', label: 'Body (HTML)', type: 'textarea' as const },
  { key: 'credential', label: 'SMTP Credential name', type: 'text' as const },
];

const SCHEDULE_FIELDS = [
  { key: 'cron', label: 'Cron expression', type: 'text' as const, placeholder: '0 9 * * MON-FRI' },
  { key: 'timezone', label: 'Timezone', type: 'text' as const, placeholder: 'UTC' },
];

const TRANSFORM_FIELDS = [
  { key: 'template', label: 'Jinja2 template (JSON)', type: 'textarea' as const, placeholder: '{"name": "{{ input.first }} {{ input.last }}"}' },
];

const OPENAI_FIELDS = [
  { key: 'model', label: 'Model', type: 'select' as const, options: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'], defaultValue: 'gpt-4o' },
  { key: 'system_prompt', label: 'System Prompt', type: 'textarea' as const },
  { key: 'user_message', label: 'User Message (Jinja2)', type: 'textarea' as const, placeholder: '{{ data.query }}' },
  { key: 'max_tokens', label: 'Max Tokens', type: 'number' as const, defaultValue: 2048 },
  { key: 'credential', label: 'Credential name', type: 'text' as const },
];

function getConfigComponent(type: NodeType, config: Record<string, unknown>, onChange: (k: string, v: unknown) => void) {
  switch (type) {
    case 'claude':
      return <ClaudeConfig config={config} onChange={onChange} />;
    case 'openai':
      return <GenericConfig fields={OPENAI_FIELDS} config={config} onChange={onChange} />;
    case 'condition':
      return <ConditionConfig config={config} onChange={onChange} />;
    case 'pii_scanner':
    case 'injection_guard':
    case 'human_gate':
      return <SecurityNodeConfig nodeType={type} config={config} onChange={onChange} />;
    case 'http':
      return <GenericConfig fields={HTTP_FIELDS} config={config} onChange={onChange} />;
    case 'email':
      return <GenericConfig fields={EMAIL_FIELDS} config={config} onChange={onChange} />;
    case 'schedule':
      return <GenericConfig fields={SCHEDULE_FIELDS} config={config} onChange={onChange} />;
    case 'transform':
      return <GenericConfig fields={TRANSFORM_FIELDS} config={config} onChange={onChange} />;
    default:
      return <p className="text-xs text-text-muted">No configurable options for this node type.</p>;
  }
}

export default function NodeConfigPanel({
  node,
  onClose,
  onConfigChange,
  onNameChange,
  onToggleDisabled,
}: NodeConfigPanelProps) {
  if (!node) return null;

  const type = node.data.type as NodeType;
  const config = (node.data.config ?? {}) as Record<string, unknown>;

  function handleConfigChange(key: string, value: unknown) {
    onConfigChange(node.id, { ...config, [key]: value });
  }

  return (
    <aside className="w-72 h-full bg-surface border-l border-border flex flex-col animate-slide-in-right">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0">
        <Settings2 size={14} className="text-text-muted shrink-0" />
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider flex-1">
          Node Config
        </span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-surface-2 text-text-muted hover:text-text-primary transition-colors"
        >
          <X size={14} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {/* Name */}
        <div>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">Node Name</label>
          <input
            type="text"
            value={node.data.name ?? ''}
            onChange={(e) => onNameChange(node.id, e.target.value)}
            className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
          />
        </div>

        {/* Disable toggle */}
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-secondary">Disabled</span>
          <button
            onClick={() => onToggleDisabled(node.id)}
            className={clsx(
              'flex items-center gap-1.5 text-xs transition-colors',
              node.data.disabled ? 'text-warning' : 'text-text-muted',
            )}
          >
            {node.data.disabled
              ? <ToggleRight size={18} className="text-warning" />
              : <ToggleLeft size={18} />
            }
          </button>
        </div>

        <div className="border-t border-border" />

        {/* Type-specific config */}
        {getConfigComponent(type, config, handleConfigChange)}
      </div>
    </aside>
  );
}
