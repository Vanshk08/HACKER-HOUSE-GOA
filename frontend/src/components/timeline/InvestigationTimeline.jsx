import {
  CheckCircle2,
  Cpu,
  Layers,
  ShieldCheck,
  Search,
} from 'lucide-react';
import { Card } from '../common/Card';

export function InvestigationTimeline({ caseData }) {
  const rawToolCalls = caseData?.tool_calls;
  const toolCalls = Array.isArray(rawToolCalls)
    ? rawToolCalls
    : (Array.isArray(caseData?.investigation?.tool_call_sequence)
        ? caseData.investigation.tool_call_sequence.map((name, i) => ({
            id: `call_${i}`,
            tool: name,
            status: 'completed',
          }))
        : []);

  const caseObj = caseData?.case || caseData?.input || {};
  const assessment = caseData?.assessment || {};
  const policy = caseData?.policy || {};
  const openedAt = caseObj.opened_at || caseData?.input?.opened_at;

  // Build real event sequence without fake timestamps
  const events = [];

  // Event 1: Intake
  const firstTxn = caseObj.first_suspicious_txn_id || caseObj.flagged_txn_id;
  events.push({
    id: 'intake',
    title: 'Investigation Initiated',
    category: 'Intake Trigger',
    description: caseObj.trigger_text || `Flagged transaction #${firstTxn}`,
    icon: Search,
    iconBg: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    timestamp: openedAt || null,
  });

  // Tool Calls sequence
  toolCalls.forEach((tc, idx) => {
    const tool = tc.tool || 'investigative_tool';
    const args = tc.args || {};
    let desc = `Invoked tool ${tool}`;
    if (tool === 'get_transaction') desc = `Retrieved transaction profile and billing attributes`;
    if (tool === 'get_customer_history') desc = `Queried customer historical activity baseline`;
    if (tool === 'get_customer_regions') desc = `Verified customer geographical billing region match`;
    if (tool === 'get_transaction_sequence') desc = `Analyzed surrounding transaction velocity sequence`;
    if (tool === 'get_card_history') desc = `Retrieved card usage history & fallback profile`;
    if (tool === 'get_similar_closed_cases') desc = `Searched historical closed cases for precedent pattern`;
    if (tool === 'get_device_connections') desc = `Inspected shared device profile & syndicate telemetry`;
    if (tool === 'find_shared_origins') desc = `Explored origin clusters in graph network`;
    if (tool === 'investigate_transaction_graph') desc = `Executed Person A MCP graph traversal on TigerGraph HHGOA_IEEE`;
    if (tool === 'request_customer_validation') desc = `Registered external cardholder verification request`;

    events.push({
      id: `tool-${idx}`,
      title: `Tool Execution: ${tool}`,
      category: 'Graph Investigation',
      description: desc,
      args: Object.keys(args).length > 0 ? JSON.stringify(args) : null,
      icon: Layers,
      iconBg: 'bg-slate-100 text-slate-700 border-slate-200',
      timestamp: null, // Honest: do not fabricate timestamps
    });
  });

  // Assessment Event
  if (assessment.verdict || caseObj.verdict) {
    events.push({
      id: 'assessment',
      title: 'Assessment Synthesized',
      category: 'LangGraph Reasoning',
      description: `Verdict concluded: ${assessment.verdict || caseObj.verdict} (Confidence: ${Math.round(
        (assessment.confidence || caseObj.confidence || 0.6) * 100
      )}%)`,
      icon: Cpu,
      iconBg: 'bg-blue-50 text-blue-700 border-blue-200',
      timestamp: null,
    });
  }

  // Policy Decision Event
  const rawActions = policy.actions || caseData?.policy_decision?.actions || caseData?.next_best_actions?.final || [];
  const actionList = Array.isArray(rawActions)
    ? rawActions.map((a) => (typeof a === 'object' && a !== null ? a.action || JSON.stringify(a) : String(a)))
    : [];
  if (actionList.length > 0) {
    events.push({
      id: 'policy',
      title: 'Policy Decision Formulated',
      category: 'Rule Engine',
      description: `Actions selected: ${actionList.join(', ')} (${(policy.matched_rules || []).join(', ')})`,
      icon: ShieldCheck,
      iconBg: 'bg-purple-50 text-purple-700 border-purple-200',
      timestamp: null,
    });
  }

  // Final Output
  events.push({
    id: 'complete',
    title: 'Investigation Completed',
    category: 'Operational Output',
    description: `Investigation concluded with ${toolCalls.length} tool executions across multi-cycle state graph.`,
    icon: CheckCircle2,
    iconBg: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    timestamp: null,
  });

  return (
    <Card
      title="Investigation Sequence & Activity Timeline"
      subtitle="Observable lifecycle trace (real event sequence without synthetic timestamps)"
      className="border-slate-200/90"
    >
      <div className="relative pl-6 space-y-6 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
        {events.map((evt, idx) => {
          const Icon = evt.icon;
          return (
            <div key={evt.id} className="relative flex items-start gap-4 group">
              {/* Timeline marker */}
              <div
                className={`absolute -left-6 mt-0.5 h-5 w-5 rounded-full border flex items-center justify-center bg-white shadow-2xs ${evt.iconBg}`}
              >
                <Icon className="h-3 w-3" />
              </div>

              {/* Event Content */}
              <div className="flex-1 bg-white p-3.5 rounded-xl border border-slate-200/80 hover:border-slate-300 transition-colors shadow-2xs">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-slate-900">{evt.title}</span>
                    <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600">
                      {evt.category}
                    </span>
                  </div>
                  {evt.timestamp ? (
                    <span className="text-[11px] font-mono text-slate-400">{evt.timestamp}</span>
                  ) : (
                    <span className="text-[10px] text-slate-400">Step {idx + 1}</span>
                  )}
                </div>

                <p className="text-xs text-slate-600 leading-normal">{evt.description}</p>

                {evt.args && (
                  <div className="mt-2 text-[10px] font-mono text-slate-500 bg-slate-50 px-2 py-1 rounded border border-slate-100 truncate">
                    Args: {evt.args}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
