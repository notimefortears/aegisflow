import { clsx } from 'clsx';

type BadgeVariant = 'default' | 'primary' | 'success' | 'warning' | 'error' | 'info' | 'outline';

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}

const variantClasses: Record<BadgeVariant, string> = {
  default: 'bg-surface-2 text-text-secondary border border-border',
  primary: 'bg-primary/10 text-primary border border-primary/20',
  success: 'bg-success/10 text-success border border-success/20',
  warning: 'bg-warning/10 text-warning border border-warning/20',
  error: 'bg-error/10 text-error border border-error/20',
  info: 'bg-info/10 text-info border border-info/20',
  outline: 'bg-transparent text-text-secondary border border-border',
};

const dotColors: Record<BadgeVariant, string> = {
  default: 'bg-text-muted',
  primary: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-error',
  info: 'bg-info',
  outline: 'bg-text-muted',
};

export default function Badge({ variant = 'default', children, className, dot }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium',
        variantClasses[variant],
        className
      )}
    >
      {dot && <span className={clsx('w-1.5 h-1.5 rounded-full shrink-0', dotColors[variant])} />}
      {children}
    </span>
  );
}
