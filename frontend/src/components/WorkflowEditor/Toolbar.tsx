import { Save, Play, ArrowLeft, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { clsx } from 'clsx';
import { useNavigate } from 'react-router-dom';

interface ToolbarProps {
  workflowName: string;
  onNameChange: (name: string) => void;
  onSave: () => void;
  onRun: () => void;
  isDirty: boolean;
  isSaving: boolean;
  isRunning: boolean;
}

export default function Toolbar({
  workflowName,
  onNameChange,
  onSave,
  onRun,
  isDirty,
  isSaving,
  isRunning,
}: ToolbarProps) {
  const navigate = useNavigate();

  return (
    <div className="flex items-center gap-3 h-12 px-4 bg-surface border-b border-border shrink-0">
      <button
        onClick={() => navigate('/dashboard')}
        className="p-1.5 rounded-md text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors"
        title="Back to dashboard"
      >
        <ArrowLeft size={16} />
      </button>

      <div className="w-px h-5 bg-border" />

      <input
        type="text"
        value={workflowName}
        onChange={(e) => onNameChange(e.target.value)}
        placeholder="Untitled Workflow"
        className="flex-1 max-w-xs bg-transparent text-sm font-medium text-text-primary placeholder:text-text-muted focus:outline-none"
      />

      {/* Dirty indicator */}
      {isDirty && !isSaving && (
        <span className="flex items-center gap-1 text-xs text-text-muted">
          <AlertCircle size={12} className="text-warning" />
          Unsaved
        </span>
      )}
      {!isDirty && !isSaving && (
        <span className="flex items-center gap-1 text-xs text-text-muted">
          <CheckCircle2 size={12} className="text-success" />
          Saved
        </span>
      )}

      <div className="flex items-center gap-2 ml-auto">
        <button
          onClick={onSave}
          disabled={isSaving || !isDirty}
          className={clsx(
            'flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
            isDirty
              ? 'bg-surface-2 border border-border text-text-primary hover:border-border-2'
              : 'text-text-muted cursor-default',
          )}
          title="Save (Ctrl+S)"
        >
          {isSaving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
          {isSaving ? 'Saving…' : 'Save'}
        </button>

        <button
          onClick={onRun}
          disabled={isRunning || isDirty}
          className="flex items-center gap-2 px-3 py-1.5 bg-primary hover:bg-primary-hover disabled:opacity-60 text-white rounded-md text-xs font-medium transition-colors"
          title={isDirty ? 'Save first' : 'Run workflow'}
        >
          {isRunning ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
          {isRunning ? 'Running…' : 'Run'}
        </button>
      </div>
    </div>
  );
}
