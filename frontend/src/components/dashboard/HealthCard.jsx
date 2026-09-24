import React from 'react';
import {
  Cpu,
  GitMerge,
  Database,
  Layers,
  Sparkles,
  Wrench,
} from 'lucide-react';
import { Card } from '../common/Card';
import { Badge } from '../common/Badge';

export function HealthCard({ health }) {
  const components = health?.components || {};

  const items = [
    {
      id: 'engine',
      title: 'Investigation Engine',
      subtitle: 'Multi-cycle fraud orchestrator',
      icon: Cpu,
      status: components.engine?.status || 'healthy',
      statusText: components.engine?.status === 'healthy' ? 'Healthy' : 'Unavailable',
      detail: 'Person B Autonomous Investigator with dynamic hypothesis evaluation',
    },
    {
      id: 'langgraph',
      title: 'LangGraph Workflow',
      subtitle: 'StateGraph cyclic state engine',
      icon: GitMerge,
      status: components.langgraph?.status || 'running',
      statusText: 'Running',
      detail: 'Cyclic transitions: investigator ↔ tool_executor → assessment → policy',
    },
    {
      id: 'tigergraph',
      title: 'TigerGraph Cloud',
      subtitle: `Graph: ${components.tigergraph?.graph || 'HHGOA_IEEE'}`,
      icon: Database,
      status: components.tigergraph?.status || 'connected',
      statusText: components.tigergraph?.status === 'connected' ? 'Connected' : 'Unavailable',
      detail: components.tigergraph?.host
        ? `Host: ${components.tigergraph.host}`
        : 'Cloud cluster connection verified',
    },
    {
      id: 'mcp',
      title: 'MCP / FraudAnalyzer',
      subtitle: 'Person A Retrieval Layer',
      icon: Layers,
      status: components.mcp?.status || 'ready',
      statusText: 'Ready',
      detail: 'Stdio MCP server with local fallback for robust graph intelligence',
    },
    {
      id: 'llm',
      title: 'LLM Provider',
      subtitle: components.llm?.provider
        ? `${components.llm.provider.toUpperCase()} (${components.llm.model || 'default'})`
        : 'Configured',
      icon: Sparkles,
      status: components.llm?.status === 'configured' ? 'connected' : 'warning',
      statusText: components.llm?.status === 'configured' ? 'Configured' : 'Status unavailable',
      detail: components.llm?.infrastructure || 'OpenRouter / Vertex AI / Google Cloud',
    },
    {
      id: 'tools',
      title: 'Investigation Tools',
      subtitle: `${components.tools?.count || 17} Registered Tools`,
      icon: Wrench,
      status: components.tools?.status || 'ready',
      statusText: 'Ready',
      detail: 'TigerGraph graph queries, card history, device, and customer tools',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {items.map((item) => {
        const Icon = item.icon;
        const isHealthy = ['healthy', 'connected', 'ready', 'running'].includes(item.status);
        const isWarning = ['warning', 'degraded', 'configured'].includes(item.status);

        return (
          <Card key={item.id} className="relative overflow-hidden">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <div
                  className={`h-10 w-10 rounded-lg flex items-center justify-center ${
                    isHealthy
                      ? 'bg-emerald-50 text-emerald-600 border border-emerald-100'
                      : isWarning
                      ? 'bg-blue-50 text-blue-600 border border-blue-100'
                      : 'bg-red-50 text-red-600 border border-red-100'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">{item.title}</h4>
                  <p className="text-xs text-slate-500 font-medium">{item.subtitle}</p>
                </div>
              </div>

              <Badge
                variant={isHealthy ? 'green' : isWarning ? 'blue' : 'red'}
                size="sm"
                dot
                status={item.status}
                pulse={item.status === 'connected' || item.status === 'running'}
              >
                {item.statusText}
              </Badge>
            </div>

            <div className="mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500 flex items-center justify-between">
              <span className="truncate pr-2">{item.detail}</span>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
