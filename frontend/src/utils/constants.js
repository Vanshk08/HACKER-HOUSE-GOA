/**
 * System constants and architecture definitions.
 */

export const PIPELINE_STEPS = [
  { id: 'case_loaded', label: '1. Case Loaded', tool: null },
  { id: 'get_transaction', label: '2. Transaction Profile', tool: 'get_transaction' },
  { id: 'get_customer_history', label: '3. Customer History', tool: 'get_customer_history' },
  { id: 'get_card_history', label: '4. Card History', tool: 'get_card_history' },
  { id: 'related_transactions', label: '5. Related Transactions', tool: 'get_transaction_sequence' },
  { id: 'get_device_connections', label: '6. Device Evidence', tool: 'get_device_connections' },
  { id: 'get_customer_regions', label: '7. Region Evidence', tool: 'get_customer_regions' },
  { id: 'email_evidence', label: '8. Email Evidence', tool: 'investigate_transaction_graph' },
  { id: 'get_similar_closed_cases', label: '9. Similar Closed Cases', tool: 'get_similar_closed_cases' },
  { id: 'assessment', label: '10. Assessment', tool: null },
  { id: 'policy', label: '11. Policy Decision', tool: null },
  { id: 'final_result', label: '12. Final Result', tool: null },
];

export const ARCHITECTURE_STAGES = [
  { id: 'case', label: 'CASE INTAKE', desc: 'Case pack / Real-time trigger', icon: 'file-text' },
  { id: 'langgraph', label: 'LANGGRAPH', desc: 'Cyclic state orchestrator', icon: 'git-merge' },
  { id: 'agent', label: 'INVESTIGATION AGENT', desc: 'Person B reasoning engine', icon: 'cpu' },
  { id: 'llm', label: 'LLM PROVIDER', desc: 'OpenRouter / Vertex / GCP', icon: 'sparkles' },
  { id: 'mcp', label: 'MCP / RETRIEVAL', desc: 'Person A FraudAnalyzer bridge', icon: 'layers' },
  { id: 'tigergraph', label: 'TIGERGRAPH CLOUD', desc: 'Graph HHGOA_IEEE database', icon: 'database' },
  { id: 'evidence', label: 'EVIDENCE AGGREGATION', desc: 'Graph-grounded signals', icon: 'search' },
  { id: 'assessment', label: 'ASSESSMENT', desc: 'Verdict & confidence calculation', icon: 'check-square' },
  { id: 'policy', label: 'POLICY ENGINE', desc: 'Deterministic rule evaluation', icon: 'shield' },
  { id: 'action', label: 'NEXT BEST ACTION', desc: 'Operational decision output', icon: 'arrow-right-circle' },
];
