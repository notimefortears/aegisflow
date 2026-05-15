import { useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useStore } from './store';
import Layout from './components/common/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import WorkflowEditor from './pages/WorkflowEditor';
import Executions from './pages/Executions';
import ExecutionDetail from './pages/ExecutionDetail';
import Settings from './pages/Settings';
import Credentials from './pages/Credentials';
import ToastContainer from './components/common/ToastContainer';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const user = useStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  const { user, fetchWorkflows, fetchDashboardStats } = useStore();

  // Prefetch data when authenticated
  useEffect(() => {
    if (user) {
      fetchWorkflows().catch(() => undefined);
      fetchDashboardStats().catch(() => undefined);
    }
  }, [user, fetchWorkflows, fetchDashboardStats]);

  return (
    <>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="workflows/:id/edit" element={<WorkflowEditor />} />
          <Route path="executions" element={<Executions />} />
          <Route path="executions/:id" element={<ExecutionDetail />} />
          <Route path="credentials" element={<Credentials />} />
          <Route path="settings" element={<Settings />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
      <ToastContainer />
    </>
  );
}
