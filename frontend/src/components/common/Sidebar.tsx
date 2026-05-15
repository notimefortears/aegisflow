import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  GitBranch,
  PlaySquare,
  KeyRound,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  LogOut,
  Zap,
} from 'lucide-react';
import { clsx } from 'clsx';
import { useStore } from '../../store';

interface NavItem {
  label: string;
  to: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard', icon: <LayoutDashboard size={18} /> },
  { label: 'Workflows', to: '/workflows-list', icon: <GitBranch size={18} /> },
  { label: 'Executions', to: '/executions', icon: <PlaySquare size={18} /> },
  { label: 'Credentials', to: '/credentials', icon: <KeyRound size={18} /> },
  { label: 'Settings', to: '/settings', icon: <Settings size={18} /> },
];

export default function Sidebar() {
  const { sidebarExpanded, toggleSidebar, user, logout } = useStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside
      className={clsx(
        'flex flex-col h-full bg-surface border-r border-border transition-all duration-300 ease-in-out shrink-0',
        sidebarExpanded ? 'w-60' : 'w-16'
      )}
    >
      {/* Logo */}
      <div
        className={clsx(
          'flex items-center h-14 border-b border-border px-3 shrink-0',
          sidebarExpanded ? 'gap-2.5' : 'justify-center'
        )}
      >
        <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shrink-0">
          <Shield size={16} className="text-white" />
        </div>
        {sidebarExpanded && (
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-semibold text-text-primary leading-tight">AegisFlow</span>
            <span className="text-[10px] text-text-muted leading-tight">AI Automation</span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 overflow-y-auto">
        <ul className="space-y-0.5 px-2">
          {navItems.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center rounded-md transition-colors duration-150 group',
                    sidebarExpanded ? 'px-2.5 py-2 gap-2.5' : 'p-2 justify-center',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-text-secondary hover:text-text-primary hover:bg-surface-2'
                  )
                }
              >
                <span className="shrink-0">{item.icon}</span>
                {sidebarExpanded && (
                  <span className="text-sm font-medium truncate">{item.label}</span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        {/* Quick actions */}
        {sidebarExpanded && (
          <div className="px-4 mt-4">
            <p className="text-[10px] uppercase tracking-wider text-text-muted mb-2 font-medium">
              Quick Actions
            </p>
            <button
              onClick={() => navigate('/workflows/new/edit')}
              className="w-full flex items-center gap-2 px-2.5 py-2 rounded-md text-sm text-text-secondary hover:text-text-primary hover:bg-surface-2 transition-colors"
            >
              <Zap size={16} />
              <span>New Workflow</span>
            </button>
          </div>
        )}
      </nav>

      {/* User / bottom section */}
      <div className="border-t border-border p-2 shrink-0">
        {sidebarExpanded && user && (
          <div className="flex items-center gap-2.5 px-2 py-2 mb-1">
            <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
              <span className="text-xs font-medium text-primary">
                {user.name.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-text-primary truncate">{user.name}</p>
              <p className="text-[10px] text-text-muted truncate">{user.email}</p>
            </div>
          </div>
        )}

        <button
          onClick={handleLogout}
          className={clsx(
            'flex items-center rounded-md text-text-muted hover:text-error hover:bg-error/5 transition-colors w-full',
            sidebarExpanded ? 'gap-2.5 px-2.5 py-2' : 'p-2 justify-center'
          )}
        >
          <LogOut size={16} className="shrink-0" />
          {sidebarExpanded && <span className="text-sm">Log out</span>}
        </button>

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className={clsx(
            'flex items-center rounded-md text-text-muted hover:text-text-primary hover:bg-surface-2 transition-colors w-full mt-1',
            sidebarExpanded ? 'gap-2.5 px-2.5 py-2' : 'p-2 justify-center'
          )}
        >
          {sidebarExpanded ? (
            <>
              <ChevronLeft size={16} className="shrink-0" />
              <span className="text-xs">Collapse</span>
            </>
          ) : (
            <ChevronRight size={16} className="shrink-0" />
          )}
        </button>
      </div>
    </aside>
  );
}
