import { useState } from 'react';
import { X, PanelLeftClose } from 'lucide-react';
import NodePalette from './NodePalette';
import type { NodeMeta } from '../utils';

interface EditorSidebarProps {
  onDragStart: (event: React.DragEvent, node: NodeMeta) => void;
  onClose?: () => void;
}

export default function EditorSidebar({ onDragStart, onClose }: EditorSidebarProps) {
  return (
    <aside className="w-56 h-full bg-surface border-r border-border flex flex-col">
      <div className="flex items-center justify-between px-3 py-3 border-b border-border shrink-0">
        <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">Nodes</span>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-surface-2 text-text-muted hover:text-text-primary transition-colors"
          >
            <PanelLeftClose size={14} />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto">
        <NodePalette onDragStart={onDragStart} />
      </div>
    </aside>
  );
}
