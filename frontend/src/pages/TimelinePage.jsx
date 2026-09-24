import React from 'react';
import { InvestigationTimeline } from '../components/timeline/InvestigationTimeline';
import { ToolExecutionLive } from '../components/tools/ToolExecutionLive';

export function TimelinePage({ caseData, cases = [], selectedCaseId, onSelectCase }) {
  const toolCalls = Array.isArray(caseData?.tool_calls)
    ? caseData.tool_calls
    : (Array.isArray(caseData?.investigation?.tool_call_sequence)
        ? caseData.investigation.tool_call_sequence.map((name, i) => ({
            id: `call_${i}`,
            tool: name,
            status: 'completed',
            timestamp: new Date().toLocaleTimeString(),
          }))
        : []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-slate-900 tracking-tight">
            Investigation Activity Timeline
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Chronological audit log of autonomous agent reasoning steps, tool requests, and policy decisions
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
          <InvestigationTimeline caseData={caseData} />
        </div>
        <div className="lg:col-span-5">
          <ToolExecutionLive toolCalls={toolCalls} isRunning={false} />
        </div>
      </div>
    </div>
  );
}
