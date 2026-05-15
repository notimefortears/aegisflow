import { clsx } from 'clsx';
import { NODE_CATALOG, CATEGORY_COLORS, type NodeCategory } from '../utils';
import type { NodeMeta } from '../utils';

const CATEGORY_ORDER: NodeCategory[] = ['trigger', 'ai', 'security', 'integration', 'logic'];
const CATEGORY_LABELS: Record<NodeCategory, string> = {
  trigger: 'Triggers',
  ai: 'AI',
  security: 'Security',
  integration: 'Integrations',
  logic: 'Logic',
};

interface NodePaletteProps {
  onDragStart: (event: React.DragEvent, node: NodeMeta) => void;
}

export default function NodePalette({ onDragStart }: NodePaletteProps) {
  const grouped = CATEGORY_ORDER.reduce<Record<NodeCategory, NodeMeta[]>>(
    (acc, cat) => {
      acc[cat] = NODE_CATALOG.filter((n) => n.category === cat);
      return acc;
    },
    {} as Record<NodeCategory, NodeMeta[]>,
  );

  return (
    <div className="flex flex-col gap-4 p-3">
      {CATEGORY_ORDER.map((cat) => {
        const colors = CATEGORY_COLORS[cat];
        return (
          <div key={cat}>
            <p className={clsx('text-[10px] font-semibold uppercase tracking-wider mb-2', colors.text)}>
              {CATEGORY_LABELS[cat]}
            </p>
            <div className="space-y-1">
              {grouped[cat].map((node) => (
                <div
                  key={node.type}
                  draggable
                  onDragStart={(e) => onDragStart(e, node)}
                  className="flex items-center gap-2.5 px-2.5 py-2 rounded-lg bg-surface-2 hover:bg-border cursor-grab active:cursor-grabbing border border-transparent hover:border-border-2 transition-all select-none"
                  title={node.description}
                >
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0', colors.badge)}>
                    {node.label.slice(0, 3).toUpperCase()}
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-text-primary truncate">{node.label}</p>
                    <p className="text-[10px] text-text-muted truncate">{node.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      <div className="pt-2 border-t border-border">
        <p className="text-[10px] text-text-muted text-center">
          Drag nodes onto the canvas
        </p>
      </div>
    </div>
  );
}
