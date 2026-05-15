import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { GitBranch, Shuffle, Merge } from 'lucide-react';
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
  condition: <GitBranch size={14} className="text-text-secondary" />,
  transform: <Shuffle size={14} className="text-text-secondary" />,
  merge: <Merge size={14} className="text-text-secondary" />,
};

function LogicNode({ data, selected }: NodeProps<NodeData>) {
  const isCondition = data.type === 'condition';

  return (
    <div
      className={clsx(
        'min-w-[160px] bg-surface border-2 rounded-xl p-3 transition-all',
        data.disabled && 'opacity-50',
        selected ? 'border-border-2 shadow-lg' : 'border-border',
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        id="input"
        className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-border-2 transition-colors"
      />

      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-lg bg-surface-2 flex items-center justify-center shrink-0">
          {typeIcons[data.type]}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-text-primary truncate">{data.name}</p>
          {isCondition && data.config?.field && (
            <p className="text-[10px] text-text-muted truncate font-mono">
              {data.config.field as string}
            </p>
          )}
        </div>
      </div>

      <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface-2 text-text-secondary font-medium capitalize">
        {data.type}
      </span>

      {isCondition ? (
        <>
          <Handle
            type="source"
            position={Position.Right}
            id="true"
            style={{ top: '30%' }}
            className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-success transition-colors"
          />
          <Handle
            type="source"
            position={Position.Right}
            id="false"
            style={{ top: '70%' }}
            className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-error transition-colors"
          />
          <div className="absolute right-[-28px] top-[22%] text-[9px] text-success">true</div>
          <div className="absolute right-[-32px] top-[62%] text-[9px] text-error">false</div>
        </>
      ) : (
        <Handle
          type="source"
          position={Position.Right}
          id="output"
          className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-border-2 transition-colors"
        />
      )}
    </div>
  );
}

export default memo(LogicNode);
