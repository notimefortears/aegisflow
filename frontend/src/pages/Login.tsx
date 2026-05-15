import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Loader2 } from 'lucide-react';
import { useStore } from '../store';

export default function Login() {
  const navigate = useNavigate();
  const { login, toast } = useStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch {
      toast('Invalid credentials', 'error');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-primary flex items-center justify-center mb-4 shadow-lg shadow-primary/25">
            <Shield size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-text-primary">AegisFlow</h1>
          <p className="text-text-muted text-sm mt-1">AI Workflow Automation</p>
        </div>

        {/* Card */}
        <div className="bg-surface border border-border rounded-xl p-6 shadow-xl">
          <h2 className="text-lg font-semibold text-text-primary mb-1">Welcome back</h2>
          <p className="text-text-muted text-sm mb-6">Sign in to your workspace</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@example.com"
                required
                autoFocus
                className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary placeholder:text-text-muted text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary placeholder:text-text-muted text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-primary hover:bg-primary-hover disabled:opacity-60 text-white font-medium rounded-md text-sm transition-colors"
            >
              {loading ? <Loader2 size={16} className="animate-spin" /> : null}
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        <p className="text-center text-text-muted text-xs mt-6">
          Self-hosted · Your data stays with you
        </p>
      </div>
    </div>
  );
}
