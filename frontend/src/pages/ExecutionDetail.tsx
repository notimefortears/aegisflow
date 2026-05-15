import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, CheckCircle2, XCircle, Loader2, Clock, Ban } from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';
import { clsx } from 'clsx';
import { useStore } from '../store';
import ExecutionTimeline from '../components/ExecutionLog/ExecutionTimeline';
import SecurityReport from '../components/ExecutionLog/SecurityReport';
import type { ExecutionStatus } from '../types';

const statusConfig: Record<ExecutionStatus, { icon: React.ReactNode; color: string; label: string }> = {
  success: { icon: <CheckCircle2 size={16} />, color: 'text-success', label: 'Success' },
  failed: { icon: <XCircle size={16} />, color: 'text-error', label: 'Failed' },
  running: { icon: <Loader2 size={16} className="animate-spin" />, color: 'text-info', label: 'Running' },
  pending: { icon: <Clock size={16} />, color: 'text-warning', label: 'Pending' },
  cancelled: { icon: <Ban size={16} />, color: 'text-text-muted', label: 'Cancelled' },
};

export default function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { activeExecution, fetchExecution } = useStore();

  useEffect(() => {
    if (id) fetchExecution(id);
  }, [id]);

  if (!activeExecution) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-text-muted" />
      </div>
    );
  }

  const exec = activeExecution;
  const status = statusConfig[exec.status];
  const nodeCount = Object.keys(exec.nodes).length;
  const successCount = Object.values(exec.nodes).filter((n) => n.status === 'success').length;

  return (
    <div className="p-6 max-w-4xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="flex items-start gap-4 mb-6">
        <button
          onClick={() => navigate('/executions')}
          className="mt-1 p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors shrink-0"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-xl font-bold text-text-primary truncate">{exec.workflowName}</h1>
            <span className={clsx('flex items-center gap-1.5 text-sm font-medium', status.color)}>
              {status.icon}
              {status.label}
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs text-text-muted flex-wrap">
            <span className="font-mono">{exec.id.slice(0, 16)}…</span>
            <span>Trigger: {exec.trigger}</span>
            {exec.startedAt && (
              <span>Started {format(new Date(exec.startedAt), 'MMM d, HH:mm:ss')}</span>
            )}
            {exec.durationMs != null && (
              <span>Duration: {exec.durationMs < 1000 ? `${exec.durationMs}ms` : `${(exec.durationMs / 1000).toFixed(2)}s`}</span>
            )}
            <span>{successCount}/{nodeCount} nodes succeeded</span>
          </div>
        </div>
      </div>

      {exec.error && (
        <div className="mb-6 p-4 bg-error/5 border border-error/20 rounded-xl">
          <p className="text-sm font-medium text-error mb-1">Execution Error</p>
          <p className="text-xs text-text-secondary font-mono">{exec.error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="xl:col-span-2">
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Timeline</h2>
          <ExecutionTimeline execution={exec} />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider mb-3">Security</h2>
          <SecurityReport execution={exec} />
        </div>
      </div>
    </div>
  );
}
