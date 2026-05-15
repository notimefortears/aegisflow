import { clsx } from 'clsx';

interface Field {
  key: string;
  label: string;
  type: 'text' | 'textarea' | 'number' | 'boolean' | 'select';
  options?: string[];
  placeholder?: string;
  defaultValue?: unknown;
}

interface GenericConfigProps {
  fields: Field[];
  config: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

export default function GenericConfig({ fields, config, onChange }: GenericConfigProps) {
  return (
    <div className="space-y-4">
      {fields.map((field) => (
        <div key={field.key}>
          <label className="block text-xs font-medium text-text-secondary mb-1.5">
            {field.label}
          </label>

          {field.type === 'textarea' && (
            <textarea
              value={(config[field.key] as string) ?? ''}
              onChange={(e) => onChange(field.key, e.target.value)}
              placeholder={field.placeholder}
              rows={3}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary placeholder:text-text-muted text-xs font-mono focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary resize-none transition-colors"
            />
          )}

          {field.type === 'text' && (
            <input
              type="text"
              value={(config[field.key] as string) ?? ''}
              onChange={(e) => onChange(field.key, e.target.value)}
              placeholder={field.placeholder}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary placeholder:text-text-muted text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
            />
          )}

          {field.type === 'number' && (
            <input
              type="number"
              value={(config[field.key] as number) ?? field.defaultValue ?? 0}
              onChange={(e) => onChange(field.key, parseFloat(e.target.value))}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
            />
          )}

          {field.type === 'boolean' && (
            <label className="flex items-center gap-2 cursor-pointer">
              <div
                onClick={() => onChange(field.key, !(config[field.key] as boolean))}
                className={clsx(
                  'relative w-9 h-5 rounded-full transition-colors cursor-pointer',
                  config[field.key] ? 'bg-primary' : 'bg-border-2',
                )}
              >
                <div
                  className={clsx(
                    'absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform',
                    config[field.key] ? 'translate-x-4' : 'translate-x-0.5',
                  )}
                />
              </div>
              <span className="text-xs text-text-secondary">
                {config[field.key] ? 'Enabled' : 'Disabled'}
              </span>
            </label>
          )}

          {field.type === 'select' && field.options && (
            <select
              value={(config[field.key] as string) ?? field.defaultValue ?? field.options[0]}
              onChange={(e) => onChange(field.key, e.target.value)}
              className="w-full px-3 py-2 bg-surface-2 border border-border rounded-md text-text-primary text-xs focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-colors"
            >
              {field.options.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          )}
        </div>
      ))}
    </div>
  );
}
