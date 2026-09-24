import React from 'react';

export function Card({
  children,
  className = '',
  title,
  subtitle,
  action,
  headerClassName = '',
  bodyClassName = '',
  footer,
  hover = false,
  onClick,
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl border border-slate-200/80 shadow-xs transition-all duration-200 ${
        hover ? 'hover:shadow-md hover:border-slate-300 cursor-pointer' : ''
      } ${className}`}
    >
      {(title || subtitle || action) && (
        <div
          className={`px-5 py-4 border-b border-slate-100 flex items-center justify-between gap-4 ${headerClassName}`}
        >
          <div>
            {title && (
              <h3 className="text-sm font-semibold text-slate-900 tracking-tight flex items-center gap-2">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
            )}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
      {footer && (
        <div className="px-5 py-3 bg-slate-50/60 border-t border-slate-100 rounded-b-xl text-xs text-slate-500">
          {footer}
        </div>
      )}
    </div>
  );
}
