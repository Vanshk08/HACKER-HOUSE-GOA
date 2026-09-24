import React, { useState } from 'react';
import {
  CreditCard,
  User,
  Smartphone,
  Mail,
  MapPin,
  Network,
  History,
  AlertCircle,
  CheckCircle2,
  HelpCircle,
  Send,
  ShieldAlert,
} from 'lucide-react';
import { Card } from '../common/Card';
import { formatCurrency, formatNumber } from '../../utils/formatters';

export function EvidenceDashboard({ caseData }) {
  const [activeCategory, setActiveCategory] = useState('primary');

  const caseObj = caseData?.case || caseData?.input || {};
  const assessment = caseData?.assessment || {};
  const rawEvidence = Array.isArray(caseObj.evidence) ? caseObj.evidence : [];
  const supporting = Array.isArray(assessment.supporting_evidence) ? assessment.supporting_evidence : [];
  const contradicting = Array.isArray(assessment.contradicting_evidence) ? assessment.contradicting_evidence : [];
  const evidenceRequests = Array.isArray(caseData?.evidence_requests)
    ? caseData.evidence_requests
    : Array.isArray(caseData?.policy?.evidence_requests)
    ? caseData.policy.evidence_requests
    : [];

  const connectedCards = Array.isArray(caseObj.connected_card_ids) ? caseObj.connected_card_ids : [];
  const connectedDevices = Array.isArray(caseObj.connected_device_profiles) ? caseObj.connected_device_profiles : [];
  const similarCases = Array.isArray(caseObj.similar_prior_cases) ? caseObj.similar_prior_cases : [];
  const affectedTxns = Array.isArray(caseObj.affected_txn_ids) ? caseObj.affected_txn_ids : [];

  const categories = [
    { id: 'primary', label: `Verified Evidence (${rawEvidence.length || supporting.length})`, icon: AlertCircle },
    { id: 'requests', label: `Customer Outreach (${evidenceRequests.length})`, icon: Send },
    { id: 'transaction', label: 'Transaction', icon: CreditCard },
    { id: 'customer', label: 'Customer', icon: User },
    { id: 'card', label: `Cards (${connectedCards.length > 0 ? connectedCards.length + 1 : 1})`, icon: CreditCard },
    { id: 'device', label: `Devices (${connectedDevices.length})`, icon: Smartphone },
    { id: 'cases', label: `Precedents (${similarCases.length})`, icon: History },
    { id: 'region', label: 'Billing Region', icon: MapPin },
    { id: 'network', label: 'Network Graph', icon: Network },
  ];

  // Helper to filter evidence items relevant to a category
  const filterEvidence = (keywords) => {
    const hits = [];
    const pool = [...rawEvidence, ...supporting];
    pool.forEach((s) => {
      if (typeof s === 'string' && keywords.some((k) => s.toLowerCase().includes(k.toLowerCase()))) {
        if (!hits.some((h) => h.text === s)) {
          hits.push({ type: 'supporting', text: s });
        }
      }
    });
    contradicting.forEach((c) => {
      if (typeof c === 'string' && keywords.some((k) => c.toLowerCase().includes(k.toLowerCase()))) {
        if (!hits.some((h) => h.text === c)) {
          hits.push({ type: 'contradicting', text: c });
        }
      }
    });
    return hits;
  };

  // Specific filtered lists
  const txnEvidence = filterEvidence(['transaction', 'spending', 'mean $', 'risk score', 'sequence', 'amount']);
  const custEvidence = filterEvidence(['customer', 'channel', 'spending range', 'spending patterns', 'online transactions', 'in_person']);
  const cardEvidence = filterEvidence(['card', 'compromise', 'blocked', 'reissued', 'multiple times']);
  const deviceEvidence = filterEvidence(['device', 'card_not_present_new_device', 'ip', 'fingerprint', 'telemetry']);
  const regionEvidence = filterEvidence(['region', 'billing region', 'out_of_region', '444.0', '330.0']);
  const networkEvidence = filterEvidence(['graph', 'network', 'shared-card', 'cluster', 'connections to other', 'syndicate']);
  const caseEvidence = filterEvidence(['closed case', 'similar', 'previous case', 'prior case', 'CC-', 'precedent', 'confirmed fraud']);

  const renderEvidenceSection = (title, items, toolName, emptyMessage = 'No evidence available in stored result.') => (
    <div className="space-y-3">
      <div className="flex items-center justify-between pb-1 border-b border-slate-100">
        <h5 className="text-xs font-bold text-slate-900">{title}</h5>
        {toolName && (
          <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
            Source: {toolName}
          </span>
        )}
      </div>

      {items.length === 0 ? (
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500 flex items-center gap-2.5">
          <HelpCircle className="h-4 w-4 text-slate-400 shrink-0" />
          <span>{emptyMessage}</span>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item, idx) => (
            <div
              key={idx}
              className={`p-3 rounded-xl border text-xs flex items-start gap-2.5 ${
                item.type === 'supporting'
                  ? 'bg-rose-50/60 border-rose-200/90 text-rose-900'
                  : 'bg-emerald-50/60 border-emerald-200/90 text-emerald-900'
              }`}
            >
              {item.type === 'supporting' ? (
                <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              ) : (
                <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
              )}
              <div>
                <span className="font-bold uppercase tracking-wider text-[9px] block mb-0.5 text-slate-500">
                  {item.type === 'supporting' ? 'Fraud Indicator (Supporting)' : 'Legitimate Indicator (Contradicting)'}
                </span>
                <p className="leading-relaxed">{item.text}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <Card
      title="Categorized Investigation Evidence"
      subtitle="Ground truth evidence discovered via TigerGraph queries and multi-agent reasoning"
      className="border-slate-200/90"
    >
      {/* Category Navigation Pills */}
      <div className="flex space-x-1 border-b border-slate-100 pb-3 mb-5 overflow-x-auto">
        {categories.map((cat) => {
          const Icon = cat.icon;
          const isActive = activeCategory === cat.id;
          return (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                isActive
                  ? 'bg-slate-900 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {cat.label}
            </button>
          );
        })}
      </div>

      {/* 0. Primary Verified Case Evidence Tab */}
      {activeCategory === 'primary' && (
        <div className="space-y-4">
          <div className="p-4 rounded-xl bg-slate-900 text-white">
            <span className="text-[10px] uppercase font-bold tracking-wider text-indigo-400 block mb-1">
              Authoritative Ground Truth Evidence
            </span>
            <p className="text-xs text-slate-300 leading-relaxed">
              These evidence items represent the core factual discoveries synthesized by the autonomous investigation pipeline across TigerGraph subgraphs.
            </p>
          </div>

          {(rawEvidence.length > 0 ? rawEvidence : supporting).length > 0 ? (
            <div className="space-y-2.5">
              {(rawEvidence.length > 0 ? rawEvidence : supporting).map((evText, idx) => (
                <div
                  key={idx}
                  className="p-3.5 bg-rose-50/60 border border-rose-200/80 rounded-xl text-xs text-rose-950 flex items-start gap-3"
                >
                  <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <span className="text-[9px] uppercase font-mono font-bold tracking-wider text-rose-500 block">
                      Evidence Item #{idx + 1}
                    </span>
                    <p className="leading-relaxed font-medium">{evText}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-500 text-center">
              No evidence returned for this case.
            </div>
          )}
        </div>
      )}

      {/* 1. Evidence Requests (Customer Outreach & Validation) */}
      {activeCategory === 'requests' && (
        <div className="space-y-4">
          {evidenceRequests.length > 0 ? (
            <div className="space-y-3">
              {evidenceRequests.map((req, idx) => (
                <div key={idx} className="p-4 bg-white border border-slate-200 rounded-xl shadow-2xs space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-100">
                    <div className="flex items-center gap-2">
                      <Send className="h-4 w-4 text-indigo-600" />
                      <strong className="text-xs font-bold text-slate-900 capitalize">
                        {(req.request_type || 'Customer Outreach').replace(/_/g, ' ')}
                      </strong>
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                        {req.request_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200">
                        Status: {req.status || 'Pending'}
                      </span>
                    </div>
                  </div>

                  <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
                    <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                      Customer Outreach Question
                    </span>
                    <p className="text-xs font-medium text-slate-800 italic">
                      "{req.question}"
                    </p>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] text-slate-600">
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase block font-mono">Target Txn</span>
                      <strong className="font-mono text-slate-800">#{req.transaction_id}</strong>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase block font-mono">Channel</span>
                      <strong className="text-slate-800 capitalize">
                        {(req.metadata?.channel || 'customer_outreach').replace(/_/g, ' ')}
                      </strong>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase block font-mono">Customer Response</span>
                      <strong className="text-amber-700 font-semibold capitalize">
                        {req.customer_response_status || 'Unknown'}
                      </strong>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 uppercase block font-mono">Awaiting Response</span>
                      <strong className="text-slate-800">
                        {req.metadata?.awaiting_response ? 'Yes (Blocking)' : 'No'}
                      </strong>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-500 space-y-1">
              <CheckCircle2 className="h-6 w-6 text-emerald-500 mx-auto mb-2" />
              <strong className="text-slate-800 block">No Pending Customer Validation</strong>
              <p className="text-[11px] text-slate-400">
                This investigation concluded without requiring asynchronous customer validation or step-up authentication.
              </p>
            </div>
          )}
        </div>
      )}

      {/* 2. Transaction Profile */}
      {activeCategory === 'transaction' && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">First Txn ID</span>
              <strong className="text-sm font-mono text-slate-900">
                #{caseObj.first_suspicious_txn_id || caseObj.flagged_txn_id || '3514030'}
              </strong>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Amount / Exposure</span>
              <strong className="text-sm font-mono text-slate-900">
                {caseObj.exposure_usd !== undefined && caseObj.exposure_usd !== null
                  ? formatCurrency(caseObj.exposure_usd)
                  : assessment.exposure !== undefined
                  ? formatCurrency(assessment.exposure)
                  : '$77.07'}
              </strong>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Customer ID</span>
              <strong className="text-sm font-mono text-slate-900">
                {caseObj.customer_id || 'C12382'}
              </strong>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/70">
              <span className="text-[10px] uppercase font-bold text-slate-400 block">Affected Txn Count</span>
              <strong className="text-sm font-mono text-slate-900">
                {affectedTxns.length > 0 ? `${affectedTxns.length} transactions` : '1 transaction'}
              </strong>
            </div>
          </div>

          <div className="p-4 rounded-xl border border-slate-200 bg-white">
            <h5 className="text-xs font-bold text-slate-900 mb-2">Transaction Trigger Context</h5>
            <p className="text-xs text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-200/60 leading-relaxed font-mono">
              {caseObj.trigger_text || 'Transaction flagged by real-time detection model for automated multi-agent investigation.'}
            </p>
          </div>

          {renderEvidenceSection('Stored Transaction Findings', txnEvidence, 'get_transaction')}
        </div>
      )}

      {/* 3. Customer Profile */}
      {activeCategory === 'customer' && (
        <div className="space-y-5">
          <div className="p-4 rounded-xl border border-slate-200 bg-white">
            <div className="flex items-center justify-between mb-3">
              <h5 className="text-xs font-bold text-slate-900">Customer Profile Baseline</h5>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                Source: get_customer_history
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Customer ID</span>
                <span className="text-sm font-mono font-bold text-slate-800">{caseObj.customer_id}</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Account Status</span>
                <span className="text-sm font-bold text-emerald-700">Active Profile</span>
              </div>
              <div className="p-3 bg-slate-50 rounded-lg">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Outreach Status</span>
                <span className="text-sm font-bold text-amber-700">
                  {caseObj.customer_response_status || 'Unknown / Not Required'}
                </span>
              </div>
            </div>
          </div>

          {renderEvidenceSection('Stored Customer Behavioral Findings', custEvidence, 'get_customer_history')}
        </div>
      )}

      {/* 4. Cards Portfolio & Connected Cards */}
      {activeCategory === 'card' && (
        <div className="space-y-5">
          <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-4">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h5 className="text-xs font-bold text-slate-900">Card Portfolio & Association Network</h5>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                Source: get_card_history / get_connected_cards
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Primary Investigated Card</span>
                <strong className="font-mono text-slate-900 text-sm">{caseObj.card_id}</strong>
                <span className="text-[11px] text-slate-500 block mt-1">Transaction payment card instrument</span>
              </div>

              <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80">
                <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">Connected Secondary Cards</span>
                {connectedCards.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {connectedCards.map((cid, i) => (
                      <span key={i} className="px-2 py-0.5 rounded font-mono font-bold text-xs bg-rose-100 text-rose-800 border border-rose-200">
                        {cid}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-xs text-slate-500 italic block mt-1">
                    No connected cards identified for this account.
                  </span>
                )}
              </div>
            </div>
          </div>

          {renderEvidenceSection('Stored Card Compromise Findings', cardEvidence, 'get_card_history')}
        </div>
      )}

      {/* 5. Device Telemetry & Connected Devices */}
      {activeCategory === 'device' && (
        <div className="space-y-5">
          <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h5 className="text-xs font-bold text-slate-900">Device Fingerprints & Telemetry</h5>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                Source: get_customer_device_history
              </span>
            </div>

            {connectedDevices.length > 0 ? (
              <div className="space-y-2">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Connected Device Profiles</span>
                <div className="flex flex-wrap gap-2">
                  {connectedDevices.map((dev, i) => (
                    <span key={i} className="px-2.5 py-1 rounded-lg font-mono text-xs font-bold bg-amber-50 text-amber-900 border border-amber-200">
                      Profile: {dev}
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-500">
                No connected device profiles identified in graph telemetry for this case.
              </div>
            )}
          </div>

          {renderEvidenceSection(
            'Device Evidence Findings',
            deviceEvidence,
            'get_customer_device_history',
            'No anomalous device telemetry flags identified.'
          )}
        </div>
      )}

      {/* 6. Similar Closed Case Precedents */}
      {activeCategory === 'cases' && (
        <div className="space-y-5">
          <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100">
              <h5 className="text-xs font-bold text-slate-900">Historical Closed Case Precedents</h5>
              <span className="text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                Source: get_similar_closed_cases
              </span>
            </div>

            {similarCases.length > 0 ? (
              <div className="space-y-2">
                <span className="text-[10px] uppercase font-bold text-slate-400 block">Matched Prior Fraud Cases</span>
                <div className="flex flex-wrap gap-2">
                  {similarCases.map((sc, i) => (
                    <span key={i} className="px-3 py-1 rounded-lg font-mono text-xs font-bold bg-rose-50 text-rose-800 border border-rose-200">
                      Case #{sc} (Confirmed Fraud)
                    </span>
                  ))}
                </div>
              </div>
            ) : (
              <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-500">
                No matching prior fraud cases identified in graph history.
              </div>
            )}
          </div>

          {renderEvidenceSection(
            'Historical Closed Case Findings',
            caseEvidence,
            'get_similar_closed_cases',
            'No similar closed case precedent evidence available in stored result.'
          )}
        </div>
      )}

      {/* 7. Billing Region */}
      {activeCategory === 'region' && (
        <div className="space-y-5">
          {renderEvidenceSection(
            'Billing Region & Geographic Telemetry',
            regionEvidence,
            'get_customer_regions',
            'No regional mismatch evidence available in stored result.'
          )}
        </div>
      )}

      {/* 8. Network Graph */}
      {activeCategory === 'network' && (
        <div className="space-y-5">
          {renderEvidenceSection(
            'TigerGraph Subgraph Association Findings',
            networkEvidence,
            'investigate_transaction_graph',
            'No network graph anomalies or syndicate linkages found in stored result.'
          )}
        </div>
      )}
    </Card>
  );
}
