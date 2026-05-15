import { useState } from 'react';
import type { Execution } from '../../types';
import NodeExecutionCard from './NodeExecutionCard';

interface ExecutionTimelineProps {
  execution: Execution;
}

export default function ExecutionTimeline({ execution }: ExecutionTimelineProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const nodeRecords = Object.values(execution.nodes).sort((a, b) => {
    const ta = a.startedAt ? new Date(a.startedAt).getTime() : 0;
    const tb = b.startedAt ? new Date(b.startedAt).getTime() : 0;
    return ta - tb;
  });

  if (nodeRecords.length === 0) {
    return (
      <div className="text-center py-10 text-text-muted text-sm">
        No node executions recorded yet.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {nodeRecords.map((record) => (
        <NodeExecutionCard
          key={record.nodeId}
          record={record}
          isSelected={selectedNodeId === record.nodeId}
          onClick={() => setSelectedNodeId(selectedNodeId === record.nodeId ? null : record.nodeId)}
        />
      ))}
    </div>
  );
}
