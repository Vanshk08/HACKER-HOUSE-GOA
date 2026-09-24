import React from 'react';

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  disabled = false,
  loading = false,
  onClick,
  className = '',
  type = 'button',
}) {
  const sizeClasses = {
    sm: 'text-xs px-2.5 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  }[size] || 'text-sm px-4 py-2 gap-2';

  const variantClasses = {
    primary:
      'bg-slate-900 text-white hover:bg-slate-800 shadow-xs border border-transparent font-medium disabled:bg-slate-300',
    secondary:
      'bg-white text-slate-700 hover:bg-slate-50 border border-slate-200 shadow-xs font-medium disabled:opacity-50',
    outline:
      'bg-transparent text-slate-700 hover:bg-slate-100 border border-slate-300 font-medium',
    ghost:
      'bg-transparent text-slate-600 hover:bg-slate-100 border border-transparent font-medium',
    danger:
      'bg-red-600 text-white hover:bg-red-700 shadow-xs font-medium disabled:bg-red-300',
    success:
      'bg-emerald-600 text-white hover:bg-emerald-700 shadow-xs font-medium',
  }[variant] || 'bg-slate-900 text-white';

  return (
    <button
      type={type}
      disabled={disabled || loading}
      onClick={onClick}
      className={`inline-flex items-center justify-center rounded-lg transition-colors cursor-pointer disabled:cursor-not-allowed select-none ${sizeClasses} ${variantClasses} ${className}`}
    >
      {loading ? (
        <svg
          className="animate-spin -ml-0.5 h-4 w-4 text-current"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      ) : Icon ? (
        <Icon className="h-4 w-4 shrink-0" />
      ) : null}
      {children}
    </button>
  );
}
