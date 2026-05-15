import { ShieldAlert, ShieldCheck, ShieldX } from 'lucide-react';
import type { Execution } from '../../types';

interface SecurityReportProps {
  execution: Execution;
}

export default function SecurityReport({ execution }: SecurityReportProps) {
  const nodes = Object.values(execution.nodes);
  const flaggedNodes = nodes.filter((n) => {
    const flags = n.outputData?.security_flags as string[] | undefined;
    return flags && flags.length > 0;
  });

  const piiDetected = flaggedNodes.filter((n) => {
    const flags = n.outputData?.security_flags as string[];
    return flags.includes('pii_detected');
  });

  const injectionBlocked = flaggedNodes.filter((n) => {
    const flags = n.outputData?.security_flags as string[];
    return flags.includes('injection_blocked') || flags.includes('blocked_pii');
  });

  if (flaggedNodes.length === 0) {
    return (
      <div className="flex items-center gap-2 p-4 bg-success/5 border border-success/20 rounded-xl">
        <ShieldCheck size={18} className="text-success shrink-0" />
        <div>
          <p className="text-sm font-medium text-success">No security issues detected</p>
          <p className="text-xs text-text-muted">All nodes passed security checks</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <ShieldAlert size={15} className="text-warning" />
        <p className="text-sm font-semibold text-text-primary">Security Report</p>
        <span className="text-xs px-2 py-0.5 rounded-full bg-warning/10 text-warning">{flaggedNodes.length} flags</span>
      </div>

      {piiDetected.length > 0 && (
        <div className="p-3 bg-warning/5 border border-warning/20 rounded-xl">
          <p className="text-xs font-medium text-warning mb-2">PII Detected ({piiDetected.length} nodes)</p>
          {piiDetected.map((n) => (
            <p key={n.nodeId} className="text-xs text-text-secondary">· {n.nodeName}</p>
          ))}
        </div>
      )}

      {injectionBlocked.length > 0 && (
        <div className="p-3 bg-error/5 border border-error/20 rounded-xl">
          <div className="flex items-center gap-1.5 mb-2">
            <ShieldX size={13} className="text-error" />
            <p className="text-xs font-medium text-error">Injection attempts blocked ({injectionBlocked.length})</p>
          </div>
          {injectionBlocked.map((n) => (
            <p key={n.nodeId} className="text-xs text-text-secondary">· {n.nodeName}</p>
          ))}
        </div>
      )}
    </div>
  );
}
