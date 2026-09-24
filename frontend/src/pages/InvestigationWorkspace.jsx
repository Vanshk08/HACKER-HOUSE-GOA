import React from 'react';
import { WorkspaceHeader } from '../components/investigation/WorkspaceHeader';
import { SummaryCards } from '../components/investigation/SummaryCards';
import { InvestigationProgress } from '../components/investigation/InvestigationProgress';
import { DecisionPolicyCard } from '../components/investigation/DecisionPolicyCard';
import { FinalResultCard } from '../components/investigation/FinalResultCard';
import { RelationshipGraph } from '../components/graph/RelationshipGraph';
import { ToolExecutionLive } from '../components/tools/ToolExecutionLive';
import { EvidenceDashboard } from '../components/evidence/EvidenceDashboard';
import { TechnicalDetails } from '../components/investigation/TechnicalDetails';
import { InvestigationTimeline } from '../components/timeline/InvestigationTimeline';

export function InvestigationWorkspace({
  caseData,
  cases = [],
  selectedCaseId,
  onSelectCase,
  onStartInvestigation,
  isInvestigating = false,
  investigationProgressStep = 12,
  activeTool = null,
  investigationError = null,
}) {
  const toolCalls = Array.isArray(caseData?.tool_calls)
    ? caseData.tool_calls
    : (caseData?.investigation?.tool_call_sequence || caseData?.investigation?.tools_used || []).map((t) =>
        typeof t === 'string' ? { tool: t, args: {} } : t
      );
  const graphData = caseData?.graph || null;

  return (
    <div className="space-y-6">
      {/* 1. Header with Case Controls */}
      <WorkspaceHeader
        caseData={caseData}
        cases={cases}
        selectedCaseId={selectedCaseId}
        onSelectCase={onSelectCase}
        onStartInvestigation={onStartInvestigation}
        isInvestigating={isInvestigating}
        investigationError={investigationError}
      />

      {/* 2. Key Summary Cards (Risk Score, Verdict, Policy, NBA, SAR) */}
      <SummaryCards caseData={caseData} />

      {/* 3. 12-Step Investigation Progress */}
      <InvestigationProgress
        caseData={caseData}
        currentStepIndex={investigationProgressStep}
        isInvestigating={isInvestigating}
      />

      {/* 4. Live Tool Execution View (Observable During/After Run) */}
      <ToolExecutionLive
        toolCalls={toolCalls}
        isRunning={isInvestigating}
        activeTool={activeTool}
      />

      {/* 5. Centerpiece 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column (7 cols): Decision & Policy + Final Result */}
        <div className="lg:col-span-7 space-y-6">
          {/* Decision & Policy Flow */}
          <DecisionPolicyCard caseData={caseData} />

          {/* Final Result & Why This Result? (Structured Factors) */}
          <FinalResultCard caseData={caseData} />
        </div>

        {/* Right Column (5 cols): Relationship Graph & Evidence Overview */}
        <div className="lg:col-span-5 space-y-6">
          {/* TigerGraph Relationship Graph */}
          <RelationshipGraph graphData={graphData} caseId={selectedCaseId} />

          {/* Timeline snippet */}
          <InvestigationTimeline caseData={caseData} />
        </div>
      </div>

      {/* 6. Categorized Evidence Dashboard */}
      <EvidenceDashboard caseData={caseData} />

      {/* 7. Collapsible Technical Details (No secrets) */}
      <TechnicalDetails caseData={caseData} />
    </div>
  );
}
