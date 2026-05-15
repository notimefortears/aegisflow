import { ShieldCheck, ShieldAlert, UserCheck } from 'lucide-react';
import type { DashboardStats } from '../../types';

interface SecurityMetricsProps {
  stats: DashboardStats | null;
  loading?: boolean;
}

export default function SecurityMetrics({ stats, loading }: SecurityMetricsProps) {
  const metrics = [
    {
      icon: <ShieldAlert size={16} className="text-warning" />,
      label: 'PII Detections',
      value: stats?.piiDetections ?? 0,
      bg: 'bg-warning/10',
    },
    {
      icon: <ShieldCheck size={16} className="text-error" />,
      label: 'Injection Blocks',
      value: stats?.injectionBlocks ?? 0,
      bg: 'bg-error/10',
    },
    {
      icon: <UserCheck size={16} className="text-info" />,
      label: 'Human Gates Pending',
      value: stats?.humanGatesPending ?? 0,
      bg: 'bg-info/10',
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-3">
      {metrics.map((m) => (
        <div key={m.label} className="bg-surface border border-border rounded-xl p-4">
          <div className={`w-8 h-8 rounded-lg ${m.bg} flex items-center justify-center mb-3`}>
            {m.icon}
          </div>
          {loading ? (
            <div className="h-7 w-12 bg-surface-2 rounded animate-pulse mb-1" />
          ) : (
            <p className="text-2xl font-bold text-text-primary tabular-nums">{m.value}</p>
          )}
          <p className="text-xs text-text-muted">{m.label}</p>
        </div>
      ))}
    </div>
  );
}
