import React from 'react';
import { StatusDot } from './StatusDot';

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  status = null,
  pulse = false,
  className = '',
}) {
  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5 font-medium',
    md: 'text-xs px-2.5 py-1 font-medium',
    lg: 'text-sm px-3 py-1.5 font-semibold',
  }[size] || 'text-xs px-2.5 py-1 font-medium';

  const variantClasses = {
    default: 'bg-slate-100 text-slate-700 border border-slate-200',
    green: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
    blue: 'bg-blue-50 text-blue-700 border border-blue-200',
    amber: 'bg-amber-50 text-amber-700 border border-amber-200',
    red: 'bg-red-50 text-red-700 border border-red-200',
    purple: 'bg-purple-50 text-purple-700 border border-purple-200',
  }[variant] || 'bg-slate-100 text-slate-700 border border-slate-200';

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ${sizeClasses} ${variantClasses} ${className}`}
    >
      {dot && <StatusDot status={status || variant} pulse={pulse} />}
      {children}
    </span>
  );
}
