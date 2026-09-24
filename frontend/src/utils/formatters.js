/**
 * UI formatting utilities and helpers.
 */

export function formatCurrency(amount) {
  if (amount === null || amount === undefined || isNaN(amount)) {
    return 'N/A';
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatNumber(val, decimals = 2) {
  if (val === null || val === undefined || isNaN(val)) {
    return 'N/A';
  }
  return Number(val).toFixed(decimals);
}

export function formatPercent(val) {
  if (val === null || val === undefined || isNaN(val)) {
    return 'N/A';
  }
  return `${Math.round(val * 100)}%`;
}

export function getVerdictTheme(verdict) {
  switch ((verdict || '').toLowerCase()) {
    case 'confirmed_fraud':
      return {
        bg: 'bg-red-50',
        text: 'text-red-700',
        border: 'border-red-200',
        dot: 'bg-red-500',
        label: 'Confirmed Fraud',
      };
    case 'suspected_fraud':
      return {
        bg: 'bg-rose-50',
        text: 'text-rose-700',
        border: 'border-rose-200',
        dot: 'bg-rose-500',
        label: 'Suspected Fraud',
      };
    case 'uncertain':
      return {
        bg: 'bg-amber-50',
        text: 'text-amber-700',
        border: 'border-amber-200',
        dot: 'bg-amber-500',
        label: 'Uncertain',
      };
    case 'legitimate':
      return {
        bg: 'bg-emerald-50',
        text: 'text-emerald-700',
        border: 'border-emerald-200',
        dot: 'bg-emerald-500',
        label: 'Legitimate',
      };
    default:
      return {
        bg: 'bg-slate-50',
        text: 'text-slate-600',
        border: 'border-slate-200',
        dot: 'bg-slate-400',
        label: verdict ? String(verdict) : 'Pending Review',
      };
  }
}

export function getStatusTheme(status) {
  const s = (status || '').toLowerCase();
  if (['healthy', 'connected', 'completed', 'ready', 'active'].includes(s)) {
    return {
      bg: 'bg-emerald-50',
      text: 'text-emerald-700',
      border: 'border-emerald-200',
      dot: 'bg-emerald-500',
      icon: 'check',
    };
  }
  if (['running', 'investigating', 'executing', 'streaming'].includes(s)) {
    return {
      bg: 'bg-blue-50',
      text: 'text-blue-700',
      border: 'border-blue-200',
      dot: 'bg-blue-500',
      icon: 'loader',
    };
  }
  if (['warning', 'degraded', 'partial', 'uncertain', 'configured'].includes(s)) {
    return {
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      border: 'border-amber-200',
      dot: 'bg-amber-500',
      icon: 'alert',
    };
  }
  if (['failed', 'unavailable', 'error'].includes(s)) {
    return {
      bg: 'bg-red-50',
      text: 'text-red-700',
      border: 'border-red-200',
      dot: 'bg-red-500',
      icon: 'x',
    };
  }
  return {
    bg: 'bg-slate-50',
    text: 'text-slate-600',
    border: 'border-slate-200',
    dot: 'bg-slate-400',
    icon: 'minus',
  };
}

export function getActionTheme(action) {
  switch (action) {
    case 'BLOCK_CARD':
      return 'bg-red-100 text-red-800 border-red-200';
    case 'FREEZE_ACCOUNT':
      return 'bg-rose-100 text-rose-800 border-rose-200';
    case 'STEP_UP_AUTH':
      return 'bg-purple-100 text-purple-800 border-purple-200';
    case 'VERIFY_WITH_CUSTOMER':
      return 'bg-blue-100 text-blue-800 border-blue-200';
    case 'CREATE_CASE':
      return 'bg-slate-100 text-slate-800 border-slate-300';
    case 'ESCALATE_TO_ANALYST':
      return 'bg-amber-100 text-amber-800 border-amber-200';
    case 'FILE_REPORT':
      return 'bg-orange-100 text-orange-800 border-orange-200';
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200';
  }
}
