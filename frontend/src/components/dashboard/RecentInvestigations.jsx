import { useState } from 'react';
import {
  Search,
  ArrowUpRight,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import {
  formatNumber,
  getVerdictTheme,
  getActionTheme,
} from '../../utils/formatters';

export function RecentInvestigations({ cases = [], onSelectCase }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('all');

  const filteredCases = cases.filter((c) => {
    const matchesSearch =
      c.case_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.flagged_txn_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (c.customer_id && c.customer_id.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesVerdict =
      verdictFilter === 'all' ||
      (verdictFilter === 'suspected_fraud' && c.verdict === 'suspected_fraud') ||
      (verdictFilter === 'uncertain' && c.verdict === 'uncertain') ||
      (verdictFilter === 'pending' && (!c.verdict || c.status === 'pending'));

    return matchesSearch && matchesVerdict;
  });

  return (
    <Card
      title="Recent Investigations"
      subtitle="Challenge dataset cases (HHG-001 through HHG-020) evaluated with TigerGraph & LangGraph"
      action={
        <div className="flex items-center gap-2">
          {/* Search */}
          <div className="relative">
            <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search case / txn..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="text-xs pl-8 pr-3 py-1.5 rounded-lg border border-slate-200 focus:outline-hidden focus:border-slate-400 bg-slate-50/50 w-44"
            />
          </div>

          {/* Filter */}
          <select
            value={verdictFilter}
            onChange={(e) => setVerdictFilter(e.target.value)}
            className="text-xs px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-hidden"
          >
            <option value="all">All Verdicts</option>
            <option value="suspected_fraud">Suspected Fraud</option>
            <option value="uncertain">Uncertain</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      }
      bodyClassName="p-0!"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="bg-slate-50/80 border-b border-slate-100 text-slate-500 font-semibold uppercase text-[10px] tracking-wider">
              <th className="py-3 px-4">Case ID</th>
              <th className="py-3 px-4">Txn ID</th>
              <th className="py-3 px-4">Trigger & Profile</th>
              <th className="py-3 px-4">Model Risk</th>
              <th className="py-3 px-4">Investigation Verdict</th>
              <th className="py-3 px-4">Policy Action</th>
              <th className="py-3 px-4">SAR</th>
              <th className="py-3 px-4">Duration</th>
              <th className="py-3 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-700">
            {filteredCases.map((c) => {
              const verdictTheme = getVerdictTheme(c.verdict);
              const actions = c.actions || [];
              const primaryAction = actions[0] || 'Pending';

              return (
                <tr
                  key={c.case_id}
                  onClick={() => onSelectCase(c.case_id)}
                  className="hover:bg-slate-50/80 transition-colors cursor-pointer group"
                >
                  {/* Case ID */}
                  <td className="py-3.5 px-4 font-semibold text-slate-900 flex items-center gap-1.5">
                    <span className="group-hover:text-indigo-600 transition-colors">
                      {c.case_id}
                    </span>
                    {c.verdict === 'suspected_fraud' && (
                      <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
                    )}
                  </td>

                  {/* Flagged Txn */}
                  <td className="py-3.5 px-4 font-mono text-slate-600 font-medium">
                    #{c.flagged_txn_id}
                  </td>

                  {/* Trigger & Profile */}
                  <td className="py-3.5 px-4 max-w-xs">
                    <div className="text-slate-800 font-medium truncate">
                      {c.trigger_text || `Trigger: ${c.trigger_type}`}
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      Customer: {c.customer_id} • Card: {c.card_id}
                    </div>
                  </td>

                  {/* Model Risk Score (SEPARATE from Verdict) */}
                  <td className="py-3.5 px-4">
                    {c.initial_risk_score !== null && c.initial_risk_score !== undefined ? (
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-slate-900">
                          {formatNumber(c.initial_risk_score, 2)}
                        </span>
                        <div className="w-12 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${
                              c.initial_risk_score >= 0.75
                                ? 'bg-red-500'
                                : c.initial_risk_score >= 0.5
                                ? 'bg-amber-500'
                                : 'bg-emerald-500'
                            }`}
                            style={{ width: `${c.initial_risk_score * 100}%` }}
                          />
                        </div>
                      </div>
                    ) : (
                      <span className="text-slate-400 italic">Analyst Alert</span>
                    )}
                  </td>

                  {/* Verdict */}
                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${verdictTheme.bg} ${verdictTheme.text} ${verdictTheme.border}`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${verdictTheme.dot}`} />
                      {verdictTheme.label}
                    </span>
                  </td>

                  {/* Policy Action */}
                  <td className="py-3.5 px-4">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium border ${getActionTheme(
                        primaryAction
                      )}`}
                    >
                      {primaryAction.replace(/_/g, ' ')}
                    </span>
                    {actions.length > 1 && (
                      <span className="text-[10px] text-slate-400 ml-1">
                        +{actions.length - 1}
                      </span>
                    )}
                  </td>

                  {/* SAR */}
                  <td className="py-3.5 px-4">
                    {c.sar_file ? (
                      <span className="text-rose-700 font-bold bg-rose-50 border border-rose-200 px-2 py-0.5 rounded text-[10px]">
                        FILE SAR
                      </span>
                    ) : (
                      <span className="text-slate-500 text-[11px]">No</span>
                    )}
                  </td>

                  {/* Duration */}
                  <td className="py-3.5 px-4 text-slate-500 font-mono text-[11px]">
                    {c.runtime_seconds ? `${formatNumber(c.runtime_seconds, 1)}s` : '—'}
                  </td>

                  {/* Action */}
                  <td className="py-3.5 px-4 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectCase(c.case_id);
                      }}
                      className="group-hover:bg-slate-900 group-hover:text-white group-hover:border-slate-900 transition-colors"
                    >
                      Workspace
                      <ArrowUpRight className="h-3 w-3 ml-1" />
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
