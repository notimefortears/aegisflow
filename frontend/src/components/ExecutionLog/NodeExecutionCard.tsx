import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, Loader2, Clock, ShieldAlert } from 'lucide-react';
import { clsx } from 'clsx';
import type { NodeExecutionRecord, NodeStatus } from '../../types';

interface NodeExecutionCardProps {
  record: NodeExecutionRecord;
  isSelected?: boolean;
  onClick?: () => void;
}

const statusStyles: Record<NodeStatus, { icon: React.ReactNode; color: string; bg: string }> = {
  pending: { icon: <Clock size={12} />, color: 'text-text-muted', bg: 'bg-surface-2' },
  running: { icon: <Loader2 size={12} className="animate-spin" />, color: 'text-info', bg: 'bg-info/10' },
  success: { icon: <CheckCircle2 size={12} />, color: 'text-success', bg: 'bg-success/10' },
  failed: { icon: <XCircle size={12} />, color: 'text-error', bg: 'bg-error/10' },
  skipped: { icon: <ChevronRight size={12} />, color: 'text-text-muted', bg: 'bg-surface-2' },
  waiting: { icon: <Clock size={12} className="text-warning animate-pulse-ring" />, color: 'text-warning', bg: 'bg-warning/10' },
};

export default function NodeExecutionCard({ record, isSelected, onClick }: NodeExecutionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const status = statusStyles[record.status];
  const hasSecurityFlags = record.outputData?.security_flags && (record.outputData.security_flags as string[]).length > 0;

  return (
    <div
      className={clsx(
        'border rounded-xl overflow-hidden cursor-pointer transition-all',
        isSelected ? 'border-primary' : 'border-border',
      )}
      onClick={onClick}
    >
      {/* Header */}
      <div
        className={clsx('flex items-center gap-3 px-4 py-3 hover:bg-surface-2/50', isSelected && 'bg-primary/5')}
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); onClick?.(); }}
      >
        <div className={clsx('flex items-center gap-1.5 shrink-0 text-xs font-medium px-2 py-0.5 rounded-full', status.bg, status.color)}>
          {status.icon}
          <span className="capitalize">{record.status}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-primary truncate">{record.nodeName}</p>
          <p className="text-xs text-text-muted capitalize">{record.nodeType.replace('_', ' ')}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasSecurityFlags && (
            <ShieldAlert size={14} className="text-warning" title="Security flags raised" />
          )}
          {record.durationMs != null && (
            <span className="text-xs text-text-muted tabular-nums">
              {record.durationMs < 1000 ? `${record.durationMs}ms` : `${(record.durationMs / 1000).toFixed(2)}s`}
            </span>
          )}
          {expanded ? <ChevronDown size={14} className="text-text-muted" /> : <ChevronRight size={14} className="text-text-muted" />}
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-border bg-background p-4 space-y-3 animate-fade-in">
          {record.error && (
            <div className="p-3 bg-error/5 border border-error/20 rounded-lg">
              <p className="text-xs font-medium text-error mb-1">Error</p>
              <p className="text-xs text-text-secondary font-mono">{record.error}</p>
            </div>
          )}

          {record.logs.length > 0 && (
            <div>
              <p className="text-xs font-medium text-text-muted mb-1.5">Logs</p>
              <div className="bg-surface rounded-lg p-2 space-y-0.5 max-h-24 overflow-y-auto">
                {record.logs.map((log, i) => (
                  <p key={i} className="text-[11px] font-mono text-text-secondary">{log}</p>
                ))}
              </div>
            </div>
          )}

          {record.outputData && (
            <div>
              <p className="text-xs font-medium text-text-muted mb-1.5">Output</p>
              <pre className="text-[11px] font-mono text-text-secondary bg-surface rounded-lg p-3 overflow-x-auto max-h-40 overflow-y-auto">
                {JSON.stringify(record.outputData, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
