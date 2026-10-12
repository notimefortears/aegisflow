import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GitBranch, PlaySquare, CheckCircle2, TrendingUp, Plus, Shield, Zap,
} from 'lucide-react';
import { useStore } from '../store';
import StatsCard from '../components/Dashboard/StatsCard';
import WorkflowCard from '../components/Dashboard/WorkflowCard';
import RecentExecutions from '../components/Dashboard/RecentExecutions';
import SecurityMetrics from '../components/Dashboard/SecurityMetrics';

export default function Dashboard() {
  const navigate = useNavigate();
  const {
    workflows, executions, dashboardStats,
    fetchWorkflows, fetchExecutions, fetchDashboardStats,
    loading,
  } = useStore();

  useEffect(() => {
    fetchWorkflows();
    fetchExecutions(undefined, 1);
    fetchDashboardStats();
  }, []);

  const stats = dashboardStats;

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Dashboard</h1>
          <p className="text-text-muted text-sm mt-0.5">Overview of your workflow automation</p>
        </div>
        <button
          onClick={() => navigate('/workflows/new/edit')}
          className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={16} />
          New Workflow
        </button>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <StatsCard
          label="Total Workflows"
          value={stats?.totalWorkflows ?? workflows.length}
          icon={GitBranch}
          accent="primary"
          loading={loading.dashboard}
        />
        <StatsCard
          label="Active Workflows"
          value={stats?.activeWorkflows ?? workflows.filter((w) => w.isActive).length}
          icon={Zap}
          accent="success"
          loading={loading.dashboard}
        />
        <StatsCard
          label="Total Executions"
          value={stats?.totalExecutions ?? 0}
          icon={PlaySquare}
          accent="info"
          loading={loading.dashboard}
        />
        <StatsCard
          label="Success Rate"
          value={stats ? `${stats.successRate.toFixed(1)}%` : '—'}
          icon={CheckCircle2}
          accent="success"
          loading={loading.dashboard}
        />
      </div>

      {/* Security metrics */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Shield size={15} className="text-warning" />
          <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Security</h2>
        </div>
        <SecurityMetrics stats={stats} loading={loading.dashboard} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        {/* Workflows */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Workflows</h2>
            <button
              onClick={() => navigate('/workflows-list')}
              className="text-xs text-primary hover:text-primary-light transition-colors"
            >
              View all
            </button>
          </div>
          {loading.workflows ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-20 bg-surface rounded-xl animate-pulse" />
              ))}
            </div>
          ) : workflows.length === 0 ? (
            <div className="bg-surface border border-border rounded-xl p-8 text-center">
              <GitBranch size={32} className="text-text-muted mx-auto mb-3" />
              <p className="text-text-secondary text-sm font-medium mb-1">No workflows yet</p>
              <p className="text-text-muted text-xs mb-4">Create your first automation workflow</p>
              <button
                onClick={() => navigate('/workflows/new/edit')}
                className="px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm rounded-lg transition-colors"
              >
                Create workflow
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              {workflows.slice(0, 5).map((w) => (
                <WorkflowCard key={w.id} workflow={w} />
              ))}
            </div>
          )}
        </div>

        {/* Recent executions */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">Recent Executions</h2>
            <button
              onClick={() => navigate('/executions')}
              className="text-xs text-primary hover:text-primary-light transition-colors"
            >
              View all
            </button>
          </div>
          <div className="bg-surface border border-border rounded-xl px-3 py-1">
            <RecentExecutions
              executions={executions.slice(0, 8)}
              loading={loading.executions}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
