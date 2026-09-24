import React from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  Cpu,
  Layers,
  ArrowRight,
} from 'lucide-react';
import { Card } from '../common/Card';
import { getVerdictTheme, formatPercent } from '../../utils/formatters';

export function DecisionPolicyCard({ caseData }) {
  const assessment = caseData?.assessment || {};
  const policy = caseData?.policy || caseData?.policy_decision || {};
  const caseObj = caseData?.case || {};
  const sar = caseData?.sar || {};

  const verdict = caseObj.verdict || assessment.verdict || 'uncertain';
  const verdictTheme = getVerdictTheme(verdict);
  const matchedRules = policy.matched_rules || [];
  const rawActions = caseData?.next_best_actions?.final || policy.actions || [];
  const actions = rawActions.map((a) => (typeof a === 'object' && a !== null ? a.action : String(a)));
  const requiresCustomer = policy.requires_customer_response || (Array.isArray(caseData?.evidence_requests) && caseData.evidence_requests.length > 0) || false;
  const evidenceCount =
    caseObj.evidence?.length ||
    caseData?.investigation?.evidence_count ||
    (typeof caseData?.tool_calls === 'number' ? caseData.tool_calls : caseData?.tool_calls?.length || 5);

  return (
    <Card
      title="Decision & Action Pipeline"
      subtitle="Deterministic policy gates: Evidence → Assessment → Policy Rules → Operational Action"
      className="bg-linear-to-b from-white to-slate-50/50"
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 items-stretch relative">
        {/* Stage 1: Evidence Discovery */}
        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-bold text-[10px] uppercase tracking-wider">Step 1</span>
              <Layers className="h-4 w-4 text-indigo-500" />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1">Graph Evidence</h4>
            <p className="text-xs text-slate-500 mb-3">
              TigerGraph queries evaluated across transaction, customer, card, regions, and precedents.
            </p>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-500">Evidence Count:</span>
            <strong className="font-mono text-slate-900">
              {evidenceCount} items
            </strong>
          </div>
        </div>

        {/* Stage 2: Assessment Synthesis */}
        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-bold text-[10px] uppercase tracking-wider">Step 2</span>
              <Cpu className="h-4 w-4 text-blue-500" />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1">Assessment Synthesis</h4>
            <div className="mt-1">
              <span
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${verdictTheme.bg} ${verdictTheme.text} ${verdictTheme.border}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${verdictTheme.dot}`} />
                {verdict.toUpperCase().replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-2 line-clamp-3">
              {caseObj.summary || assessment.reasoning || caseObj.reasoning || 'Synthesized across evaluated competing hypotheses.'}
            </p>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-500">Confidence:</span>
            <strong className="font-mono text-slate-900">
              {formatPercent(caseObj.confidence || assessment.confidence || 0.62)}
            </strong>
          </div>
        </div>

        {/* Stage 3: Policy Engine */}
        <div className="p-4 rounded-xl bg-white border border-slate-200/90 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-bold text-[10px] uppercase tracking-wider">Step 3</span>
              <ShieldCheck className="h-4 w-4 text-emerald-500" />
            </div>
            <h4 className="text-sm font-bold text-slate-900 mb-1">Policy Engine Rules</h4>
            <div className="flex flex-wrap gap-1 mt-1.5 mb-2">
              {matchedRules.map((rule) => (
                <span
                  key={rule}
                  className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-slate-100 text-slate-800 border border-slate-300"
                >
                  {rule}
                </span>
              ))}
            </div>
            <p className="text-[11px] text-slate-500 line-clamp-2">
              {policy.rationale ? policy.rationale.split('\n')[0] : 'Deterministic rule evaluation completed.'}
            </p>
          </div>
          <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-500">Customer Outreach:</span>
            <strong className="text-slate-900">
              {requiresCustomer ? 'Required' : 'Not Required'}
            </strong>
          </div>
        </div>

        {/* Stage 4: Next Best Action & Output */}
        <div className="p-4 rounded-xl bg-slate-900 text-white shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
              <span className="font-bold text-[10px] uppercase tracking-wider text-indigo-400">
                Final Step 4
              </span>
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            </div>
            <h4 className="text-sm font-bold text-white mb-2">Operational Action</h4>

            <div className="space-y-1.5 mb-3">
              {actions.map((act, i) => (
                <div
                  key={i}
                  className="flex items-center gap-1.5 text-xs font-semibold px-2 py-1 rounded bg-slate-800 border border-slate-700 text-indigo-300"
                >
                  <ArrowRight className="h-3 w-3 text-indigo-400" />
                  <span>{act.replace(/_/g, ' ')}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <span>SAR Report:</span>
            <strong className={sar.file ? 'text-rose-400 font-bold' : 'text-slate-300'}>
              {sar.file ? 'FILE' : 'NO FILE'}
            </strong>
          </div>
        </div>
      </div>
    </Card>
  );
}
