import React from 'react';
import {
  FileText,
  CheckCircle,
  Wrench,
  Clock,
  ShieldCheck,
  AlertCircle,
} from 'lucide-react';
import { Card } from '../common/Card';
import { formatNumber } from '../../utils/formatters';

export function MetricsRow({ metrics }) {
  const stats = [
    {
      label: 'Total Cases',
      value: metrics?.total_cases ?? 20,
      subtext: 'Real challenge set',
      icon: FileText,
      color: 'text-slate-900',
      bg: 'bg-slate-50',
    },
    {
      label: 'Investigations Completed',
      value: metrics?.completed ?? 20,
      subtext: '100% evaluated',
      icon: CheckCircle,
      color: 'text-emerald-700',
      bg: 'bg-emerald-50',
    },
    {
      label: 'Total Tool Executions',
      value: metrics?.total_tool_calls ?? 200,
      subtext: 'Avg ~10.0 calls / case',
      icon: Wrench,
      color: 'text-indigo-700',
      bg: 'bg-indigo-50',
    },
    {
      label: 'Average Latency',
      value: `${formatNumber(metrics?.average_latency_seconds ?? 24.56, 1)}s`,
      subtext: 'Multi-cycle reasoning',
      icon: Clock,
      color: 'text-blue-700',
      bg: 'bg-blue-50',
    },
    {
      label: 'Suspected Fraud Cases',
      value: metrics?.verdict_counts?.suspected_fraud ?? 8,
      subtext: 'Confirmed / strong pattern',
      icon: AlertCircle,
      color: 'text-rose-700',
      bg: 'bg-rose-50',
    },
    {
      label: 'Uncertain Cases',
      value: metrics?.verdict_counts?.uncertain ?? 11,
      subtext: 'Step-up auth / verification',
      icon: ShieldCheck,
      color: 'text-amber-700',
      bg: 'bg-amber-50',
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      {stats.map((stat, i) => {
        const Icon = stat.icon;
        return (
          <Card key={i} className="p-4! border-slate-200/80">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-slate-500 truncate">{stat.label}</span>
              <div className={`p-1.5 rounded-md ${stat.bg} ${stat.color}`}>
                <Icon className="h-3.5 w-3.5" />
              </div>
            </div>
            <div className="text-2xl font-bold text-slate-900 tracking-tight">{stat.value}</div>
            <div className="text-[11px] text-slate-400 mt-1 truncate">{stat.subtext}</div>
          </Card>
        );
      })}
    </div>
  );
}
