import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { CheckCircle2, XCircle, Loader2, Clock, Ban, RefreshCw } from 'lucide-react';
import { clsx } from 'clsx';
import { useStore } from '../store';
import type { ExecutionStatus } from '../types';

const statusConfig: Record<ExecutionStatus, { icon: React.ReactNode; color: string; bg: string; label: string }> = {
  success: { icon: <CheckCircle2 size={14} />, color: 'text-success', bg: 'bg-success/10', label: 'Success' },
  failed: { icon: <XCircle size={14} />, color: 'text-error', bg: 'bg-error/10', label: 'Failed' },
  running: { icon: <Loader2 size={14} className="animate-spin" />, color: 'text-info', bg: 'bg-info/10', label: 'Running' },
  pending: { icon: <Clock size={14} />, color: 'text-warning', bg: 'bg-warning/10', label: 'Pending' },
  cancelled: { icon: <Ban size={14} />, color: 'text-text-muted', bg: 'bg-surface-2', label: 'Cancelled' },
};

export default function Executions() {
  const navigate = useNavigate();
  const { executions, fetchExecutions, loading } = useStore();

  useEffect(() => {
    fetchExecutions();
  }, []);

  return (
    <div className="p-6 max-w-5xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Executions</h1>
          <p className="text-text-muted text-sm mt-0.5">History of all workflow runs</p>
        </div>
        <button
          onClick={() => fetchExecutions()}
          className="flex items-center gap-2 px-3 py-1.5 bg-surface-2 border border-border text-text-secondary text-sm rounded-lg hover:border-border-2 transition-colors"
        >
          <RefreshCw size={14} className={loading.executions ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      <div className="bg-surface border border-border rounded-xl overflow-hidden">
        {loading.executions && executions.length === 0 ? (
          <div className="p-8 text-center">
            <Loader2 size={24} className="animate-spin text-text-muted mx-auto" />
          </div>
        ) : executions.length === 0 ? (
          <div className="p-10 text-center text-text-muted text-sm">
            No executions yet. Run a workflow to see results here.
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Workflow</th>
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Status</th>
                <th className="text-left text-xs font-medium text-text-muted px-4 py-3">Trigger</th>
                <th className="text-right text-xs font-medium text-text-muted px-4 py-3">Duration</th>
                <th className="text-right text-xs font-medium text-text-muted px-4 py-3">Started</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {executions.map((exec) => {
                const status = statusConfig[exec.status];
                return (
                  <tr
                    key={exec.id}
                    onClick={() => navigate(`/executions/${exec.id}`)}
                    className="hover:bg-surface-2/50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-text-primary">{exec.workflowName}</p>
                      <p className="text-xs text-text-muted font-mono">{exec.id.slice(0, 8)}…</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx('inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full', status.bg, status.color)}>
                        {status.icon}
                        {status.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-text-secondary capitalize">{exec.trigger}</td>
                    <td className="px-4 py-3 text-right text-sm text-text-muted tabular-nums">
                      {exec.durationMs != null
                        ? exec.durationMs < 1000
                          ? `${exec.durationMs}ms`
                          : `${(exec.durationMs / 1000).toFixed(1)}s`
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-xs text-text-muted">
                      {formatDistanceToNow(new Date(exec.startedAt), { addSuffix: true })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
