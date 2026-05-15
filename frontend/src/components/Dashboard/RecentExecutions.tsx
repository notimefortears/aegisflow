import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { clsx } from 'clsx';
import { CheckCircle2, XCircle, Clock, Loader2, Ban } from 'lucide-react';
import type { Execution, ExecutionStatus } from '../../types';

interface RecentExecutionsProps {
  executions: Execution[];
  loading?: boolean;
}

const statusConfig: Record<ExecutionStatus, { icon: React.ReactNode; color: string; label: string }> = {
  success: {
    icon: <CheckCircle2 size={14} />,
    color: 'text-success',
    label: 'Success',
  },
  failed: {
    icon: <XCircle size={14} />,
    color: 'text-error',
    label: 'Failed',
  },
  running: {
    icon: <Loader2 size={14} className="animate-spin" />,
    color: 'text-info',
    label: 'Running',
  },
  pending: {
    icon: <Clock size={14} />,
    color: 'text-warning',
    label: 'Pending',
  },
  cancelled: {
    icon: <Ban size={14} />,
    color: 'text-text-muted',
    label: 'Cancelled',
  },
};

export default function RecentExecutions({ executions, loading }: RecentExecutionsProps) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="space-y-2">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 bg-surface-2 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  if (executions.length === 0) {
    return (
      <div className="text-center py-10 text-text-muted text-sm">
        No executions yet. Run a workflow to see results here.
      </div>
    );
  }

  return (
    <div className="divide-y divide-border">
      {executions.map((execution) => {
        const status = statusConfig[execution.status];
        return (
          <div
            key={execution.id}
            onClick={() => navigate(`/executions/${execution.id}`)}
            className="flex items-center justify-between py-3 px-1 hover:bg-surface-2/50 cursor-pointer rounded-md transition-colors group"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className={clsx('shrink-0', status.color)}>{status.icon}</span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {execution.workflowName}
                </p>
                <p className="text-xs text-text-muted">
                  {execution.trigger} · {formatDistanceToNow(new Date(execution.startedAt), { addSuffix: true })}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              {execution.durationMs != null && (
                <span className="text-xs text-text-muted tabular-nums">
                  {execution.durationMs < 1000
                    ? `${execution.durationMs}ms`
                    : `${(execution.durationMs / 1000).toFixed(1)}s`}
                </span>
              )}
              <span className={clsx('text-xs font-medium', status.color)}>{status.label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
