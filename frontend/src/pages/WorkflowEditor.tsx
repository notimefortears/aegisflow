import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { useStore } from '../store';
import WorkflowEditorCanvas from '../components/WorkflowEditor';
import type { Workflow, WorkflowDefinition } from '../types';

const EMPTY_DEFINITION: WorkflowDefinition = { nodes: [], edges: [], variables: {} };

function buildNewWorkflow(): Workflow {
  return {
    id: '',
    name: 'Untitled Workflow',
    definition: EMPTY_DEFINITION,
    isActive: false,
    tags: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    createdBy: '',
  };
}

export default function WorkflowEditorPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { workflows, fetchWorkflows, loading } = useStore();
  const [workflow, setWorkflow] = useState<Workflow | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (id === 'new') {
      setWorkflow(buildNewWorkflow());
      return;
    }

    const found = workflows.find((w) => w.id === id);
    if (found) {
      setWorkflow(found);
    } else {
      // Try fetching
      fetchWorkflows().then(() => {
        const w = workflows.find((w) => w.id === id);
        if (w) setWorkflow(w);
        else setNotFound(true);
      });
    }
  }, [id, workflows]);

  if (notFound) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-text-primary font-medium mb-2">Workflow not found</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="text-primary text-sm hover:underline"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    );
  }

  if (!workflow || loading.workflows) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={24} className="animate-spin text-text-muted" />
      </div>
    );
  }

  return <WorkflowEditorCanvas workflow={workflow} />;
}
