import React from 'react';
import { Database, Sparkles, GitMerge } from 'lucide-react';

export function Footer({ health }) {
  const llmProvider = health?.components?.llm?.provider || 'openrouter';
  const llmModel = health?.components?.llm?.model || 'google/gemini-2.5-flash';
  const tgGraph = health?.components?.tigergraph?.graph || 'HHGOA_IEEE';

  return (
    <footer className="mt-16 border-t border-slate-200 bg-white py-6 text-xs text-slate-500">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4 text-slate-600">
          <span className="flex items-center gap-1.5">
            <Database className="h-3.5 w-3.5 text-slate-400" />
            Graph: <span className="font-semibold text-slate-800">{tgGraph}</span>
          </span>
          <span className="text-slate-300">•</span>
          <span className="flex items-center gap-1.5">
            <GitMerge className="h-3.5 w-3.5 text-slate-400" />
            Orchestration: <span className="font-semibold text-slate-800">LangGraph (Person B)</span>
          </span>
          <span className="text-slate-300">•</span>
          <span className="flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-slate-400" />
            AI Provider: <span className="font-semibold text-slate-800">{llmProvider}</span>
            <span className="text-slate-400">({llmModel})</span>
          </span>
        </div>

        <div className="text-slate-400">
          Enterprise Fraud Decision Support • Hacker House Goa
        </div>
      </div>
    </footer>
  );
}
