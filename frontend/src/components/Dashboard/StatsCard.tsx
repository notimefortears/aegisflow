import { clsx } from 'clsx';
import type { LucideIcon } from 'lucide-react';

interface StatsCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  trend?: { value: number; label: string };
  accent?: 'primary' | 'success' | 'warning' | 'error' | 'info';
  loading?: boolean;
}

const accentMap = {
  primary: 'text-primary bg-primary/10',
  success: 'text-success bg-success/10',
  warning: 'text-warning bg-warning/10',
  error: 'text-error bg-error/10',
  info: 'text-info bg-info/10',
};

export default function StatsCard({
  label,
  value,
  icon: Icon,
  trend,
  accent = 'primary',
  loading = false,
}: StatsCardProps) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 hover:border-border-2 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center', accentMap[accent])}>
          <Icon size={18} />
        </div>
        {trend && (
          <span
            className={clsx(
              'text-xs font-medium px-2 py-0.5 rounded-full',
              trend.value >= 0 ? 'text-success bg-success/10' : 'text-error bg-error/10'
            )}
          >
            {trend.value >= 0 ? '+' : ''}{trend.value}% {trend.label}
          </span>
        )}
      </div>
      {loading ? (
        <div className="h-8 w-20 bg-surface-2 rounded animate-pulse" />
      ) : (
        <p className="text-2xl font-bold text-text-primary tabular-nums">{value}</p>
      )}
      <p className="text-xs text-text-muted mt-1">{label}</p>
    </div>
  );
}
