import React from 'react';
import { HealthCard } from '../components/dashboard/HealthCard';
import { ArchitectureFlow } from '../components/dashboard/ArchitectureFlow';
import { MetricsRow } from '../components/dashboard/MetricsRow';

export function SystemHealthPage({ health, metrics }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          System Health & Architecture
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Real-time status of TigerGraph Cloud, LangGraph workflow, LLM inference provider, and MCP retrieval layer
        </p>
      </div>

      {/* Component Health Cards */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs uppercase font-bold tracking-wider text-slate-400">
            Active System Components
          </h2>
          <span className="text-[11px] text-slate-400">Ground-truth verification</span>
        </div>
        <HealthCard health={health} />
      </section>

      {/* System Metrics */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs uppercase font-bold tracking-wider text-slate-400">
            Engine Benchmark Telemetry
          </h2>
          <span className="text-[11px] text-slate-400">Evaluation statistics</span>
        </div>
        <MetricsRow metrics={metrics} />
      </section>

      {/* Architecture Flow */}
      <section>
        <ArchitectureFlow />
      </section>
    </div>
  );
}
