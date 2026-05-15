import React from 'react';
import { Loader2 } from 'lucide-react';
import { clsx } from 'clsx';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
type Size = 'xs' | 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: React.ReactNode;
  iconRight?: React.ReactNode;
}

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-primary hover:bg-primary-hover text-white shadow-sm shadow-primary/20',
  secondary:
    'bg-surface-2 hover:bg-[#222] text-text-primary border border-border hover:border-border-2',
  ghost:
    'bg-transparent hover:bg-surface-2 text-text-secondary hover:text-text-primary',
  danger:
    'bg-error/10 hover:bg-error/20 text-error border border-error/20 hover:border-error/40',
  outline:
    'bg-transparent border border-border hover:border-border-2 text-text-primary hover:bg-surface-2',
};

const sizeClasses: Record<Size, string> = {
  xs: 'px-2 py-1 text-xs rounded gap-1',
  sm: 'px-3 py-1.5 text-xs rounded gap-1.5',
  md: 'px-4 py-2 text-sm rounded-md gap-2',
  lg: 'px-5 py-2.5 text-sm rounded-md gap-2',
};

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { variant = 'secondary', size = 'md', loading, icon, iconRight, children, className, disabled, ...props },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={clsx(
          'inline-flex items-center justify-center font-medium transition-all duration-150',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 focus-visible:ring-offset-background',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'whitespace-nowrap select-none',
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        {...props}
      >
        {loading ? (
          <Loader2 size={size === 'xs' ? 12 : 14} className="animate-spin shrink-0" />
        ) : icon ? (
          <span className="shrink-0">{icon}</span>
        ) : null}
        {children && <span>{children}</span>}
        {iconRight && !loading && <span className="shrink-0">{iconRight}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';
export default Button;
