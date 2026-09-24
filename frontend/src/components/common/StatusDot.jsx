import React from 'react';
import { getStatusTheme } from '../../utils/formatters';

export function StatusDot({ status, pulse = false, className = '' }) {
  const theme = getStatusTheme(status);
  return (
    <span className={`relative inline-flex items-center justify-center ${className}`}>
      {pulse && (
        <span
          className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${theme.dot}`}
        />
      )}
      <span className={`relative inline-block h-2 w-2 rounded-full ${theme.dot}`} />
    </span>
  );
}
