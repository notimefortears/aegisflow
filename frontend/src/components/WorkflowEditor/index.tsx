import { useCallback, useRef, useEffect, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
  type ReactFlowInstance,
  BackgroundVariant,
} from 'reactflow';
import 'reactflow/dist/style.css';

import { useNavigate } from 'react-router-dom';
import { nanoid } from 'nanoid';
import { useStore } from '../../store';
import { definitionToFlow, flowToDefinition, toRFNodeType } from './utils';
import type { NodeMeta } from './utils';
import type { Workflow } from '../../types';
import Toolbar from './Toolbar';
import EditorSidebar from './Sidebar';
import NodeConfigPanel from './NodeConfig';
import AINode from './NodeTypes/AINode';
import SecurityNode from './NodeTypes/SecurityNode';
import TriggerNode from './NodeTypes/TriggerNode';
import LogicNode from './NodeTypes/LogicNode';
import IntegrationNode from './NodeTypes/IntegrationNode';

const nodeTypes = {
  aiNode: AINode,
  securityNode: SecurityNode,
  triggerNode: TriggerNode,
  logicNode: LogicNode,
  integrationNode: IntegrationNode,
};

const defaultEdgeOptions = {
  type: 'smoothstep',
  style: { stroke: '#3a3a3a', strokeWidth: 2 },
  animated: false,
};

interface WorkflowEditorCanvasProps {
  workflow: Workflow;
}

export default function WorkflowEditorCanvas({ workflow }: WorkflowEditorCanvasProps) {
  const navigate = useNavigate();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [rfInstance, setRfInstance] = useState<ReactFlowInstance | null>(null);

  const {
    saveWorkflow, executeWorkflow,
    isDirty, markDirty, markClean,
    selectedNodeId, selectNode,
    loading, toast,
  } = useStore();

  const { nodes: initialNodes, edges: initialEdges } = definitionToFlow(workflow.definition);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [workflowName, setWorkflowName] = useState(workflow.name);
  const [showSidebar, setShowSidebar] = useState(true);

  // Keyboard shortcuts
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedNodeId && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
          setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
          setEdges((eds) => eds.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
          selectNode(null);
          markDirty();
        }
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedNodeId, nodes, edges]);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge({ ...params, ...defaultEdgeOptions }, eds));
    markDirty();
  }, []);

  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    selectNode(node.id);
  }, []);

  const onPaneClick = useCallback(() => {
    selectNode(null);
  }, []);

  // Drag-to-canvas: accept dragged node from palette
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const raw = e.dataTransfer.getData('application/aegisflow-node');
    if (!raw || !rfInstance || !reactFlowWrapper.current) return;

    const meta: NodeMeta = JSON.parse(raw);
    const bounds = reactFlowWrapper.current.getBoundingClientRect();
    const position = rfInstance.project({
      x: e.clientX - bounds.left,
      y: e.clientY - bounds.top,
    });

    const newNode: Node = {
      id: nanoid(8),
      type: toRFNodeType(meta.type),
      position,
      data: {
        type: meta.type,
        name: meta.label,
        config: {},
        disabled: false,
      },
    };
    setNodes((nds) => [...nds, newNode]);
    selectNode(newNode.id);
    markDirty();
  }, [rfInstance]);

  function onPaletteDragStart(event: React.DragEvent, meta: NodeMeta) {
    event.dataTransfer.setData('application/aegisflow-node', JSON.stringify(meta));
    event.dataTransfer.effectAllowed = 'move';
  }

  async function handleSave() {
    if (!isDirty) return;
    const definition = flowToDefinition(nodes, edges, workflow.definition);
    try {
      await saveWorkflow({ id: workflow.id, name: workflowName, definition });
      markClean();
    } catch {
      // error already toasted by store
    }
  }

  async function handleRun() {
    try {
      const execution = await executeWorkflow(workflow.id);
      navigate(`/executions/${execution.id}`);
    } catch {
      toast('Failed to start execution', 'error');
    }
  }

  function handleConfigChange(nodeId: string, config: Record<string, unknown>) {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, config } } : n))
    );
    markDirty();
  }

  function handleNameChange(nodeId: string, name: string) {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, name } } : n))
    );
    markDirty();
  }

  function handleToggleDisabled(nodeId: string) {
    setNodes((nds) =>
      nds.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, disabled: !n.data.disabled } } : n))
    );
    markDirty();
  }

  const selectedNode = nodes.find((n) => n.id === selectedNodeId) ?? null;

  return (
    <div className="flex flex-col h-full">
      <Toolbar
        workflowName={workflowName}
        onNameChange={(name) => { setWorkflowName(name); markDirty(); }}
        onSave={handleSave}
        onRun={handleRun}
        isDirty={isDirty}
        isSaving={loading.saving}
        isRunning={loading.executing}
      />

      <div className="flex flex-1 overflow-hidden">
        {showSidebar && (
          <EditorSidebar onDragStart={onPaletteDragStart} onClose={() => setShowSidebar(false)} />
        )}

        <div ref={reactFlowWrapper} className="flex-1 h-full bg-background" onDragOver={onDragOver} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={(changes) => { onNodesChange(changes); }}
            onEdgesChange={(changes) => { onEdgesChange(changes); markDirty(); }}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onInit={setRfInstance}
            nodeTypes={nodeTypes}
            defaultEdgeOptions={defaultEdgeOptions}
            fitView
            proOptions={{ hideAttribution: true }}
            className="bg-background"
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="#2a2a2a"
            />
            <Controls
              className="!bg-surface !border-border !shadow-none"
              showInteractive={false}
            />
            <MiniMap
              nodeColor={(node) => {
                const t = node.data?.type as string;
                if (['claude','openai'].includes(t)) return '#7c3aed';
                if (['pii_scanner','injection_guard','human_gate'].includes(t)) return '#f59e0b';
                if (['webhook','schedule','manual'].includes(t)) return '#10b981';
                if (['http','email','database'].includes(t)) return '#3b82f6';
                return '#3a3a3a';
              }}
              maskColor="#0a0a0a99"
              className="!bg-surface !border-border"
            />
          </ReactFlow>
        </div>

        {selectedNode && (
          <NodeConfigPanel
            node={selectedNode}
            onClose={() => selectNode(null)}
            onConfigChange={handleConfigChange}
            onNameChange={handleNameChange}
            onToggleDisabled={handleToggleDisabled}
          />
        )}
      </div>
    </div>
  );
}
