import { useCallback } from 'react';
import type { Node, Edge } from 'reactflow';
import { useStore } from '../store';
import type { WorkflowDefinition, WorkflowNode, WorkflowEdge, NodeType } from '../types';

// ── Conversion helpers ────────────────────────────────────────────────────────

export function workflowNodesToFlow(nodes: WorkflowNode[]): Node[] {
  return nodes.map((n) => ({
    id: n.id,
    type: n.type,
    position: n.position,
    data: {
      label: n.name,
      nodeType: n.type,
      config: n.config,
      disabled: n.disabled ?? false,
      status: undefined,
    },
  }));
}

export function workflowEdgesToFlow(edges: WorkflowEdge[]): Edge[] {
  return edges.map((e) => ({
    id: e.id,
    source: e.source,
    sourceHandle: e.sourceHandle,
    target: e.target,
    targetHandle: e.targetHandle,
    animated: false,
    type: 'smoothstep',
  }));
}

export function flowNodesToWorkflow(nodes: Node[]): WorkflowNode[] {
  return nodes.map((n) => ({
    id: n.id,
    type: n.data.nodeType as NodeType,
    name: n.data.label as string,
    config: (n.data.config as Record<string, unknown>) ?? {},
    position: n.position,
    disabled: (n.data.disabled as boolean | undefined) ?? false,
  }));
}

export function flowEdgesToWorkflow(edges: Edge[]): WorkflowEdge[] {
  return edges.map((e) => ({
    id: e.id,
    source: e.source,
    sourceHandle: e.sourceHandle ?? 'output',
    target: e.target,
    targetHandle: e.targetHandle ?? 'input',
  }));
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useWorkflow() {
  const {
    selectedWorkflow,
    editorNodes,
    editorEdges,
    isDirty,
    setEditorNodes,
    setEditorEdges,
    markDirty,
    markClean,
    saveWorkflow,
    selectWorkflow,
    loading,
  } = useStore();

  const loadWorkflowToEditor = useCallback(
    (definition: WorkflowDefinition) => {
      setEditorNodes(workflowNodesToFlow(definition.nodes));
      setEditorEdges(workflowEdgesToFlow(definition.edges));
      markClean();
    },
    [setEditorNodes, setEditorEdges, markClean]
  );

  const saveCurrentWorkflow = useCallback(async () => {
    if (!selectedWorkflow) return;

    const definition: WorkflowDefinition = {
      nodes: flowNodesToWorkflow(editorNodes),
      edges: flowEdgesToWorkflow(editorEdges),
      variables: selectedWorkflow.definition.variables,
    };

    await saveWorkflow({
      id: selectedWorkflow.id,
      name: selectedWorkflow.name,
      description: selectedWorkflow.description,
      definition,
      tags: selectedWorkflow.tags,
      isActive: selectedWorkflow.isActive,
    });
  }, [selectedWorkflow, editorNodes, editorEdges, saveWorkflow]);

  const updateNodeConfig = useCallback(
    (nodeId: string, config: Record<string, unknown>) => {
      setEditorNodes(
        editorNodes.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, config } } : n
        )
      );
      markDirty();
    },
    [editorNodes, setEditorNodes, markDirty]
  );

  const updateNodeName = useCallback(
    (nodeId: string, name: string) => {
      setEditorNodes(
        editorNodes.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, label: name } } : n
        )
      );
      markDirty();
    },
    [editorNodes, setEditorNodes, markDirty]
  );

  const removeNode = useCallback(
    (nodeId: string) => {
      setEditorNodes(editorNodes.filter((n) => n.id !== nodeId));
      setEditorEdges(editorEdges.filter((e) => e.source !== nodeId && e.target !== nodeId));
      markDirty();
    },
    [editorNodes, editorEdges, setEditorNodes, setEditorEdges, markDirty]
  );

  return {
    selectedWorkflow,
    editorNodes,
    editorEdges,
    isDirty,
    isSaving: loading.saving,
    isExecuting: loading.executing,
    loadWorkflowToEditor,
    saveCurrentWorkflow,
    updateNodeConfig,
    updateNodeName,
    removeNode,
    selectWorkflow,
    markDirty,
  };
}
