/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0a0a0a',
        surface: '#111111',
        'surface-2': '#1a1a1a',
        border: '#2a2a2a',
        'border-2': '#3a3a3a',
        'text-primary': '#f4f4f5',
        'text-secondary': '#a1a1aa',
        'text-muted': '#71717a',
        primary: {
          DEFAULT: '#7c3aed',
          hover: '#6d28d9',
          light: '#8b5cf6',
          muted: '#7c3aed33',
        },
        success: {
          DEFAULT: '#10b981',
          muted: '#10b98133',
        },
        warning: {
          DEFAULT: '#f59e0b',
          muted: '#f59e0b33',
        },
        error: {
          DEFAULT: '#ef4444',
          muted: '#ef444433',
        },
        info: {
          DEFAULT: '#3b82f6',
          muted: '#3b82f633',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        lg: '0.5rem',
        md: '0.375rem',
        sm: '0.25rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-in-right': 'slideInRight 0.25s ease-out',
        'pulse-ring': 'pulseRing 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseRing: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};
