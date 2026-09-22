import unittest
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent.assessment import AssessmentSchema
from agent.investigator import InvestigationAgent
from agent.orchestrator import build_investigation_graph
from agent.state import create_initial_state
from tools.tigergraph_fraud import investigate_transaction_graph


class IntegrationInvestigator:
    def __init__(self):
        self.call_count = 0

    def bind_tools(self, tools):
        self.tool_names = {item.name for item in tools}
        return self

    def invoke(self, messages):
        self.call_count += 1
        if self.call_count == 1:
            return AIMessage(
                content="Inspecting the local transaction before graph analysis.",
                tool_calls=[{
                    "name": "get_transaction",
                    "args": {"transaction_id": "3514030"},
                    "id": "local_tx",
                }],
            )
        if self.call_count == 2:
            return AIMessage(
                content="Requesting Person A graph evidence through MCP.",
                tool_calls=[{
                    "name": "investigate_transaction_graph",
                    "args": {"transaction_id": "3514030"},
                    "id": "graph_tx",
                }],
            )
        return AIMessage(
            content="Local and TigerGraph evidence collected; investigation concluded.",
            tool_calls=[],
        )


class IntegrationAssessment:
    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        context = messages[-1].content
        if "graph_signal_from_person_a" not in context:
            raise AssertionError("Assessment did not receive Person A graph evidence")
        return AssessmentSchema(
            verdict="uncertain",
            fraud_probability=0.45,
            fraud_type=None,
            exposure=77.07,
            affected_txn_ids=["3514030"],
            supporting_evidence=["graph_signal_from_person_a"],
            contradicting_evidence=["Local transaction evidence is consistent with the case."],
            reasoning="Assessment consumed local and Person A TigerGraph evidence.",
            confidence=0.60,
        )


class TestPersonABIntegration(unittest.TestCase):
    def test_mcp_graph_evidence_reaches_assessment_and_policy(self):
        graph_result = {
            "transaction_id": "3514030",
            "found": True,
            "fraud_signals": ["graph_signal_from_person_a"],
            "risk_assessment": {"risk_score": 55, "risk_level": "MEDIUM"},
            "network_evidence": {
                "linked_cards": [{"card_id": "C12382-K1"}],
                "related_transaction_count": 2,
                "related_transactions": [],
            },
        }
        investigator = InvestigationAgent(IntegrationInvestigator())
        workflow = build_investigation_graph(
            investigator=investigator,
            assessment_llm=IntegrationAssessment(),
        )
        initial_state = create_initial_state(
            case_id="HHG-001",
            customer_id="C12382",
            card_id="C12382-K1",
            flagged_txn_id="3514030",
        )

        with patch(
            "tools.tigergraph_fraud._call_person_a_mcp",
            return_value=graph_result,
        ) as mcp_call:
            final_state = workflow.invoke(initial_state)

        mcp_call.assert_called_once_with("3514030")
        self.assertIn("get_transaction", final_state["tools_used"])
        self.assertIn("investigate_transaction_graph", final_state["tools_used"])
        self.assertTrue(any(
            evidence["source"] == "investigate_transaction_graph"
            and evidence["data"]["result"] == graph_result
            for evidence in final_state["evidence"]
        ))
        self.assertIn("graph_signal_from_person_a", final_state["assessment"]["supporting_evidence"])
        self.assertTrue(final_state["policy_decision"])


if __name__ == "__main__":
    unittest.main()