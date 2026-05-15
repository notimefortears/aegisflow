import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Globe, Mail, Database, Loader2, CheckCircle2, XCircle } from 'lucide-react';
import { clsx } from 'clsx';
import type { NodeType, NodeStatus } from '../../../types';

interface NodeData {
  type: NodeType;
  name: string;
  config: Record<string, unknown>;
  disabled?: boolean;
  executionStatus?: NodeStatus;
}

const typeIcons: Record<string, React.ReactNode> = {
  http: <Globe size={14} className="text-info" />,
  email: <Mail size={14} className="text-info" />,
  database: <Database size={14} className="text-info" />,
};

const statusStyles: Record<string, string> = {
  running: 'border-info shadow-info/20 shadow-lg',
  success: 'border-success',
  failed: 'border-error',
};

const statusIcons: Record<string, React.ReactNode> = {
  running: <Loader2 size={12} className="text-info animate-spin" />,
  success: <CheckCircle2 size={12} className="text-success" />,
  failed: <XCircle size={12} className="text-error" />,
};

function IntegrationNode({ data, selected }: NodeProps<NodeData>) {
  const status = data.executionStatus;

  return (
    <div
      className={clsx(
        'min-w-[170px] bg-surface border-2 rounded-xl p-3 transition-all',
        data.disabled && 'opacity-50',
        status && statusStyles[status],
        !status && selected ? 'border-info shadow-lg shadow-info/20' : !status && 'border-border',
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="input"
        className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-info transition-colors"
      />

      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-info/10 flex items-center justify-center shrink-0">
          {typeIcons[data.type] ?? <Globe size={14} className="text-info" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-text-primary truncate">{data.name}</p>
          {data.config?.url && (
            <p className="text-[10px] text-text-muted truncate">
              {(data.config.url as string).replace(/^https?:\/\//, '').slice(0, 24)}…
            </p>
          )}
        </div>
        {status && statusIcons[status] && <span className="shrink-0">{statusIcons[status]}</span>}
      </div>

      <span className="text-[10px] px-1.5 py-0.5 rounded bg-info/10 text-info font-medium capitalize">
        {data.type}
      </span>

      <Handle
        type="source"
        position={Position.Right}
        id="output"
        className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-info transition-colors"
      />
    </div>
  );
}

export default memo(IntegrationNode);
