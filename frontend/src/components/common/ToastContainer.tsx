import { X, CheckCircle2, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import { useStore } from '../../store';

const icons = {
  success: <CheckCircle2 size={16} className="text-success shrink-0" />,
  error: <AlertCircle size={16} className="text-error shrink-0" />,
  warning: <AlertTriangle size={16} className="text-warning shrink-0" />,
  info: <Info size={16} className="text-info shrink-0" />,
};

const borderColors = {
  success: 'border-success/20',
  error: 'border-error/20',
  warning: 'border-warning/20',
  info: 'border-info/20',
};

export default function ToastContainer() {
  const { toasts, dismissToast } = useStore();

  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={clsx(
            'pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg border',
            'bg-surface shadow-xl shadow-black/40 min-w-[280px] max-w-[400px]',
            'animate-fade-in',
            borderColors[toast.type]
          )}
        >
          {icons[toast.type]}
          <p className="flex-1 text-sm text-text-primary">{toast.message}</p>
          <button
            onClick={() => dismissToast(toast.id)}
            className="text-text-muted hover:text-text-primary transition-colors"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
