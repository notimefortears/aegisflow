import { useState } from 'react';
import { Loader2, User, Shield, Bell } from 'lucide-react';
import { useStore } from '../store';

export default function Settings() {
  const { user, toast } = useStore();
  const [saving, setSaving] = useState(false);

  return (
    <div className="p-6 max-w-2xl mx-auto animate-fade-in">
      <h1 className="text-xl font-bold text-text-primary mb-6">Settings</h1>

      {/* Profile section */}
      <div className="bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <User size={15} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">Profile</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Email</label>
            <input
              type="email"
              value={user?.email ?? ''}
              disabled
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-muted text-xs cursor-not-allowed"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Display Name</label>
            <input
              type="text"
              defaultValue={user?.name ?? ''}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Role</label>
            <span className="inline-flex px-2.5 py-1 bg-primary/10 text-primary text-xs font-medium rounded-full capitalize">
              {user?.role}
            </span>
          </div>
        </div>
      </div>

      {/* Security section */}
      <div className="bg-surface border border-border rounded-xl p-5 mb-4">
        <div className="flex items-center gap-2 mb-4">
          <Shield size={15} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">Security</h2>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Current Password</label>
            <input type="password" placeholder="••••••••" className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary" />
          </div>
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">New Password</label>
            <input type="password" placeholder="••••••••" className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary" />
          </div>
          <button className="px-4 py-2 bg-surface-2 border border-border text-text-secondary text-sm rounded-lg hover:border-border-2 hover:text-text-primary transition-colors">
            Update password
          </button>
        </div>
      </div>

      {/* Notifications */}
      <div className="bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Bell size={15} className="text-text-muted" />
          <h2 className="text-sm font-semibold text-text-primary">Notifications</h2>
        </div>
        <div className="space-y-3">
          {[
            { label: 'Execution failures', description: 'Email when a workflow fails' },
            { label: 'Human gate requests', description: 'Email when approval is needed' },
            { label: 'Security alerts', description: 'Email on PII or injection detection' },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between">
              <div>
                <p className="text-sm text-text-primary">{item.label}</p>
                <p className="text-xs text-text-muted">{item.description}</p>
              </div>
              <div className="w-9 h-5 rounded-full bg-primary/20 cursor-pointer" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
