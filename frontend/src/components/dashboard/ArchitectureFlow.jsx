import React from 'react';
import {
  FileText,
  GitMerge,
  Cpu,
  Sparkles,
  Layers,
  Database,
  Search,
  CheckSquare,
  Shield,
  ArrowRight,
  CheckCircle2,
} from 'lucide-react';
import { Card } from '../common/Card';
import { ARCHITECTURE_STAGES } from '../../utils/constants';

export function ArchitectureFlow() {
  const stageIcons = {
    case: FileText,
    langgraph: GitMerge,
    agent: Cpu,
    llm: Sparkles,
    mcp: Layers,
    tigergraph: Database,
    evidence: Search,
    assessment: CheckSquare,
    policy: Shield,
    action: CheckCircle2,
  };

  return (
    <Card
      title="System Architecture Pipeline"
      subtitle="Multi-agent graph decision pipeline: from intake to operational next-best-action"
      className="overflow-hidden"
    >
      <div className="relative overflow-x-auto py-2">
        <div className="flex items-center min-w-[920px] justify-between gap-1">
          {ARCHITECTURE_STAGES.map((stage, idx) => {
            const Icon = stageIcons[stage.id] || Cpu;
            const isLast = idx === ARCHITECTURE_STAGES.length - 1;

            return (
              <React.Fragment key={stage.id}>
                <div className="flex flex-col items-center text-center group cursor-default p-2 rounded-lg hover:bg-slate-50 transition-colors w-24 shrink-0">
                  <div className="h-10 w-10 rounded-xl bg-slate-100 group-hover:bg-slate-900 group-hover:text-white text-slate-700 flex items-center justify-center transition-colors border border-slate-200/80 mb-2 shadow-2xs">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-[11px] font-bold text-slate-900 leading-tight">
                    {stage.label}
                  </span>
                  <span className="text-[9px] text-slate-500 mt-1 line-clamp-2 leading-tight">
                    {stage.desc}
                  </span>
                </div>

                {!isLast && (
                  <div className="flex items-center text-slate-300 shrink-0 -mt-6">
                    <ArrowRight className="h-4 w-4 text-slate-300" />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
