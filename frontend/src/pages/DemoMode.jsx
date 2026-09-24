import React, { useState } from 'react';
import {
  Play,
  Sparkles,
} from 'lucide-react';
import { Card } from '../components/common/Card';
import { Button } from '../components/common/Button';
import { Badge } from '../components/common/Badge';
import { SummaryCards } from '../components/investigation/SummaryCards';
import { InvestigationProgress } from '../components/investigation/InvestigationProgress';
import { DecisionPolicyCard } from '../components/investigation/DecisionPolicyCard';
import { RelationshipGraph } from '../components/graph/RelationshipGraph';
import { FinalResultCard } from '../components/investigation/FinalResultCard';
import { ToolExecutionLive } from '../components/tools/ToolExecutionLive';

export function DemoMode({
  caseData,
  onSelectCase,
  onStartInvestigation,
  isInvestigating,
  investigationProgressStep,
  activeTool,
}) {
  const [demoCase, setDemoCase] = useState('HHG-001');

  const demoCases = [
    {
      id: 'HHG-001',
      title: 'HHG-001 (Suspected Fraud - Compromised Card History)',
      desc: 'Real-time model score 0.61 on txn #3514030 ($77.07). Autonomous TigerGraph lookup uncovers 4 confirmed prior fraud cases on card C12382-K1.',
    },
    {
      id: 'HHG-014',
      title: 'HHG-014 (Suspected Fraud - Shared Device Profile)',
      desc: 'Analyst alert for txn #3478561 ($74.96). Uncovers device SM-G935F shared across 13 customers and linked to 10 confirmed fraud cases.',
    },
  ];

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

  const handleLaunchDemo = (cid) => {
    setDemoCase(cid);
    onSelectCase(cid);
    onStartInvestigation(cid);
  };

  return (
    <div className="space-y-6">
      {/* Demo Guide Banner */}
      <Card className="bg-linear-to-r from-slate-900 to-indigo-950 text-white border-none shadow-md">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="p-1 rounded bg-indigo-500/30 text-indigo-300 font-mono text-[10px] uppercase font-bold tracking-wider">
                Hackathon Judge Guide
              </span>
              <span className="text-xs text-indigo-200">Interactive Demo Experience</span>
            </div>
            <h2 className="text-2xl font-black tracking-tight">
              Fraud Investigation in 30 Seconds
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl leading-relaxed">
              Experience the end-to-end multi-agent pipeline: intake, autonomous tool execution against TigerGraph Cloud, multi-cycle reasoning, and deterministic policy gates resulting in verified Next Best Actions.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch gap-3 shrink-0">
            <Button
              size="lg"
              variant="primary"
              className="bg-white! text-slate-900! hover:bg-slate-100! font-bold shadow-md"
              icon={Sparkles}
              disabled={isInvestigating}
              onClick={() => handleLaunchDemo('HHG-001')}
            >
              Run Demo Case HHG-001
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="border-indigo-400/50! text-white! hover:bg-indigo-900/50!"
              icon={Play}
              disabled={isInvestigating}
              onClick={() => handleLaunchDemo('HHG-014')}
            >
              Run Demo Case HHG-014
            </Button>
          </div>
        </div>
      </Card>

      {/* Demo Selection Tabs */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {demoCases.map((dc) => (
          <div
            key={dc.id}
            onClick={() => {
              setDemoCase(dc.id);
              onSelectCase(dc.id);
            }}
            className={`p-4 rounded-xl border cursor-pointer transition-all ${
              demoCase === dc.id
                ? 'bg-indigo-50/40 border-indigo-300 shadow-xs'
                : 'bg-white border-slate-200 hover:border-slate-300'
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <h4 className="text-sm font-bold text-slate-900">{dc.title}</h4>
              <Badge variant={demoCase === dc.id ? 'blue' : 'default'} size="sm">
                {demoCase === dc.id ? 'Selected' : 'Select'}
              </Badge>
            </div>
            <p className="text-xs text-slate-600 leading-normal">{dc.desc}</p>
          </div>
        ))}
      </div>

      {/* Real-time Workspace Display */}
      <div className="space-y-6">
        <SummaryCards caseData={caseData} />

        <InvestigationProgress
          caseData={caseData}
          currentStepIndex={investigationProgressStep}
          isInvestigating={isInvestigating}
        />

        <ToolExecutionLive
          toolCalls={toolCalls}
          isRunning={isInvestigating}
          activeTool={activeTool}
        />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          <div className="lg:col-span-7 space-y-6">
            <DecisionPolicyCard caseData={caseData} />
            <FinalResultCard caseData={caseData} />
          </div>
          <div className="lg:col-span-5">
            <RelationshipGraph graphData={caseData?.graph} caseId={demoCase} />
          </div>
        </div>
      </div>
    </div>
  );
}
