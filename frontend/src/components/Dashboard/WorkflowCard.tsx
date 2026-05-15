import { useNavigate } from 'react-router-dom';
import { Play, Pause, GitBranch, Clock, ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';
import { formatDistanceToNow } from 'date-fns';
import type { Workflow } from '../../types';
import { useStore } from '../../store';

interface WorkflowCardProps {
  workflow: Workflow;
}

export default function WorkflowCard({ workflow }: WorkflowCardProps) {
  const navigate = useNavigate();
  const { toggleWorkflowActive, executeWorkflow, toast, loading } = useStore();

  async function handleToggle(e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await toggleWorkflowActive(workflow.id, !workflow.isActive);
    } catch {
      toast('Failed to update workflow status', 'error');
    }
  }

  async function handleRun(e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const exec = await executeWorkflow(workflow.id);
      navigate(`/executions/${exec.id}`);
    } catch {
      toast('Failed to execute workflow', 'error');
    }
  }

  return (
    <div
      onClick={() => navigate(`/workflows/${workflow.id}/edit`)}
      className="group bg-surface border border-border rounded-xl p-4 hover:border-border-2 hover:bg-surface-2/50 cursor-pointer transition-all"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
            <GitBranch size={15} className="text-primary" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-text-primary truncate">{workflow.name}</p>
            {workflow.description && (
              <p className="text-xs text-text-muted truncate">{workflow.description}</p>
            )}
          </div>
        </div>

        <div className={clsx(
          'shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full',
          workflow.isActive
            ? 'bg-success/10 text-success'
            : 'bg-surface-2 text-text-muted'
        )}>
          {workflow.isActive ? 'Active' : 'Inactive'}
        </div>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1 text-xs text-text-muted">
          <Clock size={12} />
          <span>
            {workflow.lastExecutedAt
              ? formatDistanceToNow(new Date(workflow.lastExecutedAt), { addSuffix: true })
              : 'Never run'}
          </span>
        </div>

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={handleToggle}
            title={workflow.isActive ? 'Deactivate' : 'Activate'}
            className="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
          >
            {workflow.isActive ? <Pause size={14} /> : <Play size={14} />}
          </button>
          <button
            onClick={handleRun}
            disabled={loading.executing}
            title="Run now"
            className="p-1.5 rounded-md text-text-muted hover:text-success hover:bg-success/10 transition-colors disabled:opacity-50"
          >
            <Play size={14} />
          </button>
          <ChevronRight size={14} className="text-text-muted" />
        </div>
      </div>

      {workflow.tags.length > 0 && (
        <div className="flex gap-1 flex-wrap mt-3">
          {workflow.tags.map((tag) => (
            <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-surface-2 text-text-muted rounded">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
