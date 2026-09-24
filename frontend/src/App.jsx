import React, { useState, useEffect, useCallback } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Footer } from './components/layout/Footer';
import { InvestigationWorkspace } from './pages/InvestigationWorkspace';
import { Overview } from './pages/Overview';
import { EvidencePage } from './pages/EvidencePage';
import { GraphPage } from './pages/GraphPage';
import { TimelinePage } from './pages/TimelinePage';
import { AgentsTools } from './pages/AgentsTools';
import { SystemHealthPage } from './pages/SystemHealthPage';

import { fetchHealth } from './api/healthApi';
import { fetchMetrics } from './api/metricsApi';
import {
  fetchCases,
  fetchCase,
  startInvestigation,
  subscribeInvestigationStream,
} from './api/investigationApi';
import { fetchTools } from './api/toolsApi';

export function App() {
  // Default to the Single-Case Investigation Workspace
  const [activeTab, setActiveTab] = useState('workspace');

  // Backend state
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [cases, setCases] = useState([]);
  const [tools, setTools] = useState([]);

  // Default demo case: HHG-001 (Transaction: 3514030)
  const [selectedCaseId, setSelectedCaseId] = useState('HHG-001');
  const [caseData, setCaseData] = useState(null);

  // Single-case investigation execution state
  const [isInvestigating, setIsInvestigating] = useState(false);
  const [investigationProgressStep, setInvestigationProgressStep] = useState(12);
  const [activeTool, setActiveTool] = useState(null);
  const [investigationError, setInvestigationError] = useState(null);

  // Initial data loading
  useEffect(() => {
    async function loadInitialData() {
      try {
        const [healthRes, metricsRes, casesRes, toolsRes] = await Promise.all([
          fetchHealth().catch((e) => ({ status: 'unavailable', error: e.message })),
          fetchMetrics().catch(() => null),
          fetchCases().catch(() => ({ cases: [] })),
          fetchTools().catch(() => ({ tools: [] })),
        ]);

        setHealth(healthRes);
        setMetrics(metricsRes);
        setCases(casesRes?.cases || []);
        setTools(toolsRes?.tools || []);
      } catch (err) {
        console.error('Initial data load error:', err);
      }
    }

    loadInitialData();
  }, []);

  // Fetch selected single case data
  const loadCaseData = useCallback(async (caseId) => {
    setInvestigationError(null);
    try {
      const data = await fetchCase(caseId);
      setCaseData(data);
    } catch (err) {
      console.error(`Failed to load case ${caseId}:`, err);
      setInvestigationError(err.message);
    }
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      loadCaseData(selectedCaseId);
    }
  }, [selectedCaseId, loadCaseData]);

  // Case selection handler (single-case only)
  const handleSelectCase = (caseId) => {
    setSelectedCaseId(caseId);
  };

  // Start / stream single-case investigation for the selected case only
  const handleStartInvestigation = async (caseId = selectedCaseId) => {
    setIsInvestigating(true);
    setInvestigationError(null);
    setInvestigationProgressStep(1);
    setActiveTool(null);

    // Stream the single-case investigation
    try {
      let currentStep = 1;
      subscribeInvestigationStream(
        caseId,
        (event) => {
          if (event.type === 'case_loaded') {
            setInvestigationProgressStep(1);
          } else if (event.type === 'tool_execution') {
            currentStep += 1;
            setInvestigationProgressStep(Math.min(currentStep, 9));
            setActiveTool(event.data.tool);
          } else if (event.type === 'assessment') {
            setInvestigationProgressStep(10);
            setActiveTool(null);
          } else if (event.type === 'policy') {
            setInvestigationProgressStep(11);
          } else if (event.type === 'complete') {
            setInvestigationProgressStep(12);
            setIsInvestigating(false);
            if (event.data?.result) {
              setCaseData(event.data.result);
            }
          }
        },
        async (error) => {
          console.warn('SSE stream error, executing single case directly:', error);
          try {
            const result = await startInvestigation(caseId);
            setCaseData(result);
            setInvestigationProgressStep(12);
          } catch (e) {
            setInvestigationError(e.message);
          } finally {
            setIsInvestigating(false);
          }
        },
        (finalResult) => {
          setIsInvestigating(false);
          if (finalResult?.result) {
            setCaseData(finalResult.result);
          }
        }
      );
    } catch (err) {
      console.error('Investigation execution failed:', err);
      setInvestigationError(err.message);
      setIsInvestigating(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900 antialiased selection:bg-indigo-100 selection:text-indigo-900">
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        health={health}
      />

      {/* Main Single-Case Investigation View */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'workspace' && (
          <InvestigationWorkspace
            caseData={caseData}
            cases={cases}
            selectedCaseId={selectedCaseId}
            onSelectCase={handleSelectCase}
            onStartInvestigation={handleStartInvestigation}
            isInvestigating={isInvestigating}
            investigationProgressStep={investigationProgressStep}
            activeTool={activeTool}
            investigationError={investigationError}
          />
        )}

        {activeTab === 'overview' && (
          <Overview
            health={health}
            metrics={metrics}
            cases={cases}
            onSelectCase={(cid) => {
              handleSelectCase(cid);
              setActiveTab('workspace');
            }}
            onStartInvestigation={handleStartInvestigation}
          />
        )}

        {activeTab === 'evidence' && (
          <EvidencePage
            caseData={caseData}
            cases={cases}
            selectedCaseId={selectedCaseId}
            onSelectCase={handleSelectCase}
          />
        )}

        {activeTab === 'graph' && (
          <GraphPage
            caseData={caseData}
            cases={cases}
            selectedCaseId={selectedCaseId}
            onSelectCase={handleSelectCase}
          />
        )}

        {activeTab === 'timeline' && (
          <TimelinePage
            caseData={caseData}
            cases={cases}
            selectedCaseId={selectedCaseId}
            onSelectCase={handleSelectCase}
          />
        )}

        {activeTab === 'agents' && (
          <AgentsTools health={health} tools={tools} />
        )}

        {activeTab === 'health' && (
          <SystemHealthPage health={health} metrics={metrics} />
        )}
      </main>

      {/* Footer */}
      <Footer health={health} />
    </div>
  );
}

export default App;
