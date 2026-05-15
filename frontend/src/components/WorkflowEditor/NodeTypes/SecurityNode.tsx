import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { ShieldCheck, ShieldAlert, UserCheck, Loader2, CheckCircle2, XCircle } from 'lucide-react';
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
  pii_scanner: <ShieldAlert size={14} className="text-warning" />,
  injection_guard: <ShieldCheck size={14} className="text-warning" />,
  human_gate: <UserCheck size={14} className="text-warning" />,
};

const statusStyles: Record<string, string> = {
  running: 'border-info shadow-info/20 shadow-lg',
  success: 'border-success',
  failed: 'border-error',
  waiting: 'border-warning animate-pulse-ring',
};

function SecurityNode({ data, selected }: NodeProps<NodeData>) {
  const isDisabled = data.disabled;
  const status = data.executionStatus;
  const hasDualOutput = data.type === 'injection_guard' || data.type === 'pii_scanner';

  return (
    <div
      className={clsx(
        'min-w-[180px] bg-surface border-2 rounded-xl p-3 transition-all',
        isDisabled && 'opacity-50',
        status && statusStyles[status],
        !status && selected ? 'border-warning shadow-lg shadow-warning/20' : !status && 'border-border',
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="input"
        className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-warning transition-colors"
      />

      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-warning/10 flex items-center justify-center shrink-0">
          {typeIcons[data.type] ?? <ShieldCheck size={14} className="text-warning" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-text-primary truncate">{data.name}</p>
          {status === 'running' && (
            <p className="text-[10px] text-info flex items-center gap-1">
              <Loader2 size={10} className="animate-spin" /> Scanning…
            </p>
          )}
          {status === 'success' && (
            <p className="text-[10px] text-success flex items-center gap-1">
              <CheckCircle2 size={10} /> Passed
            </p>
          )}
          {status === 'failed' && (
            <p className="text-[10px] text-error flex items-center gap-1">
              <XCircle size={10} /> Blocked
            </p>
          )}
        </div>
      </div>

      <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning/10 text-warning font-medium">
        Security
      </span>

      {/* Dual output handles for scanner/guard nodes */}
      {hasDualOutput ? (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="safe"
            style={{ top: '35%' }}
            className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-success transition-colors"
          />
          <Handle
            type="source"
            position={Position.Right}
            id="blocked"
            style={{ top: '65%' }}
            className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-error transition-colors"
          />
          <div className="absolute right-[-68px] top-[28%] text-[9px] text-success">safe</div>
          <div className="absolute right-[-72px] top-[57%] text-[9px] text-error">blocked</div>
        </>
      ) : (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="approved"
            style={{ top: '35%' }}
            className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-success transition-colors"
          />
          <Handle
            type="source"
            position={Position.Right}
            id="rejected"
            style={{ top: '65%' }}
            className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-error transition-colors"
          />
          <div className="absolute right-[-76px] top-[28%] text-[9px] text-success">approved</div>
          <div className="absolute right-[-72px] top-[57%] text-[9px] text-error">rejected</div>
        </>
      )}
    </div>
  );
}

export default memo(SecurityNode);
