import { useEffect, useState } from 'react';
import { Plus, Trash2, KeyRound, Loader2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { useStore } from '../store';
import type { CredentialType } from '../types';
import { credentialsApi } from '../api/client';

const CREDENTIAL_TYPES: { value: CredentialType; label: string }[] = [
  { value: 'anthropic_api_key', label: 'Anthropic API Key' },
  { value: 'openai_api_key', label: 'OpenAI API Key' },
  { value: 'smtp', label: 'SMTP Email' },
  { value: 'http_bearer', label: 'HTTP Bearer Token' },
  { value: 'http_basic', label: 'HTTP Basic Auth' },
  { value: 'postgres', label: 'PostgreSQL' },
  { value: 'webhook_hmac', label: 'Webhook HMAC Secret' },
];

export default function Credentials() {
  const { credentials, fetchCredentials, deleteCredential, toast, loading } = useStore();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', type: 'anthropic_api_key' as CredentialType, value: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchCredentials();
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await credentialsApi.create({ name: form.name, type: form.type, values: { key: form.value } });
      await fetchCredentials();
      setShowForm(false);
      setForm({ name: '', type: 'anthropic_api_key', value: '' });
      toast('Credential saved (encrypted)', 'success');
    } catch {
      toast('Failed to save credential', 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!window.confirm(`Delete credential "${name}"?`)) return;
    try {
      await deleteCredential(id);
    } catch {
      toast('Failed to delete credential', 'error');
    }
  }

  return (
    <div className="p-6 max-w-3xl mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-text-primary">Credentials</h1>
          <p className="text-text-muted text-sm mt-0.5">API keys and secrets, stored AES-256 encrypted</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={16} />
          Add Credential
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={handleCreate} className="bg-surface border border-border rounded-xl p-5 mb-6 animate-fade-in">
          <h3 className="text-sm font-semibold text-text-primary mb-4">New Credential</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">Name</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="my-anthropic-key"
                required
                className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">Type</label>
              <select
                value={form.type}
                onChange={(e) => setForm({ ...form, type: e.target.value as CredentialType })}
                className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
              >
                {CREDENTIAL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-text-secondary mb-1.5">Value</label>
              <input
                type="password"
                value={form.value}
                onChange={(e) => setForm({ ...form, value: e.target.value })}
                placeholder="sk-ant-api03-…"
                required
                className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary font-mono"
              />
            </div>
          </div>
          <div className="flex items-center gap-3 mt-5">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary-hover disabled:opacity-60 text-white text-sm rounded-lg transition-colors"
            >
              {saving && <Loader2 size={14} className="animate-spin" />}
              Save encrypted
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* List */}
      <div className="bg-surface border border-border rounded-xl divide-y divide-border">
        {loading.credentials && credentials.length === 0 ? (
          <div className="p-8 text-center"><Loader2 size={20} className="animate-spin text-text-muted mx-auto" /></div>
        ) : credentials.length === 0 ? (
          <div className="p-8 text-center">
            <KeyRound size={28} className="text-text-muted mx-auto mb-3" />
            <p className="text-text-secondary text-sm">No credentials yet</p>
          </div>
        ) : (
          credentials.map((cred) => (
            <div key={cred.id} className="flex items-center gap-4 px-5 py-4">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <KeyRound size={14} className="text-primary" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">{cred.name}</p>
                <p className="text-xs text-text-muted">{cred.type} · added {formatDistanceToNow(new Date(cred.createdAt), { addSuffix: true })}</p>
              </div>
              <button
                onClick={() => handleDelete(cred.id, cred.name)}
                className="p-2 rounded-md text-text-muted hover:text-error hover:bg-error/10 transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
