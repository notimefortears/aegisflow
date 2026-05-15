import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import { Webhook, Clock, Play } from 'lucide-react';
import { clsx } from 'clsx';
import type { NodeType } from '../../../types';

interface NodeData {
  type: NodeType;
  name: string;
  config: Record<string, unknown>;
  disabled?: boolean;
}

const triggerIcons: Record<string, React.ReactNode> = {
  webhook: <Webhook size={14} className="text-success" />,
  schedule: <Clock size={14} className="text-success" />,
  manual: <Play size={14} className="text-success" />,
};

function TriggerNode({ data, selected }: NodeProps<NodeData>) {
  return (
    <div
      className={clsx(
        'min-w-[160px] bg-surface border-2 rounded-2xl p-3 transition-all',
        data.disabled && 'opacity-50',
        selected ? 'border-success shadow-lg shadow-success/20' : 'border-border',
      )}
    >
      <div className="flex items-center gap-2">
        <div className="w-7 h-7 rounded-lg bg-success/10 flex items-center justify-center shrink-0">
          {triggerIcons[data.type] ?? <Play size={14} className="text-success" />}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-text-primary truncate">{data.name}</p>
          <p className="text-[10px] text-text-muted capitalize">{data.type}</p>
        </div>
      </div>

      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-success/10 text-success font-medium">
          Trigger
        </span>
        {data.config?.cron && (
          <span className="text-[10px] text-text-muted font-mono truncate max-w-[80px]">
            {data.config.cron as string}
          </span>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        id="output"
        className="!w-3 !h-3 !bg-border-2 !border-2 !border-background hover:!bg-success transition-colors"
      />
    </div>
  );
}

export default memo(TriggerNode);
