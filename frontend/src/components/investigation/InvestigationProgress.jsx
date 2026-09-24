import {
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
  MinusCircle,
} from 'lucide-react';
import { Card } from '../common/Card';
import { PIPELINE_STEPS } from '../../utils/constants';

export function InvestigationProgress({ caseData, currentStepIndex = 12, isInvestigating = false }) {
  const toolCallsList = Array.isArray(caseData?.tool_calls)
    ? caseData.tool_calls.map((tc) => (typeof tc === 'object' && tc !== null ? tc.tool : String(tc)))
    : [];
  const toolsUsed = new Set(
    caseData?.investigation?.tools_used ||
    caseData?.investigation?.tool_call_sequence ||
    toolCallsList
  );

  const getStepStatus = (step, idx) => {
    // If currently investigating live via SSE
    if (isInvestigating) {
      if (idx < currentStepIndex) return 'completed';
      if (idx === currentStepIndex) return 'running';
      return 'pending';
    }

    // If case has final completed result
    if (caseData?.case?.status === 'completed' || caseData?.status === 'completed') {
      if (step.id === 'case_loaded' || step.id === 'assessment' || step.id === 'policy' || step.id === 'final_result') {
        return 'completed';
      }
      if (step.tool && toolsUsed.has(step.tool)) {
        return 'completed';
      }
      // Specific checks for evidence types
      if (step.id === 'email_evidence' || step.id === 'get_device_connections') {
        // Did we search device/email?
        if (toolsUsed.has('get_device_connections') || toolsUsed.has('investigate_transaction_graph')) {
          return 'completed';
        }
        return 'unavailable';
      }
      return toolsUsed.has(step.tool) ? 'completed' : 'unavailable';
    }

    return 'pending';
  };

  return (
    <Card
      title="Investigation Progress & Workflow State"
      subtitle="Observable 12-stage multi-cycle graph evaluation: tracked honestly from tool calls"
      className="overflow-hidden"
    >
      <div className="overflow-x-auto py-2">
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2 min-w-[700px]">
          {PIPELINE_STEPS.map((step, idx) => {
            const status = getStepStatus(step, idx);

            const statusStyles = {
              completed: {
                bg: 'bg-emerald-50 border-emerald-200 text-emerald-800',
                icon: CheckCircle2,
                iconColor: 'text-emerald-600',
                badge: 'Completed',
              },
              running: {
                bg: 'bg-blue-50 border-blue-300 text-blue-800 animate-pulse',
                icon: Loader2,
                iconColor: 'text-blue-600 animate-spin',
                badge: 'Running',
              },
              unavailable: {
                bg: 'bg-slate-50 border-slate-200 text-slate-500 opacity-75',
                icon: MinusCircle,
                iconColor: 'text-slate-400',
                badge: 'No Signal',
              },
              failed: {
                bg: 'bg-red-50 border-red-200 text-red-700',
                icon: XCircle,
                iconColor: 'text-red-500',
                badge: 'Failed',
              },
              pending: {
                bg: 'bg-white border-slate-200 text-slate-400',
                icon: Clock,
                iconColor: 'text-slate-300',
                badge: 'Pending',
              },
            }[status] || {
              bg: 'bg-white border-slate-200 text-slate-500',
              icon: Clock,
              iconColor: 'text-slate-400',
              badge: 'Pending',
            };

            const Icon = statusStyles.icon;

            return (
              <div
                key={step.id}
                className={`p-3 rounded-xl border flex flex-col justify-between transition-all ${statusStyles.bg}`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-mono font-bold text-slate-400">
                    STEP {idx + 1}
                  </span>
                  <Icon className={`h-3.5 w-3.5 ${statusStyles.iconColor}`} />
                </div>
                <div className="text-xs font-semibold text-slate-900 leading-tight">
                  {step.label.replace(/^\d+\.\s*/, '')}
                </div>
                <div className="mt-2 text-[10px] font-medium text-slate-500 flex items-center justify-between">
                  <span>{statusStyles.badge}</span>
                  {step.tool && toolsUsed.has(step.tool) && (
                    <span className="text-[9px] font-mono text-emerald-600">✓ called</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Card>
  );
}
