import React from 'react';
import { EvidenceDashboard } from '../components/evidence/EvidenceDashboard';
import { RelationshipGraph } from '../components/graph/RelationshipGraph';

export function EvidencePage({ caseData, cases = [], selectedCaseId, onSelectCase }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Evidence Explorer & Graph Context
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Inspecting case evidence discovered through graph queries, historical baselines, and entity mining
          </p>
        </div>

        {/* Case Switcher */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Selected Case:</span>
          <select
            value={selectedCaseId}
            onChange={(e) => onSelectCase(e.target.value)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800"
          >
            {cases.map((c) => (
              <option key={c.case_id} value={c.case_id}>
                {c.case_id} ({c.verdict || 'pending'})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-7">
          <EvidenceDashboard caseData={caseData} />
        </div>
        <div className="lg:col-span-5">
          <RelationshipGraph graphData={caseData?.graph} caseId={selectedCaseId} />
        </div>
      </div>
    </div>
  );
}
