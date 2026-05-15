import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Brain, Loader2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import type { NodeType, NodeStatus } from '../../../types';

interface NodeData {
  type: NodeType;
  name: string;
  config: Record<string, unknown>;
  disabled?: boolean;
  executionStatus?: NodeStatus;
}

const statusStyles: Record<string, string> = {
  running: 'border-info shadow-info/20 shadow-lg',
  success: 'border-success',
  failed: 'border-error',
  waiting: 'border-warning',
};

const statusIcons: Record<string, React.ReactNode> = {
  running: <Loader2 size={12} className="text-info animate-spin" />,
  success: <CheckCircle2 size={12} className="text-success" />,
  failed: <XCircle size={12} className="text-error" />,
  waiting: <AlertTriangle size={12} className="text-warning" />,
};

function AINode({ data, selected }: NodeProps<NodeData>) {
  const isDisabled = data.disabled;
  const status = data.executionStatus;
  const model = (data.config?.model as string) ?? 'claude-sonnet-4-6';
  const shortModel = model.split('-').slice(1, 3).join(' ');

  return (
    <div
      className={clsx(
        'min-w-[180px] bg-surface border-2 rounded-xl p-3 transition-all',
        isDisabled && 'opacity-50',
        status && statusStyles[status],
        !status && selected ? 'border-primary shadow-lg shadow-primary/20' : !status && 'border-border',
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="input"
        className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-primary transition-colors"
      />

      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Brain size={14} className="text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-text-primary truncate">{data.name}</p>
          <p className="text-[10px] text-text-muted capitalize">{shortModel}</p>
        </div>
        {status && statusIcons[status] && (
          <span className="shrink-0">{statusIcons[status]}</span>
        )}
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-medium capitalize">
          {data.type}
        </span>
        {isDisabled && (
          <span className="text-[10px] text-text-muted">disabled</span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id="output"
        className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-primary transition-colors"
      />
    </div>
  );
}

export default memo(AINode);
