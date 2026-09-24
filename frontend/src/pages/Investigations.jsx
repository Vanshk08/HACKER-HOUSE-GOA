import React from 'react';
import { RecentInvestigations } from '../components/dashboard/RecentInvestigations';

export function Investigations({ cases, onSelectCase, onStartInvestigation }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          Case Directory & History
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Full benchmark dataset of 20 real challenge cases with evaluated verdicts and policy decisions
        </p>
      </div>

      <RecentInvestigations
        cases={cases}
        onSelectCase={onSelectCase}
        onInvestigateCase={onStartInvestigation}
      />
    </div>
  );
}
