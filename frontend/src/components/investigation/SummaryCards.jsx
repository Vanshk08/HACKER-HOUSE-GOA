import {
  Percent,
  CheckCircle2,
  Fingerprint,
  ArrowRightCircle,
  FileText,
} from 'lucide-react';
import { Card } from '../common/Card';
import {
  formatNumber,
  formatPercent,
  getVerdictTheme,
} from '../../utils/formatters';

export function SummaryCards({ caseData }) {
  const caseObj = caseData?.case || caseData?.input || {};
  const assessment = caseData?.assessment || {};
  const policy = caseData?.policy || {};
  const sar = caseData?.sar || {};
  const nextActions = caseData?.next_best_actions || {};

  // 1. Fraud Probability (Primary) & Intake Score (Secondary)
  const fraudProbability =
    caseObj.fraud_probability !== undefined && caseObj.fraud_probability !== null
      ? caseObj.fraud_probability
      : assessment.fraud_probability;

  const initialRiskScore =
    caseObj.risk_score !== undefined && caseObj.risk_score !== null
      ? caseObj.risk_score
      : caseData?.input?.risk_score;

  // 2. Verdict (Confirmed Fraud, Suspected Fraud, Uncertain, Legitimate)
  const verdict = caseObj.verdict || assessment.verdict || 'uncertain';
  const verdictTheme = getVerdictTheme(verdict);
  const confidence =
    caseObj.confidence !== undefined && caseObj.confidence !== null
      ? caseObj.confidence
      : assessment.confidence;

  // 3. Pattern & Description
  const pattern = caseObj.pattern || 'none';
  const patternDescription =
    caseObj.pattern_description ||
    (pattern === 'none' ? 'No specific fraud pattern identified.' : '');

  // 4. Next Best Actions (Safe handling of objects { action, route, reason })
  const finalNBA = Array.isArray(nextActions.final)
    ? nextActions.final
    : Array.isArray(policy.actions)
    ? policy.actions
    : [];

  const initialNBA = Array.isArray(nextActions.initial)
    ? nextActions.initial
    : [];

  // Helper to safely format NBA item
  const formatNBAItem = (item) => {
    if (!item) return { action: 'NONE', route: '', reason: '' };
    if (typeof item === 'string') {
      return { action: item, route: '', reason: '' };
    }
    return {
      action: item.action || 'ACTION',
      route: item.route || '',
      reason: item.reason || '',
    };
  };

  // 5. SAR Determination
  const sarFile = sar.file !== undefined ? sar.file : false;
  const sarReason =
    sar.reason ||
    (Array.isArray(sar.reasons) && sar.reasons[0]) ||
    (sarFile ? 'Mandatory SAR filing criteria met.' : 'SAR threshold not met (exposure <= $1,000, no verified multi-card cluster).');

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      {/* Card 1: Fraud Probability */}
      <Card className="border-slate-200/90 hover:border-slate-300">
        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
          <span className="font-semibold uppercase tracking-wider text-[10px]">
            Fraud Probability
          </span>
          <Percent className="h-4 w-4 text-indigo-500" />
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-3xl font-extrabold text-slate-900 tracking-tight font-mono">
            {fraudProbability !== null && fraudProbability !== undefined
              ? formatPercent(fraudProbability)
              : 'N/A'}
          </span>
          {initialRiskScore !== null && initialRiskScore !== undefined && (
            <span className="text-[11px] text-slate-400 font-mono">
              (Intake: {formatNumber(initialRiskScore, 2)})
            </span>
          )}
        </div>
        <div className="mt-2">
          {fraudProbability !== null && fraudProbability !== undefined ? (
            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
              <div
                className={`h-full ${
                  fraudProbability >= 0.7
                    ? 'bg-rose-500'
                    : fraudProbability >= 0.3
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
                style={{ width: `${Math.min(Math.max(fraudProbability * 100, 3), 100)}%` }}
              />
            </div>
          ) : (
            <div className="text-[11px] text-slate-400 italic">Evaluating probability...</div>
          )}
        </div>
        <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] text-slate-400 flex items-center justify-between">
          <span>Final Assessment</span>
          <span className="font-semibold text-slate-600">
            {fraudProbability >= 0.7 ? 'High Risk' : fraudProbability >= 0.3 ? 'Moderate Risk' : 'Low Risk'}
          </span>
        </div>
      </Card>

      {/* Card 2: Final Investigation Verdict */}
      <Card
        className={`border-2 ${
          verdict === 'confirmed_fraud' || verdict === 'suspected_fraud'
            ? 'border-rose-300 bg-rose-50/20'
            : verdict === 'uncertain'
            ? 'border-amber-300 bg-amber-50/20'
            : 'border-emerald-300 bg-emerald-50/20'
        }`}
      >
        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
          <span className="font-semibold uppercase tracking-wider text-[10px]">
            Investigation Verdict
          </span>
          <CheckCircle2 className={`h-4 w-4 ${verdictTheme.text}`} />
        </div>
        <div className="flex items-baseline gap-2">
          <span className={`text-xl font-extrabold tracking-tight capitalize ${verdictTheme.text}`}>
            {verdictTheme.label}
          </span>
        </div>
        <div className="mt-2 flex items-center gap-2 text-xs text-slate-600">
          <span>Confidence:</span>
          <strong className="font-mono text-slate-900">
            {confidence !== null && confidence !== undefined ? formatPercent(confidence) : 'N/A'}
          </strong>
        </div>
        <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] text-slate-500 truncate">
          Synthesized by LangGraph Assessment
        </div>
      </Card>

      {/* Card 3: Fraud Pattern & Description */}
      <Card className="border-slate-200/90">
        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
          <span className="font-semibold uppercase tracking-wider text-[10px]">
            Pattern Classification
          </span>
          <Fingerprint className="h-4 w-4 text-slate-400" />
        </div>
        <div className="flex flex-col gap-1">
          <span
            className={`inline-block px-2 py-0.5 rounded-md text-xs font-bold font-mono tracking-tight ${
              pattern !== 'none'
                ? 'bg-indigo-50 text-indigo-800 border border-indigo-200'
                : 'bg-slate-100 text-slate-600 border border-slate-200'
            }`}
          >
            {pattern !== 'none' ? pattern.replace(/_/g, ' ').toUpperCase() : 'NO PATTERN'}
          </span>
          <p className="text-[11px] text-slate-500 leading-tight line-clamp-2 mt-1">
            {patternDescription || 'No specific fraud pattern identified.'}
          </p>
        </div>
        <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] text-slate-400 flex items-center justify-between">
          <span>Pattern Status</span>
          <span className="font-semibold text-slate-600">
            {pattern !== 'none' ? 'Identified' : 'Standard Baseline'}
          </span>
        </div>
      </Card>

      {/* Card 4: Next Best Actions */}
      <Card className="border-slate-200/90">
        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
          <span className="font-semibold uppercase tracking-wider text-[10px]">
            Next Best Action (NBA)
          </span>
          <ArrowRightCircle className="h-4 w-4 text-slate-400" />
        </div>
        <div className="space-y-1.5">
          {finalNBA.slice(0, 2).map((rawItem, i) => {
            const item = formatNBAItem(rawItem);
            return (
              <div key={i} className="flex flex-col text-xs text-slate-800">
                <div className="flex items-center gap-1.5 font-bold">
                  <span className="h-1.5 w-1.5 rounded-full bg-indigo-600 shrink-0" />
                  <span>{item.action.replace(/_/g, ' ')}</span>
                  {item.route && (
                    <span className="text-[9px] uppercase font-mono px-1 py-0.2 rounded bg-slate-100 text-slate-500 border border-slate-200">
                      {item.route}
                    </span>
                  )}
                </div>
                {item.reason && (
                  <p className="text-[10px] text-slate-500 line-clamp-1 ml-3 mt-0.5">
                    {item.reason}
                  </p>
                )}
              </div>
            );
          })}
          {finalNBA.length === 0 && (
            <span className="text-xs text-slate-400 italic">No operational action required</span>
          )}
        </div>
        <div className="mt-3 pt-2 border-t border-slate-100 text-[10px] text-slate-400 truncate">
          Initial:{' '}
          <span className="text-slate-600 font-medium">
            {initialNBA.length > 0
              ? initialNBA.map((x) => (typeof x === 'object' ? x.action : String(x))).join(' → ')
              : 'VERIFY'}
          </span>
        </div>
      </Card>

      {/* Card 5: SAR Determination */}
      <Card className="border-slate-200/90">
        <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
          <span className="font-semibold uppercase tracking-wider text-[10px]">
            SAR Determination
          </span>
          <FileText className="h-4 w-4 text-slate-400" />
        </div>
        <div>
          {sarFile ? (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              FILE SAR REPORT
            </div>
          ) : (
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-slate-100 text-slate-700 border border-slate-200">
              <span className="h-2 w-2 rounded-full bg-slate-400" />
              DO NOT FILE
            </div>
          )}
        </div>
        <p className="mt-2 text-[11px] text-slate-500 line-clamp-2 leading-tight">
          {sarReason}
        </p>
        <div className="mt-2 pt-2 border-t border-slate-100 text-[10px] text-slate-400">
          Regulatory Compliance Gate
        </div>
      </Card>
    </div>
  );
}
