import { clsx } from 'clsx';
import type { ExecutionStatus, NodeStatus } from '../../types';

type Status = ExecutionStatus | NodeStatus;

interface StatusBadgeProps {
  status: Status;
  size?: 'sm' | 'md';
}

const statusConfig: Record<Status, { label: string; classes: string; dotClass: string }> = {
  pending: {
    label: 'Pending',
    classes: 'bg-surface-2 text-text-secondary border border-border',
    dotClass: 'bg-text-muted',
  },
  running: {
    label: 'Running',
    classes: 'bg-warning/10 text-warning border border-warning/20',
    dotClass: 'bg-warning animate-pulse',
  },
  success: {
    label: 'Success',
    classes: 'bg-success/10 text-success border border-success/20',
    dotClass: 'bg-success',
  },
  failed: {
    label: 'Failed',
    classes: 'bg-error/10 text-error border border-error/20',
    dotClass: 'bg-error',
  },
  cancelled: {
    label: 'Cancelled',
    classes: 'bg-surface-2 text-text-muted border border-border',
    dotClass: 'bg-text-muted',
  },
  skipped: {
    label: 'Skipped',
    classes: 'bg-surface-2 text-text-muted border border-border',
    dotClass: 'bg-text-muted',
  },
  waiting: {
    label: 'Waiting',
    classes: 'bg-info/10 text-info border border-info/20',
    dotClass: 'bg-info animate-pulse',
  },
};

export default function StatusBadge({ status, size = 'md' }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full font-medium',
        size === 'sm' ? 'px-1.5 py-0.5 text-xs' : 'px-2 py-0.5 text-xs',
        config.classes
      )}
    >
      <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', config.dotClass)} />
      {config.label}
    </span>
  );
}
