import React from 'react';
import { RelationshipGraph } from '../components/graph/RelationshipGraph';

export function GraphPage({ caseData, cases = [], selectedCaseId, onSelectCase }) {
  const caseObj = caseData?.case || caseData?.input || {};
  const caseId = caseObj.case_id || selectedCaseId;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Case Relationship Graph
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Visualizing verified TigerGraph graph entities and relationships strictly for case {caseId}
          </p>
        </div>

        {/* Single-case switcher */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 font-medium">Investigating Case:</span>
          <select
            value={selectedCaseId}
            onChange={(e) => onSelectCase(e.target.value)}
            className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-800"
          >
            {cases.map((c) => (
              <option key={c.case_id} value={c.case_id}>
                {c.case_id} — Txn #{c.first_suspicious_txn_id || c.flagged_txn_id}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs">
        <RelationshipGraph graphData={caseData?.graph} />
      </div>
    </div>
  );
}
