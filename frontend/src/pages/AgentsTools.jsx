import React from 'react';
import { AgentsToolsView } from '../components/agents/AgentsToolsView';

export function AgentsTools({ health, tools }) {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black text-slate-900 tracking-tight">
          Agents, Models & Investigative Tools
        </h1>
        <p className="text-xs text-slate-500 mt-1">
          Complete multi-agent topology: Person B investigator, LangGraph, LLM inference, Person A MCP, and TigerGraph tools
        </p>
      </div>

      <AgentsToolsView health={health} tools={tools} />
    </div>
  );
}
