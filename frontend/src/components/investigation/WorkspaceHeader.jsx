import React, { useState } from 'react';
import {
  Play,
  RotateCw,
  Sparkles,
  AlertCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ArrowRight,
  Database,
  CheckCircle2,
} from 'lucide-react';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { getVerdictTheme, formatNumber } from '../../utils/formatters';

export function WorkspaceHeader({
  caseData,
  cases = [],
  selectedCaseId,
  onSelectCase,
  onStartInvestigation,
  isInvestigating = false,
  investigationError = null,
}) {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [customInput, setCustomInput] = useState('');

  const caseObj = caseData?.case || caseData?.input || {};
  const caseId = caseObj.case_id || selectedCaseId || 'HHG-001';
  const txnId = caseObj.first_suspicious_txn_id || (caseObj.affected_txn_ids && caseObj.affected_txn_ids[0]) || caseObj.flagged_txn_id || caseObj.transaction_id || '3514030';
  const customerId = caseObj.customer_id || 'C12382';
  const cardId = caseObj.card_id || 'C12382-K1';
  const triggerText = caseObj.trigger_text || `Flagged transaction ${txnId}`;
  const triggerType = caseObj.trigger_type || 'risk_score';
  const status = isInvestigating ? 'running' : caseObj.status || 'completed';
  const verdictTheme = getVerdictTheme(caseObj.verdict || caseData?.assessment?.verdict);

  // Stepper logic
  const currentIndex = cases.findIndex((c) => c.case_id === caseId);
  const hasPrev = currentIndex > 0;
  const hasNext = currentIndex < cases.length - 1;

  const handlePrev = () => {
    if (hasPrev) onSelectCase(cases[currentIndex - 1].case_id);
    else if (cases.length > 0) onSelectCase(cases[cases.length - 1].case_id);
  };

  const handleNext = () => {
    if (hasNext) onSelectCase(cases[currentIndex + 1].case_id);
    else if (cases.length > 0) onSelectCase(cases[0].case_id);
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (!customInput.trim()) return;
    const target = customInput.trim();
    const match = cases.find(
      (c) =>
        c.case_id.toLowerCase() === target.toLowerCase() ||
        String(c.first_suspicious_txn_id) === target ||
        String(c.flagged_txn_id) === target
    );
    if (match) {
      onSelectCase(match.case_id);
    } else {
      onSelectCase(target.toUpperCase());
    }
    setCustomInput('');
  };

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs space-y-4">
      {/* Top Demo Mode Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-100 text-xs">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
          </span>
          <span className="font-bold uppercase tracking-wider text-[10px] bg-amber-100 text-amber-900 px-2 py-0.5 rounded border border-amber-200">
            DEMO MODE
          </span>
          <span className="text-slate-600 font-medium">
            Displaying stored investigation results from completed cases (<code className="text-[11px] font-mono text-slate-800 bg-slate-100 px-1 py-0.5 rounded">cases/</code>)
          </span>
        </div>
        <div className="flex items-center gap-3 text-slate-500 text-[11px]">
          <span className="flex items-center gap-1 font-mono">
            <Database className="h-3.5 w-3.5 text-indigo-500" />
            20 Cases Available (HHG-001 - HHG-020)
          </span>
          <span>•</span>
          <span className="flex items-center gap-1 text-emerald-700 font-semibold">
            <CheckCircle2 className="h-3.5 w-3.5" />
            100% Precomputed Ground Truth
          </span>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
        {/* Left Side: Case Identifiers & Trigger */}
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-xs uppercase font-bold tracking-wider text-slate-400">
              Active Case
            </span>

            {/* Stepper buttons (< and >) */}
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
              <button
                type="button"
                onClick={handlePrev}
                title="Previous Case"
                className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition-all cursor-pointer"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={handleNext}
                title="Next Case"
                className="p-1 rounded text-slate-600 hover:text-slate-900 hover:bg-white transition-all cursor-pointer"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            {/* Case Selector Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 text-white font-bold text-base hover:bg-slate-800 transition-colors shadow-2xs cursor-pointer"
              >
                <span>{caseId}</span>
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </button>

              {dropdownOpen && (
                <div className="absolute left-0 mt-1 w-72 bg-white border border-slate-200 rounded-xl shadow-lg z-50 py-1 max-h-80 overflow-y-auto">
                  <div className="px-3 py-1.5 text-[10px] uppercase font-bold text-slate-400 border-b border-slate-100 flex items-center justify-between">
                    <span>Benchmark Cases (HHG-001 - HHG-020)</span>
                    <span>20 Cases</span>
                  </div>
                  {cases.map((c) => {
                    const cTheme = getVerdictTheme(c.verdict);
                    return (
                      <button
                        key={c.case_id}
                        onClick={() => {
                          onSelectCase(c.case_id);
                          setDropdownOpen(false);
                        }}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-50 transition-colors cursor-pointer ${
                          c.case_id === caseId ? 'bg-indigo-50/70 font-semibold text-indigo-700' : 'text-slate-700'
                        }`}
                      >
                        <div className="flex flex-col">
                          <span className="font-bold text-slate-900">{c.case_id}</span>
                          <span className="text-[11px] text-slate-400 font-mono">
                            Txn #{c.first_suspicious_txn_id || c.flagged_txn_id}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${cTheme.bg} ${cTheme.text} ${cTheme.border}`}>
                            {cTheme.label}
                          </span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Status Chip */}
            <Badge
              variant={isInvestigating ? 'blue' : status === 'completed' ? 'green' : 'amber'}
              size="md"
              dot
              pulse={isInvestigating}
            >
              {isInvestigating ? 'Investigation Running...' : 'STORED DEMO RESULT'}
            </Badge>

            {/* Verdict Badge */}
            {caseObj.verdict && !isInvestigating && (
              <span
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${verdictTheme.bg} ${verdictTheme.text} ${verdictTheme.border}`}
              >
                <span className={`h-2 w-2 rounded-full ${verdictTheme.dot}`} />
                VERDICT: {verdictTheme.label.toUpperCase()}
              </span>
            )}
          </div>

          {/* Trigger Text */}
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 font-semibold border border-slate-200">
              {triggerType}
            </span>
            <p className="text-sm font-medium text-slate-800 leading-snug">
              {triggerText}
            </p>
          </div>

          {/* Metadata badges */}
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
            <span>
              Flagged Txn: <strong className="font-mono text-slate-800">#{txnId}</strong>
            </span>
            <span className="text-slate-300">•</span>
            <span>
              Customer: <strong className="font-mono text-slate-800">{customerId}</strong>
            </span>
            <span className="text-slate-300">•</span>
            <span>
              Card ID: <strong className="font-mono text-slate-800">{cardId}</strong>
            </span>
            {caseObj.exposure_usd !== undefined && caseObj.exposure_usd !== null && (
              <>
                <span className="text-slate-300">•</span>
                <span>
                  Exposure: <strong className="text-slate-800">${formatNumber(caseObj.exposure_usd, 2)}</strong>
                </span>
              </>
            )}
            {caseObj.pattern && caseObj.pattern !== 'none' && (
              <>
                <span className="text-slate-300">•</span>
                <span>
                  Pattern: <strong className="text-indigo-700 font-mono font-semibold">{caseObj.pattern.replace(/_/g, ' ')}</strong>
                </span>
              </>
            )}
            {caseObj.written_to_graph && caseObj.graph_case_id && (
              <>
                <span className="text-slate-300">•</span>
                <span className="text-emerald-700 font-semibold flex items-center gap-1">
                  Graph Case: #{caseObj.graph_case_id}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Right Side: Quick Inputs & Action Buttons */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 shrink-0">
          {/* Quick Input Form */}
          <form onSubmit={handleCustomSubmit} className="relative">
            <input
              type="text"
              placeholder="Case / Txn (e.g. HHG-002)..."
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              className="text-xs pl-3 pr-8 py-2 rounded-lg border border-slate-200 focus:outline-hidden focus:border-slate-400 bg-slate-50 w-full sm:w-48"
            />
            <button
              type="submit"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 cursor-pointer"
            >
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </form>

          {/* Demo Case Button */}
          <Button
            variant="secondary"
            size="md"
            icon={Sparkles}
            onClick={() => onSelectCase('HHG-001')}
            disabled={isInvestigating}
          >
            Demo HHG-001
          </Button>

          {/* Replay Stored Investigation Flow */}
          <Button
            variant="primary"
            size="md"
            icon={isInvestigating ? RotateCw : Play}
            loading={isInvestigating}
            disabled={isInvestigating}
            onClick={() => onStartInvestigation(caseId)}
          >
            {isInvestigating ? 'Streaming Steps...' : 'Replay Flow'}
          </Button>
        </div>
      </div>

      {investigationError && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
          <span>{investigationError}</span>
        </div>
      )}
    </div>
  );
}
