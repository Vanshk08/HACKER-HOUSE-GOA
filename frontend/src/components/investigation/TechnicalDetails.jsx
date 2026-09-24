import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Code2, Copy, Check } from 'lucide-react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';

export function TechnicalDetails({ caseData }) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const caseObj = caseData?.case || {};
  const toolCallsCount =
    typeof caseData?.tool_calls === 'number'
      ? caseData.tool_calls
      : Array.isArray(caseData?.tool_calls)
      ? caseData.tool_calls.length
      : caseData?.investigation?.tool_call_count || 0;

  // Safe sanitized record without secrets
  const sanitized = {
    case_id: caseData?.case_id || caseObj.case_id,
    first_suspicious_txn_id: caseObj.first_suspicious_txn_id || caseObj.flagged_txn_id || caseData?.input?.flagged_txn_id,
    verdict: caseObj.verdict || caseData?.assessment?.verdict,
    fraud_probability: caseObj.fraud_probability,
    pattern: caseObj.pattern,
    pattern_description: caseObj.pattern_description,
    affected_txn_ids: caseObj.affected_txn_ids,
    connected_card_ids: caseObj.connected_card_ids,
    connected_device_profiles: caseObj.connected_device_profiles,
    similar_prior_cases: caseObj.similar_prior_cases,
    written_to_graph: caseObj.written_to_graph,
    graph_case_id: caseObj.graph_case_id,
    provider: caseData?.provider || 'openrouter',
    model: caseData?.model || 'google/gemini-2.5-flash',
    status: caseData?.status || caseObj.status,
    runtime_seconds: caseData?.latency_s || caseData?.runtime_seconds || caseData?.latency?.seconds,
    tokens: caseData?.tokens ?? 0,
    tool_calls: toolCallsCount,
    stop_reason: caseData?.stop_reason,
    policy_actions: caseData?.next_best_actions?.final || caseData?.policy?.actions,
    sar_file: caseData?.sar?.file,
    sar_reason: caseData?.sar?.reason,
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(sanitized, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Card className="border-slate-200">
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        <div className="flex items-center gap-2">
          <Code2 className="h-4 w-4 text-slate-500" />
          <span className="text-xs font-semibold text-slate-800">
            Technical Execution & Model Telemetry
          </span>
          <span className="text-[10px] text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
            Safe Metadata Only
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          )}
        </div>
      </div>

      {isOpen && (
        <div className="mt-4 pt-4 border-t border-slate-100">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs mb-4">
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">AI Provider</span>
              <strong className="text-slate-800">{sanitized.provider}</strong>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Configured Model</span>
              <strong className="text-slate-800 truncate block">{sanitized.model}</strong>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Latency</span>
              <strong className="text-slate-800">{sanitized.runtime_seconds ? `${sanitized.runtime_seconds}s` : '—'}</strong>
            </div>
            <div className="p-2.5 bg-slate-50 rounded-lg border border-slate-200/60">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Tool Calls</span>
              <strong className="text-slate-800">{toolCallsCount} executions</strong>
            </div>
          </div>

          <div className="relative">
            <div className="absolute right-2 top-2 z-10">
              <Button size="sm" variant="outline" icon={copied ? Check : Copy} onClick={handleCopy}>
                {copied ? 'Copied' : 'Copy JSON'}
              </Button>
            </div>
            <pre className="p-4 bg-slate-900 text-slate-100 rounded-xl text-[11px] font-mono overflow-x-auto max-h-64 leading-relaxed">
              {JSON.stringify(sanitized, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </Card>
  );
}
