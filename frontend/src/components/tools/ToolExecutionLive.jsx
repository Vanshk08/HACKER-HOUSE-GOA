import React from 'react';
import {
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';

export function ToolExecutionLive({ toolCalls = [], isRunning = false, activeTool = null }) {
  const safeList = Array.isArray(toolCalls) ? toolCalls : [];
  if (safeList.length === 0 && !isRunning) {
    return null;
  }

  return (
    <Card
      title="Observable Tool Execution Monitor"
      subtitle="Auditable runtime execution: tool arguments, duration, and status without hidden model reasoning"
      action={
        <Badge variant={isRunning ? 'blue' : 'green'} size="sm" dot pulse={isRunning}>
          {isRunning ? 'Executing Tools...' : `${safeList.length} Tools Completed`}
        </Badge>
      }
      className="border-slate-200/90"
    >
      <div className="space-y-2.5 max-h-80 overflow-y-auto pr-1">
        {safeList.map((tc, idx) => {
          const tool = tc.tool;
          const args = tc.args || {};
          const isCurrent = activeTool === tool && isRunning;

          return (
            <div
              key={idx}
              className={`p-3 rounded-xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                isCurrent
                  ? 'bg-blue-50/70 border-blue-300 shadow-xs'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center gap-3">
                <div
                  className={`h-8 w-8 rounded-lg flex items-center justify-center shrink-0 ${
                    isCurrent
                      ? 'bg-blue-600 text-white'
                      : 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                  }`}
                >
                  {isCurrent ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="h-4 w-4" />
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-900">{tool}</span>
                    <span className="text-[10px] text-slate-400 font-mono">#{idx + 1}</span>
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5 truncate max-w-md">
                    Input: {Object.keys(args).length > 0 ? JSON.stringify(args) : '—'}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 self-end sm:self-auto">
                <Badge variant={isCurrent ? 'blue' : 'green'} size="sm">
                  {isCurrent ? 'Executing' : 'Completed'}
                </Badge>
                <span className="text-[10px] font-mono text-slate-400">TigerGraph</span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
